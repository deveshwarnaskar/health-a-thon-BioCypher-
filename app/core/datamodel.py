"""Thin, dependency-free persistence layer on top of SQLite.

Table shapes
------------
patients(id, name, uh_id, phone, lang, is_active)
caregivers(id, patient_id, phone, name, ts)          (max ONE active per patient)
avoid_items(id, patient_id, set_by, item, ts)
windows(id, patient_id, start_date, end_date, status, caregiver_phone, created_at)
meals(id, window_id, ts, sender_phone, role, source, status,
      items_json, portion, portion_ml, carbs, gi, confidence, correction_note)
readings(id, window_id, ts, sender_phone, role, tag, value)
outbound(id, window_id, ts, route, kind, body)       (what we sent — audit/nudge log)
audit(id, ts, actor, action, detail)

`meals.status` = pending | confirmed | corrected  — the confirm loop.
Only confirmed/corrected rows feed the doctor report.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterator, Optional

from .clock import iso_now, now_local


def _type_from_tag(tag: Optional[str]) -> Optional[str]:
    """Collapse any legacy reading tag/context into the 3 doctor-meaningful
    types: fasting | postprandial (2hr after eating) | random.
    pre-meal pricks are no longer tracked -> typed as random."""
    t = str(tag or "").strip().lower()
    if not t:
        return None
    if t == "fasting":
        return "fasting"
    if t == "pre":
        return "random"
    if t in ("postbreakfast", "postlunch", "postdinner"):
        return "postprandial"
    if t == "random":
        return "random"
    return "postprandial"

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients(
    id INTEGER PRIMARY KEY, name TEXT, uh_id TEXT UNIQUE, phone TEXT,
    lang TEXT DEFAULT 'sa', is_active INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS caregivers(
    id INTEGER PRIMARY KEY, patient_id INTEGER REFERENCES patients(id),
    phone TEXT, name TEXT, ts TEXT, active INTEGER DEFAULT 1);

CREATE TABLE IF NOT EXISTS avoid_items(
    id INTEGER PRIMARY KEY, patient_id INTEGER REFERENCES patients(id),
    set_by TEXT, item TEXT, ts TEXT);

CREATE TABLE IF NOT EXISTS windows(
    id INTEGER PRIMARY KEY, patient_id INTEGER REFERENCES patients(id),
    start_date TEXT, end_date TEXT, status TEXT DEFAULT 'open',
    caregiver_phone TEXT, created_at TEXT);

CREATE TABLE IF NOT EXISTS meals(
    id INTEGER PRIMARY KEY, window_id INTEGER REFERENCES windows(id),
    ts TEXT, sender_phone TEXT, role TEXT, source TEXT,
    status TEXT DEFAULT 'pending',
    items_json TEXT, portion TEXT, portion_ml REAL, carbs REAL,
    gi TEXT, confidence REAL, correction_note TEXT);

CREATE TABLE IF NOT EXISTS readings(
    id INTEGER PRIMARY KEY, window_id INTEGER REFERENCES windows(id),
    ts TEXT, sender_phone TEXT, role TEXT, tag TEXT, value REAL);

CREATE TABLE IF NOT EXISTS outbound(
    id INTEGER PRIMARY KEY, window_id INTEGER REFERENCES windows(id),
    ts TEXT, route TEXT, kind TEXT, body TEXT, unique_key TEXT UNIQUE);

CREATE TABLE IF NOT EXISTS audit(
    id INTEGER PRIMARY KEY, ts TEXT, actor TEXT, action TEXT, detail TEXT);

CREATE TABLE IF NOT EXISTS raw_inbound(
    id INTEGER PRIMARY KEY, window_id INTEGER REFERENCES windows(id),
    ts TEXT, sender_phone TEXT, role TEXT, raw_text TEXT, refined_json TEXT, status TEXT);

CREATE TABLE IF NOT EXISTS webhook_events(
    id INTEGER PRIMARY KEY, ts TEXT, event_type TEXT, client_ip TEXT,
    status TEXT, detail TEXT);

CREATE INDEX IF NOT EXISTS ix_meals_window ON meals(window_id);
CREATE INDEX IF NOT EXISTS ix_readings_window ON readings(window_id);
CREATE INDEX IF NOT EXISTS ix_raw_inbound_window ON raw_inbound(window_id);
CREATE INDEX IF NOT EXISTS ix_webhook_events_ts ON webhook_events(ts);
"""


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")


