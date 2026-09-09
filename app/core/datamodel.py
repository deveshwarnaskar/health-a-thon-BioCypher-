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
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Iterator, Optional

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

CREATE INDEX IF NOT EXISTS ix_meals_window ON meals(window_id);
CREATE INDEX IF NOT EXISTS ix_readings_window ON readings(window_id);
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
        self.conn.executescript(SCHEMA)
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
        r = self.conn.execute("SELECT * FROM patients WHERE phone=? AND is_active=1",
                              (phone,)).fetchone()
        return dict(r) if r else None

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
                (patient_id, phone, name, iso(datetime.now())))
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
                          (patient_id, set_by, it.strip(), iso(datetime.now())))

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
                (patient_id, start_date, end_date, caregiver_phone, iso(datetime.now())))
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
                     ts: Optional[str] = None) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO meals(window_id, ts, sender_phone, role, source, status, items_json,"
                " portion, portion_ml, carbs, gi, confidence)"
                " VALUES(?,?,?,?,?, 'pending', ?,?,?,?,?,?)",
                (window_id, ts or iso(datetime.now()), sender_phone, role, source,
                 json.dumps(items, ensure_ascii=False), portion, portion_ml, carbs, gi, confidence))
            return cur.lastrowid

    def mark_pending_stale(self, sender_phone: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE meals SET status='pending' WHERE sender_phone=? AND status='pending'",
                      (sender_phone,))

    def newest_pending(self, sender_phone: str) -> Optional[dict]:
        r = self.conn.execute(
            "SELECT * FROM meals WHERE sender_phone=? AND status='pending' "
            "ORDER BY ts DESC LIMIT 1", (sender_phone,)).fetchone()
        return dict(r) if r else None

    def finalize_meal(self, meal_id: int, status: str, portion: Optional[str] = None,
                      correction_note: Optional[str] = None) -> None:
        meal = self.conn.execute("SELECT * FROM meals WHERE id=?", (meal_id,)).fetchone()
        if not meal:
            return
        with self.tx() as c:
            if portion:
                c.execute("UPDATE meals SET status=?, portion=?, correction_note=? WHERE id=?",
                          (status, portion, correction_note or portion, meal_id))
            else:
                c.execute("UPDATE meals SET status=?, correction_note=? WHERE id=?",
                          (status, correction_note, meal_id))

    def meals_for_window(self, window_id: int, confirmed_only: bool = True) -> list[dict]:
        q = ("SELECT * FROM meals WHERE window_id=? "
             + ("AND status IN ('confirmed','corrected') " if confirmed_only else "")
             + "ORDER BY ts")
        return [dict(r) for r in self.conn.execute(q, (window_id,)).fetchall()]

    # ---- readings ------------------------------------------------------
    def add_reading(self, window_id: int, sender_phone: str, role: str,
                    tag: str, value: float, ts: Optional[str] = None) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO readings(window_id, ts, sender_phone, role, tag, value)"
                " VALUES(?,?,?,?,?,?)",
                (window_id, ts or iso(datetime.now()), sender_phone, role, tag, value))
            return cur.lastrowid

    def readings_for_window(self, window_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM readings WHERE window_id=? ORDER BY ts",
            (window_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---- outbound (what we said; nudge idempotency) --------------------
    def record_outbound(self, window_id: Optional[int], route: str, kind: str,
                        body: str, unique_key: Optional[str] = None) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO outbound(window_id, ts, route, kind, body, unique_key)"
                " VALUES(?,?,?,?,?,?)",
                (window_id, iso(datetime.now()), route, kind, body, unique_key))

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
                      (iso(datetime.now()), actor, action, detail))

    def audit_log(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT 200").fetchall()
        return [dict(r) for r in rows]