class Store:
    def __init__(self, path: str = "aahaar.db"):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("PRAGMA busy_timeout=5000")
        except sqlite3.OperationalError:
            pass
        self.conn.executescript(SCHEMA)
        # additive migration: idempotency key for Meta webhook message IDs
        try:
            self.conn.execute("ALTER TABLE raw_inbound ADD COLUMN message_id TEXT")
        except sqlite3.OperationalError:
            pass  # column already present
        # additive migration: readings confirmation state + candidate values
        for col, ddl in (
            ("status", "ALTER TABLE readings ADD COLUMN status TEXT DEFAULT 'confirmed'"),
            ("candidates_json", "ALTER TABLE readings ADD COLUMN candidates_json TEXT"),
            ("raw_id", "ALTER TABLE readings ADD COLUMN raw_id INTEGER"),
            ("reading_type", "ALTER TABLE readings ADD COLUMN reading_type TEXT"),
        ):
            try:
                self.conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already present
        # additive migration: patient-stated meal size + meal replacement chain
        for col, ddl in (
            ("portion_text", "ALTER TABLE meals ADD COLUMN portion_text TEXT"),
            ("superseded_by", "ALTER TABLE meals ADD COLUMN superseded_by INTEGER"),
        ):
            try:
                self.conn.execute(ddl)
            except sqlite3.OperationalError:
                pass  # column already present
        # reading_type backfill from the legacy tag (idempotent: NULLs only).
        # pre-meal pricks are no longer a type -> typed as random; the old meal
        # slots collapse to one 2hr post-prandial type.
        self.conn.execute(
            "UPDATE readings SET reading_type='fasting'"
            " WHERE reading_type IS NULL AND tag='fasting'")
        self.conn.execute(
            "UPDATE readings SET reading_type='random'"
            " WHERE reading_type IS NULL AND tag='pre'")
        self.conn.execute(
            "UPDATE readings SET reading_type='postprandial'"
            " WHERE reading_type IS NULL AND tag IN"
            " ('postprandial','postbreakfast','postlunch','postdinner')")
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ---- patients ----------------------------------------------------
    def add_patient(self, name, uh_id, phone, lang="sa", is_active=1) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO patients(name, uh_id, phone, lang, is_active) VALUES(?,?,?,?,?)",
                (name, uh_id, phone, lang, is_active))
            return cur.lastrowid

    def get_patient(self, patient_id: int) -> Optional[dict]:
        r = self.conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
        return dict(r) if r else None

    def list_patients(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM patients ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def get_patient_by_phone(self, phone: str) -> Optional[dict]:
        if not phone:
            return None
        clean = re.sub(r"\D", "", str(phone))
        # 1. Exact match
        r = self.conn.execute("SELECT * FROM patients WHERE phone=? AND is_active=1",
                              (phone,)).fetchone()
        if r:
            return dict(r)
        # 2. Normalized digits match (e.g. +917439030190 vs 917439030190 vs 7439030190)
        rows = self.conn.execute("SELECT * FROM patients WHERE is_active=1").fetchall()
        for row in rows:
            p_clean = re.sub(r"\D", "", str(row["phone"] or ""))
            if p_clean == clean or (len(clean) >= 10 and len(p_clean) >= 10 and clean[-10:] == p_clean[-10:]):
                return dict(row)
        return None

    def get_patient_by_uh(self, uh_id: str) -> Optional[dict]:
        r = self.conn.execute("SELECT * FROM patients WHERE uh_id=?", (uh_id,)).fetchone()
        return dict(r) if r else None

    def set_patient_phone(self, patient_id: int, phone: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE patients SET phone=? WHERE id=?", (phone, patient_id))

    # ---- caregivers --------------------------------------------------
    def set_caregiver(self, patient_id: int, phone: str, name: str) -> int:
        with self.tx() as c:
            c.execute("UPDATE caregivers SET active=0 WHERE patient_id=?", (patient_id,))
            cur = c.execute(
                "INSERT INTO caregivers(patient_id, phone, name, ts, active) VALUES(?,?,?,?,1)",
                (patient_id, phone, name, iso_now()))
            return cur.lastrowid

    def get_caregiver(self, patient_id: int) -> Optional[dict]:
        r = self.conn.execute(
            "SELECT * FROM caregivers WHERE patient_id=? AND active=1",
            (patient_id,)).fetchone()
        return dict(r) if r else None

    def set_caregiver_phone(self, patient_id: int, phone: str,
                            name: Optional[str] = None) -> None:
        """(Re)link a caregiver number, keeping the current caregiver label.
        Open windows are kept in sync so the role guard binds the new number."""
        existing = self.get_caregiver(patient_id)
        self.set_caregiver(patient_id, phone, name or (existing or {}).get("name")
                           or "Designated caregiver")
        with self.tx() as c:
            c.execute("UPDATE windows SET caregiver_phone=? "
                      "WHERE patient_id=? AND status='open'", (phone, patient_id))

    def clear_caregiver(self, patient_id: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE caregivers SET active=0 WHERE patient_id=?", (patient_id,))
            c.execute("UPDATE windows SET caregiver_phone=NULL "
                      "WHERE patient_id=? AND status='open'", (patient_id,))

    # ---- avoid list ---------------------------------------------------
    def set_avoid_items(self, patient_id: int, set_by: str, items: list[str]):
        with self.tx() as c:
            c.execute("DELETE FROM avoid_items WHERE patient_id=?", (patient_id,))
            for it in items:
                c.execute("INSERT INTO avoid_items(patient_id, set_by, item, ts) VALUES(?,?,?,?)",
                          (patient_id, set_by, it.strip(), iso_now()))

    def get_avoid_items(self, patient_id: int) -> list[str]:
        rows = self.conn.execute("SELECT item FROM avoid_items WHERE patient_id=?",
                                 (patient_id,)).fetchall()
        return [r["item"] for r in rows]

    # ---- windows ------------------------------------------------------
    def open_window(self, patient_id: int, start_date: str, end_date: str,
                    caregiver_phone: Optional[str] = None) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO windows(patient_id, start_date, end_date, status, caregiver_phone, created_at)"
                " VALUES(?,?,?, 'open', ?, ?)",
                (patient_id, start_date, end_date, caregiver_phone, iso_now()))
            return cur.lastrowid

    def close_window(self, window_id: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE windows SET status='closed' WHERE id=?", (window_id,))

    def list_windows(self, patient_id: Optional[int] = None) -> list[dict]:
        q = "SELECT * FROM windows"
        args: tuple = ()
        if patient_id is not None:
            q += " WHERE patient_id=?"
            args = (patient_id,)
        q += " ORDER BY start_date"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    def get_window(self, window_id: int) -> Optional[dict]:
        r = self.conn.execute("SELECT * FROM windows WHERE id=?", (window_id,)).fetchone()
        return dict(r) if r else None

    def active_window_for(self, patient_id: int, on: Optional[date] = None) -> Optional[dict]:
        on = on or date.today()
        d = on.isoformat()
        rows = self.conn.execute(
            "SELECT * FROM windows WHERE patient_id=? AND status='open' AND start_date<=? AND end_date>=? "
            "ORDER BY start_date DESC LIMIT 1", (patient_id, d, d)).fetchall()
        return dict(rows[0]) if rows else None

    def last_window_for(self, patient_id: int) -> Optional[dict]:
        r = self.conn.execute(
            "SELECT * FROM windows WHERE patient_id=? ORDER BY end_date DESC LIMIT 1",
            (patient_id,)).fetchone()
        return dict(r) if r else None

    # ---- meals (the confirm loop lives here) --------------------------
    def propose_meal(self, window_id: int, sender_phone: str, role: str, source: str,
                     items: list[dict], portion: str, portion_ml: float,
                     carbs: float, gi: str, confidence: float,
                     ts: Optional[str] = None,
                     portion_text: Optional[str] = None,
                     superseded_by: Optional[int] = None) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO meals(window_id, ts, sender_phone, role, source, status, items_json,"
                " portion, portion_ml, carbs, gi, confidence, portion_text, superseded_by)"
                " VALUES(?,?,?,?,?, 'pending', ?,?,?,?,?,?,?,?)",
                (window_id, ts or iso_now(), sender_phone, role, source,
                 json.dumps(items, ensure_ascii=False), portion, portion_ml, carbs, gi,
                 confidence, portion_text, superseded_by))
            return cur.lastrowid

    def mark_pending_stale(self, sender_phone: str) -> None:
        clean = re.sub(r"\D", "", str(sender_phone or ""))
        with self.tx() as c:
            c.execute("UPDATE meals SET status='stale' WHERE sender_phone=? AND status='pending'",
                      (sender_phone,))
            if clean:
                rows = c.execute("SELECT id, sender_phone FROM meals WHERE status='pending'").fetchall()
                for r in rows:
                    r_clean = re.sub(r"\D", "", str(r["sender_phone"] or ""))
                    if r_clean == clean or (len(clean) >= 10 and len(r_clean) >= 10 and clean[-10:] == r_clean[-10:]):
                        c.execute("UPDATE meals SET status='stale' WHERE id=?", (r["id"],))

    def newest_pending(self, sender_phone: str) -> Optional[dict]:
        r = self.conn.execute(
            "SELECT * FROM meals WHERE sender_phone=? AND status='pending' "
            "ORDER BY ts DESC LIMIT 1", (sender_phone,)).fetchone()
        if r:
            return dict(r)
        clean = re.sub(r"\D", "", str(sender_phone or ""))
        if clean:
            rows = self.conn.execute(
                "SELECT * FROM meals WHERE status='pending' ORDER BY ts DESC"
            ).fetchall()
            for row in rows:
                r_clean = re.sub(r"\D", "", str(row["sender_phone"] or ""))
                if r_clean == clean or (len(clean) >= 10 and len(r_clean) >= 10 and clean[-10:] == r_clean[-10:]):
                    return dict(row)
        return None

    def finalize_meal(self, meal_id: int, status: str, portion: Optional[str] = None,
                      correction_note: Optional[str] = None,
                      portion_text: Optional[str] = None) -> None:
        meal = self.conn.execute("SELECT * FROM meals WHERE id=?", (meal_id,)).fetchone()
        if not meal:
            return
        with self.tx() as c:
            op = "UPDATE meals SET status=?"
            args: list = [status]
            if portion:
                op += ", portion=?, correction_note=?"
                args += [portion, correction_note or portion]
            elif correction_note:
                op += ", correction_note=?"
                args.append(correction_note)
            if portion_text:
                op += ", portion_text=?"
                args.append(portion_text)
            op += " WHERE id=?"
            args.append(meal_id)
            c.execute(op, tuple(args))

    def meals_for_window(self, window_id: int, confirmed_only: bool = True) -> list[dict]:
        q = ("SELECT * FROM meals WHERE window_id=? "
             + ("AND status IN ('confirmed','corrected') " if confirmed_only else "")
             + "ORDER BY ts")
        return [dict(r) for r in self.conn.execute(q, (window_id,)).fetchall()]

    def update_meal(self, meal_id: int, portion: Optional[str] = None,
                    items_json: Optional[str] = None, ts: Optional[str] = None,
                    status: Optional[str] = None, carbs: Optional[float] = None,
                    gi: Optional[str] = None,
                    portion_text: Optional[str] = None,
                    superseded_by: Optional[int] = None) -> None:
        """Edit a logged meal (operator edit or AI correction)."""
        sets: list[str] = []
        args: list = []
        for col, val in (("portion", portion), ("items_json", items_json),
                         ("ts", ts), ("status", status), ("carbs", carbs),
                         ("gi", gi), ("portion_text", portion_text),
                         ("superseded_by", superseded_by)):
            if val is not None:
                sets.append(f"{col}=?")
                args.append(val)
        if not sets:
            return
        args.append(int(meal_id))
        with self.tx() as c:
            c.execute(f"UPDATE meals SET {', '.join(sets)} WHERE id=?",
                      tuple(args))

    def supersede_meal(self, meal_id: int, by_meal_id: int) -> None:
        """Tag an existing meal as replaced by a new one while keeping the row,
        so the previous + changed version stay visible at the same time."""
        with self.tx() as c:
            c.execute("UPDATE meals SET status='superseded', superseded_by=? WHERE id=?",
                      (int(by_meal_id), int(meal_id)))

    def meal_at_time(self, window_id: int, ts: str,
                     except_id: Optional[int] = None) -> Optional[dict]:
        """Latest meal in the same window on the SAME day/time (used to detect
        that a new meal is a replacement of an existing one)."""
        base = (ts or "")[:16]
        if len(base) < 16:
            return None
        with self.tx() as c:
            r = c.execute(
                "SELECT * FROM meals WHERE window_id=? AND substr(ts,1,16)=? "
                "AND status IN ('confirmed','corrected') AND (superseded_by IS NULL) "
                "AND (? IS NULL OR id!=?) ORDER BY ts DESC LIMIT 1",
                (window_id, base, except_id, except_id)).fetchone()
        return dict(r) if r else None

    def delete_meal(self, meal_id: int) -> bool:
        with self.tx() as c:
            cur = c.execute("DELETE FROM meals WHERE id=?", (int(meal_id),))
            return cur.rowcount > 0

    def reset_demo_data(self, window_id: Optional[int] = None) -> None:
        """Wipe all demo log data (readings, meals, raw/outbound, audit,
        webhook events, avoid list). Patients, caregivers and windows survive
        so the demo restarts logging fresh on the same patient.

        When a window_id is given only that window's rows are removed.
        """
        with self.tx() as c:
            if window_id:
                for t in ("meals", "readings", "raw_inbound", "outbound"):
                    c.execute(f"DELETE FROM {t} WHERE window_id=?", (window_id,))
                # audit / webhook_events / avoid_items are global (no window_id).
                c.execute("DELETE FROM webhook_events")
                c.execute("DELETE FROM avoid_items")
                c.execute("DELETE FROM audit")
                return
            for t in ("meals", "readings", "raw_inbound", "outbound", "audit",
                      "webhook_events", "avoid_items"):
                c.execute(f"DELETE FROM {t}")

    # ---- readings ------------------------------------------------------
    def add_reading(self, window_id: int, sender_phone: str, role: str,
                    tag: str, value: float, ts: Optional[str] = None,
                    status: str = "confirmed",
                    candidates_json: Optional[str] = None,
                    raw_id: Optional[int] = None,
                    reading_type: Optional[str] = None) -> int:
        reading_type = reading_type if reading_type else _type_from_tag(tag)
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO readings(window_id, ts, sender_phone, role, tag, value,"
                " status, candidates_json, raw_id, reading_type)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (window_id, ts or iso_now(), sender_phone, role, tag, value,
                 status, candidates_json, raw_id, reading_type))
            return cur.lastrowid

    def readings_for_window(self, window_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM readings WHERE window_id=? ORDER BY ts",
            (window_id,)).fetchall()
        return [dict(r) for r in rows]

    def recent_reading(self, sender_phone: str,
                       window_id: Optional[int] = None,
                       since_min: float = 45) -> Optional[dict]:
        """Most recent reading from a sender (default: logged within ~45 min)."""
        try:
            since = (now_local() - timedelta(minutes=since_min)).strftime(
                "%Y-%m-%dT%H:%M:%S")
        except Exception:
            since = iso_now()
        q = ("SELECT * FROM readings WHERE sender_phone=? AND ts>=? "
             + ("AND window_id=? " if window_id else "")
             + "ORDER BY ts DESC LIMIT 1")
        args = [sender_phone, since]
        if window_id:
            args.append(window_id)
        r = self.conn.execute(q, tuple(args)).fetchone()
        return dict(r) if r else None

    def pending_reading_near(self, sender_phone: str,
                             window_id: Optional[int] = None) -> Optional[dict]:
        """Latest status='pending' reading (awaits the patient's confirmation)."""
        q = ("SELECT * FROM readings WHERE sender_phone=? AND status='pending' "
             + ("AND window_id=? " if window_id else "")
             + "ORDER BY ts DESC LIMIT 1")
        args = [sender_phone]
        if window_id:
            args.append(window_id)
        r = self.conn.execute(q, tuple(args)).fetchone()
        return dict(r) if r else None

    def set_reading_tag(self, reading_id: int, tag: str,
                        reading_type: Optional[str] = None) -> None:
        rt = reading_type if reading_type else _type_from_tag(tag)
        with self.tx() as c:
            c.execute("UPDATE readings SET tag=?, reading_type=? WHERE id=?",
                      (tag, rt, int(reading_id)))

    def resolve_reading(self, reading_id: int, value: float,
                        tag: Optional[str] = None) -> None:
        """Confirm an ambiguous (pending) reading to its real value."""
        with self.tx() as c:
            if tag:
                rt = _type_from_tag(tag)
                c.execute("UPDATE readings SET status='confirmed', value=?, tag=?,"
                          " reading_type=?, candidates_json=NULL WHERE id=?",
                          (float(value), tag, rt, int(reading_id)))
            else:
                c.execute("UPDATE readings SET status='confirmed', value=?,"
                          " candidates_json=NULL WHERE id=?",
                          (float(value), int(reading_id)))

    def update_reading(self, reading_id: int, value: Optional[float] = None,
                       tag: Optional[str] = None, ts: Optional[str] = None,
                       status: Optional[str] = None,
                       reading_type: Optional[str] = None) -> bool:
        """Edit a logged reading (operator/doctor edit or AI correction)."""
        sets: list[str] = []
        args: list = []
        updates: list[tuple[str, object]] = []
        if value is not None:
            updates.append(("value", value))
        if tag is not None:
            updates.append(("tag", tag))
        if ts is not None:
            updates.append(("ts", ts))
        if status is not None:
            updates.append(("status", status))
        if reading_type is not None:
            updates.append(("reading_type", reading_type))
        elif tag is not None:
            updates.append(("reading_type", _type_from_tag(tag)))
        if not updates:
            return False
        for col, val in updates:
            sets.append(f"{col}=?")
            args.append(val)
        args.append(int(reading_id))
        with self.tx() as c:
            cur = c.execute(f"UPDATE readings SET {', '.join(sets)} WHERE id=?",
                            tuple(args))
            return cur.rowcount > 0

    def delete_reading(self, reading_id: int) -> bool:
        with self.tx() as c:
            cur = c.execute("DELETE FROM readings WHERE id=?", (int(reading_id),))
            return cur.rowcount > 0

    # ---- outbound (what we said; nudge idempotency) --------------------
    def record_outbound(self, window_id: Optional[int], route: str, kind: str,
                        body: str, unique_key: Optional[str] = None) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO outbound(window_id, ts, route, kind, body, unique_key)"
                " VALUES(?,?,?,?,?,?)",
                (window_id, iso_now(), route, kind, body, unique_key))

    def has_outbound_key(self, unique_key: str) -> bool:
        r = self.conn.execute("SELECT id FROM outbound WHERE unique_key=?", (unique_key,)).fetchone()
        return r is not None

    def outbound_log(self, window_id: Optional[int] = None) -> list[dict]:
        q = "SELECT * FROM outbound"
        args: tuple = ()
        if window_id is not None:
            q += " WHERE window_id=?"
            args = (window_id,)
        q += " ORDER BY ts"
        return [dict(r) for r in self.conn.execute(q, args).fetchall()]

    # ---- audit ---------------------------------------------------------
    def audit(self, actor: str, action: str, detail: str = "") -> None:
        with self.tx() as c:
            c.execute("INSERT INTO audit(ts, actor, action, detail) VALUES(?,?,?,?)",
                      (iso_now(), actor, action, detail))

    def audit_log(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT 200").fetchall()
        return [dict(r) for r in rows]

    # ---- webhook events (durable across redeploys / multi-worker) -------
    def record_webhook_event(self, event_type: str, client_ip: str,
                             status: str, detail: dict) -> int:
        """Persist a Meta webhook event (GET verify / POST inbound) so the
        dashboard counter and diagnostics survive every redeploy / restart.
        """
        import json as _json
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO webhook_events(ts, event_type, client_ip, status, detail)"
                " VALUES(?,?,?,?,?)",
                (iso_now(), event_type or "", client_ip or "",
                 status or "", _json.dumps(detail or {}, ensure_ascii=False)))
            return cur.lastrowid

    def recent_webhook_events(self, limit: int = 30) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM webhook_events ORDER BY id DESC LIMIT ?",
            (max(1, limit),)).fetchall()
        return [dict(r) for r in rows]

    def webhook_event_count(self) -> int:
        r = self.conn.execute("SELECT COUNT(*) AS c FROM webhook_events").fetchone()
        return int(r["c"] or 0)

    # ---- raw inbound (unaltered audit of all patient speech/text) -------
    def record_raw_inbound(self, window_id: Optional[int], sender_phone: str,
                           role: str, raw_text: str, refined_json: str = "",
                           status: str = "received", ts: Optional[str] = None) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO raw_inbound(window_id, ts, sender_phone, role, raw_text, refined_json, status)"
                " VALUES(?,?,?,?,?,?,?)",
                (window_id, ts or iso_now(), sender_phone or "", role or "patient",
                 raw_text or "", refined_json or "", status))
            return cur.lastrowid

    def record_raw_received(self, sender_phone: str, raw_text: str,
                            message_id: str = "", role: str = "patient",
                            ts: Optional[str] = None) -> tuple[int, bool]:
        """Persist a webhook message BEFORE any processing (store-first, durable).

        Returns (raw_inbound.id, is_duplicate). A non-empty Meta message id is used
        for idempotency so redelivered webhooks can never double-process.
        """
        mid = str(message_id or "").strip()
        if mid:
            r = self.conn.execute("SELECT id FROM raw_inbound WHERE message_id=?",
                                  (mid,)).fetchone()
            if r:
                return r["id"], True
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO raw_inbound(window_id, ts, sender_phone, role, raw_text, refined_json, status, message_id)"
                " VALUES(NULL,?,?,?,?,?,?,?)",
                (ts or iso_now(), sender_phone or "", role or "patient",
                 raw_text or "", "", "received", mid))
            return cur.lastrowid, False

    def mark_raw_processed(self, raw_id: int, window_id: Optional[int],
                           role: str, status: str = "processed") -> None:
        """Attach resolution/outcome to an already-captured raw message (in place)."""
        with self.tx() as c:
            c.execute("UPDATE raw_inbound SET window_id=?, role=?, status=? WHERE id=?",
                      (window_id, role or "patient", status or "processed", int(raw_id)))

    def raw_inbound_log(self, window_id: Optional[int] = None,
                        sender_phone: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM raw_inbound"
        args: list = []
        if window_id is not None:
            q += " WHERE window_id=?"
            args.append(window_id)
        q += " ORDER BY id ASC LIMIT 250"
        rows = [dict(r) for r in self.conn.execute(q, tuple(args)).fetchall()]
        if sender_phone:
            clean = re.sub(r"\D", "", str(sender_phone))
            if clean:
                # Fetch newest unlinked messages first
                unlinked = [dict(r) for r in self.conn.execute(
                    "SELECT * FROM raw_inbound WHERE window_id IS NULL ORDER BY id DESC LIMIT 100").fetchall()]
                unlinked.reverse()
                for u in unlinked:
                    u_clean = re.sub(r"\D", "", str(u.get("sender_phone") or ""))
                    if u_clean == clean or (len(clean) >= 10 and len(u_clean) >= 10 and clean[-10:] == u_clean[-10:]):
                        if not any(r["id"] == u["id"] for r in rows):
                            rows.append(u)
                rows.sort(key=lambda x: x.get("id", 0))
        return rows

    def raw_inbound_all(self, limit: int = 50) -> list[dict]:
        """Fetch the most recent inbound messages across all senders for live doctor visibility."""
        rows = [dict(r) for r in self.conn.execute(
            "SELECT * FROM raw_inbound ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
        rows.reverse()
        return rows