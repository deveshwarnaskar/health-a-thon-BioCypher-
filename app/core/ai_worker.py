"""Decoupled AI intake worker.

Polls raw_inbound rows that have not yet been analysed by the intake notifier.
For each stored row it writes `refined_json` (intent, missing fields, the
suggested follow-up). Follow-up WhatsApp questions are NOT auto-sent: they are
released only from the dashboard (POST /api/v1/analyze/stored with send=true,
or the "Send follow-up via WhatsApp" checkbox). Sends go through the SAME
outbound channel the doctor composer uses (backend.send), one at a time with a
short pacing gap.

It is an independent consumer of the database: it never reads from or writes to
the Meta webhook request cycle, so enabling or disabling it cannot affect the
store-first webhook architecture. The same analysis is also available on demand
from the dashboard (POST /api/v1/analyze/stored).

Auto-start is opt-in via AAHAAR_AI_INTAKE=on (default off). The dashboard
trigger works even when the worker is off. Setting AAHAAR_AI_INTAKE_AUTO_SEND=on
(e.g. a lab/hackathon demo) makes the worker release follow-ups automatically.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Callable, Optional

from ..config import Settings
from .datamodel import Store
from .intake_ai import IntakeResult, analyze_intake
from .parse import PATIENT_TAG_LABELS, _is_dup_answer, _tag_from_text


class IntakeWorker:
    def __init__(self, store: Store, cfg: Settings, send_func: Callable,
                 interval: float = 15.0):
        self.store = store
        self.cfg = cfg
        self.send = send_func
        self.interval = max(5.0, float(interval))
        self.last_run: Optional[str] = None
        self.last_summary: dict = {"analyzed": 0, "sent": 0, "skipped": 0}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def run_once(self, limit: int = 10, should_send: bool = False,
                 send_gap: float = 0.5) -> dict:
        """Analyze stored rows; send a follow-up only when explicitly asked.

        Analyze-only (the default) never touches WhatsApp. When should_send is
        true, messages that still need a follow-up (should_reply and not yet
        sent) are released one at a time with `send_gap` seconds between them.
        """
        import time
        summary = {"analyzed": 0, "sent": 0, "skipped": 0}
        try:
            rows = self.store.raw_inbound_all(limit=1000)
        except Exception as e:
            print(f"[Aahaar] AI intake worker DB read error: {e}")
            return summary
        pending = self._pending_rows(rows)
        for r in pending[:max(1, int(limit))]:
            sender = str(r.get("sender_phone") or "").strip()
            try:
                fj = r.get("refined_json") or ""
                if fj:
                    res = self._from_stored(r["raw_text"], fj)
                else:
                    patient = self.store.get_patient_by_phone(sender) if sender else None
                    res = analyze_intake(r["raw_text"],
                                         patient_name=patient["name"] if patient else "Patient",
                                         cfg=self.cfg,
                                         msg_ts=str(r.get("ts") or ""))
                    self._save_refined(r["id"], res, followup_sent=False)
                    summary["analyzed"] += 1
            except Exception as e:
                print(f"[Aahaar] AI intake worker analyze error (raw_id={r.get('id')}): {e}")
                summary["skipped"] += 1
                continue

            self._maybe_register(r, res, sender)
            self._maybe_register_meal(r, res, sender)

            if res.should_reply and not res.reply:
                self._save_refined(r["id"], res, followup_sent=True)
                continue

            if res.should_reply and res.reply and sender and should_send:
                try:
                    from ..core.process import Outbound
                    ok = bool(self.send(Outbound(route="patient", kind="text",
                                                 body=res.reply, to_phone=sender)))
                except Exception as e:
                    print(f"[Aahaar] AI intake worker send error: {e}")
                    ok = False
                if ok:
                    summary["sent"] += 1
                    self._save_refined(r["id"], res, followup_sent=True)
                    try:
                        self.store.audit("ai_intake", "followup_sent",
                                         f"raw_id={r['id']}")
                    except Exception:
                        pass
                    time.sleep(max(0.0, float(send_gap)))
                else:
                    summary["skipped"] += 1

        self.last_run = datetime.now().isoformat()
        self.last_summary = summary
        return summary

    def _pending_rows(self, rows: list[dict]) -> list[dict]:
        """Rows still worth a visit: never analysed, or analysed but still
        waiting for their follow-up to be released."""
        pending = []
        for r in rows:
            raw = r.get("raw_text") or ""
            if not raw:
                continue
            fj = r.get("refined_json") or ""
            if not fj:
                pending.append(r)
                continue
            try:
                parsed = json.loads(fj)
            except Exception:
                pending.append(r)
                continue
            if parsed.get("should_reply") and not parsed.get("followup_sent"):
                pending.append(r)
        pending.sort(key=lambda r: r.get("id") or 0)
        return pending

    def _from_stored(self, raw_text: str, fj: str) -> IntakeResult:
        parsed = json.loads(fj)
        return IntakeResult(
            intent=parsed.get("intent", "unknown"),
            missing=list(parsed.get("missing") or []),
            reply=parsed.get("reply", ""),
            should_reply=bool(parsed.get("should_reply")),
            raw_text=raw_text,
            confidence=float(parsed.get("confidence") or 0.0),
            analyzed_by=parsed.get("analyzed_by", "stored"),
            reading_value=parsed.get("reading_value"),
            reading_tag=parsed.get("reading_tag"),
            reading_candidates=list(parsed.get("reading_candidates") or []),
            reading_status=parsed.get("reading_status", "none"),
            reading_ts=parsed.get("reading_ts"),
            meal_items=list(parsed.get("meal_items") or []),
            meal_portion=parsed.get("meal_portion"),
        )

    def _save_refined(self, raw_id: int, res: IntakeResult,
                      followup_sent: bool = False,
                      registered: bool = False) -> None:
        prev_registered = prev_meal_registered = False
        dup_pending = None
        try:
            row = self.store.conn.execute(
                "SELECT refined_json FROM raw_inbound WHERE id=?",
                (int(raw_id),)).fetchone()
            if row and row["refined_json"]:
                prev = json.loads(row["refined_json"])
                prev_registered = bool(prev.get("registered"))
                prev_meal_registered = bool(prev.get("meal_registered"))
                dup_pending = prev.get("dup_pending")
        except Exception:
            pass
        payload = {
            "intent": res.intent,
            "missing": res.missing,
            "reply": res.reply,
            "should_reply": res.should_reply,
            "confidence": res.confidence,
            "analyzed_by": res.analyzed_by,
            "followup_sent": bool(followup_sent),
            "reading_value": res.reading_value,
            "reading_tag": res.reading_tag,
            "reading_candidates": list(res.reading_candidates or []),
            "reading_status": res.reading_status,
            "reading_ts": res.reading_ts,
            "meal_items": list(res.meal_items or []),
            "meal_portion": res.meal_portion,
            "registered": bool(prev_registered) or bool(registered),
            "meal_registered": bool(prev_meal_registered),
        }
        if dup_pending is not None:
            payload["dup_pending"] = dup_pending
        with self.store.tx() as c:
            c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                      (json.dumps(payload, ensure_ascii=False), int(raw_id)))

    def _maybe_register(self, raw_row: dict, res: IntakeResult, sender: str) -> None:
        """Write the AI-decided reading into the readings table (window-scoped).

        Off-webhook and dashboard-driven. Handles:
          * tag answers   -> apply the reading-context tag in place;
          * dup answers   -> "new" registers the earlier blocked value, otherwise skip;
          * resolutions   -> confirm an ambiguous (pending) reading to its true value;
          * ambiguous     -> keep a status='pending' row (never guess a number);
          * single value  -> confirm it (same-day duplicates ask instead of re-logging).
        Never duplicated — guarded by the row marker and by an existing-reading check.
        """
        try:
            if not sender:
                return
            patient = self.store.get_patient_by_phone(sender)
            if not patient:
                return
            window = (self.store.active_window_for(patient["id"])
                      or self.store.last_window_for(patient["id"]))
            if not window or not window.get("id"):
                return
            wid = window["id"]
            intent = res.intent

            # same-row idempotency
            fj = raw_row.get("refined_json") or ""
            if fj:
                try:
                    if json.loads(fj).get("registered"):
                        return
                except Exception:
                    pass

            if intent == "tag_answer":
                tag = _tag_from_text(res.raw_text) or "postprandial"
                pend = self.store.pending_reading_near(sender, wid)
                rows = sorted((r for r in self.store.readings_for_window(wid)
                               if r.get("sender_phone") == sender
                               and r.get("status") == "confirmed"),
                              key=lambda r: r.get("ts") or "", reverse=True)
                target = pend or (rows[0] if rows else None)
                if target:
                    self.store.set_reading_tag(target["id"], tag)
                    self.store.audit("ai_intake", "reading_tagged",
                                     f"raw_id={raw_row['id']} reading={target['id']} "
                                     f"({'pending ' if pend else ''}{tag})")
                self._mark_registered(raw_row["id"])
                return

            if intent == "dup_answer":
                ans = _is_dup_answer(res.raw_text)
                dup = self._find_dup_pending(sender)
                if ans == "new" and dup:
                    v = float(dup["value"])
                    ts = str(dup.get("ts") or self._now_iso())
                    self.store.add_reading(wid, sender, "patient", "postprandial", v, ts=ts)
                    self.store.audit("ai_intake", "reading_registered",
                                     f"raw_id={raw_row['id']} confirmed-dup {v:g} at {ts}")
                    res.reply = self._confirm_reading(v, None, ts)
                    res.should_reply = True
                    res.missing = []
                else:
                    self.store.audit("ai_intake", "duplicate_skipped",
                                     f"raw_id={raw_row['id']} ans={ans or ''}")
                    res.reply = ""
                    res.should_reply = False
                self._mark_registered(raw_row["id"])
                return

            if intent == "resolution" and res.reading_value is not None:
                v = float(res.reading_value)
                ts = res.reading_ts or self._now_iso()
                pend = self.store.pending_reading_near(sender, wid)
                if pend:
                    self.store.resolve_reading(pend["id"], v)
                    self.store.audit("ai_intake", "reading_resolved",
                                     f"raw_id={raw_row['id']} reading={pend['id']} -> {v:g}")
                    res.reply = self._confirm_reading(v, pend.get("tag"), ts)
                else:
                    self.store.add_reading(wid, sender, "patient", "postprandial", v, ts=ts)
                    self.store.audit("ai_intake", "reading_registered",
                                     f"raw_id={raw_row['id']} {v:g} at {ts}")
                    res.reply = self._confirm_reading(v, None, ts)
                res.should_reply = True
                res.missing = []
                self._mark_registered(raw_row["id"])
                return

            if intent == "reading" and res.reading_status == "ambiguous" and res.reading_candidates:
                cand = sorted(float(x) for x in res.reading_candidates)
                existing = self.store.pending_reading_near(sender, wid)
                if existing and existing.get("candidates_json"):
                    try:
                        if sorted(float(x) for x in
                                  json.loads(existing["candidates_json"])) == cand:
                            self._mark_registered(raw_row["id"])
                            return
                    except Exception:
                        pass
                ts = res.reading_ts or self._now_iso()
                self.store.add_reading(wid, sender, "patient", "postprandial",
                                       cand[0] if cand else 0.0,
                                       ts=ts, status="pending",
                                       candidates_json=json.dumps(cand),
                                       raw_id=int(raw_row["id"]))
                self.store.audit("ai_intake", "reading_pending",
                                 f"raw_id={raw_row['id']} candidates={cand}")
                self._mark_registered(raw_row["id"])
                return

            if res.reading_status == "resolved" and res.reading_value is not None:
                v = float(res.reading_value)
                tag = res.reading_tag or "postprandial"
                ts = res.reading_ts or self._now_iso()
                target_day = (ts or "")[:10]
                dup = None
                for rd in self.store.readings_for_window(wid):
                    if (rd.get("sender_phone") == sender
                            and rd.get("status") == "confirmed"
                            and str(rd.get("ts") or "")[:10] == target_day):
                        try:
                            if abs(float(rd.get("value") or 0.0) - v) < 0.5:
                                dup = rd
                                break
                        except (TypeError, ValueError):
                            continue
                if dup:
                    self.store.audit("ai_intake", "duplicate_asked",
                                     f"raw_id={raw_row['id']} value={v:g} "
                                     f"matches reading {dup['id']}")
                    name = (patient.get("name") or "ji").strip() or "ji"
                    res.reply = (f"{name} ji, sugar {v:g} is already logged for "
                                 f"{self._hm(ts)} — naya hai ya mistake? ('naya' / 'mistake')")
                    res.should_reply = True
                    res.missing = ["duplicate"]
                    self._store_dup_pending(raw_row["id"], v, ts)
                    self._mark_registered(raw_row["id"])
                    return
                self.store.add_reading(wid, sender, "patient", tag, v, ts=ts)
                self.store.audit("ai_intake", "reading_registered",
                                 f"raw_id={raw_row['id']} {tag} {v:g} at {ts}")
                self._mark_registered(raw_row["id"])
                return
        except Exception as e:
            print(f"[Aahaar] AI intake register error: {e}")

    @staticmethod
    def _hm(ts_s: Optional[str]) -> str:
        s = str(ts_s or "")
        return s[11:16] if len(s) >= 16 else s

    def _confirm_reading(self, value: float, tag: Optional[str], ts_s: Optional[str]) -> str:
        hm = self._hm(ts_s)
        if tag:
            label = PATIENT_TAG_LABELS.get(tag, tag)
            return f"✅ Logged sugar {value:g} ({label}) — {hm}."
        return f"✅ Logged sugar {value:g} — {hm}. Ye fasting thi ya khane ke baad?"

    def _store_dup_pending(self, raw_id: int, value: float, ts: Optional[str]) -> None:
        try:
            with self.store.tx() as c:
                row = c.execute("SELECT refined_json FROM raw_inbound WHERE id=?",
                                (int(raw_id),)).fetchone()
                if not row or not row["refined_json"]:
                    return
                p = json.loads(row["refined_json"])
                p["dup_pending"] = {"value": float(value), "ts": str(ts or "")}
                c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                          (json.dumps(p, ensure_ascii=False), int(raw_id)))
        except Exception as e:
            print(f"[Aahaar] AI intake store dup-pending error: {e}")

    def _find_dup_pending(self, sender: str) -> Optional[dict]:
        try:
            for r in self.store.raw_inbound_all(limit=1000):
                if str(r.get("sender_phone") or "") != sender:
                    continue
                fj = r.get("refined_json") or ""
                if not fj:
                    continue
                p = json.loads(fj)
                d = p.get("dup_pending")
                if isinstance(d, dict) and d.get("value") is not None:
                    return d
        except Exception as e:
            print(f"[Aahaar] AI intake find dup-pending error: {e}")
        return None

    def _mark_registered(self, raw_id: int) -> None:
        self._mark_flag(raw_id, "registered")

    def _maybe_register_meal(self, raw_row: dict, res: IntakeResult,
                             sender: str) -> None:
        """Store the AI-recognized MEAL into the meals table (window-scoped).

        Off-webhook and dashboard-driven, like the reading registration.
        Only registers when dishes were actually recognized. Never duplicated:
        guarded by the row marker AND by dedup against a meal the deterministic
        webhook already proposed for the same dish set (ordinary meal messages
        keep their normal proposal+confirm loop; for ambiguous-reading messages
        the deterministic confirm is suppressed, so this becomes the only
        logger). The message's own timestamp is kept.
        """
        try:
            items = list(res.meal_items or [])
            if not items:
                return
            fj = raw_row.get("refined_json") or ""
            if fj:
                try:
                    if json.loads(fj).get("meal_registered"):
                        return
                except Exception:
                    pass
            if not sender:
                return
            patient = self.store.get_patient_by_phone(sender)
            if not patient:
                return
            window = (self.store.active_window_for(patient["id"])
                      or self.store.last_window_for(patient["id"]))
            if not window or not window.get("id"):
                return
            ts = str(raw_row.get("ts") or self._now_iso())
            want = {(str(it.get("item") or "").lower(), it.get("genus"),
                     it.get("portion") or "m") for it in items}
            if any(self._same_dish_set(m.get("items_json"), want)
                   for m in self.store.meals_for_window(window["id"],
                                                        confirmed_only=False)):
                if res.intent == "meal":
                    res.reply = ""
                    res.should_reply = False
                self._mark_flag(raw_row["id"], "meal_registered")
                return
            portion = res.meal_portion or items[0].get("portion", "m") or "m"
            carbs = sum(float(it.get("carbs", 0.0)) for it in items)
            gi = self._split_gi(items)
            meal_id = self.store.propose_meal(
                window["id"], sender, "patient", "ai",
                items, portion, self.cfg.katori(portion), carbs, gi,
                float(res.confidence), ts=ts)
            names = ", ".join(str(it.get("item") or it) for it in items)
            self.store.audit("ai_intake", "meal_registered",
                             f"raw_id={raw_row['id']} meal_id={meal_id} "
                             f"ts={ts} {names}")
            self._mark_flag(raw_row["id"], "meal_registered")
        except Exception as e:
            print(f"[Aahaar] AI intake meal-register error: {e}")

    def _mark_flag(self, raw_id: int, key: str) -> None:
        try:
            with self.store.tx() as c:
                row = c.execute(
                    "SELECT refined_json FROM raw_inbound WHERE id=?",
                    (int(raw_id),)).fetchone()
                if not row or not row["refined_json"]:
                    return
                p = json.loads(row["refined_json"])
                p[key] = True
                c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                          (json.dumps(p, ensure_ascii=False), int(raw_id)))
        except Exception as e:
            print(f"[Aahaar] AI intake mark-registered error: {e}")

    @staticmethod
    def _split_gi(items: list[dict]) -> str:
        from .nutrition import gi_bucket_index
        buckets = {it.get("gi", "med") for it in items}
        ranked = sorted(buckets, key=gi_bucket_index, reverse=True)
        return ranked[0] if ranked else "med"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _same_dish_set(items_json: Optional[str], want: set) -> bool:
        try:
            have = {(str(x.get("item") or "").lower(), x.get("genus"),
                     x.get("portion") or "m")
                    for x in json.loads(items_json or "[]")}
            return bool(have) and have == want
        except Exception:
            return False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _loop() -> None:
            auto_send = bool(getattr(self.cfg, "ai_intake_auto_send", False))
            send_gap = float(getattr(self.cfg, "ai_intake_send_gap", 0.5))
            while not self._stop.is_set():
                try:
                    self.run_once(limit=10, should_send=auto_send,
                                  send_gap=send_gap)
                except Exception as e:
                    print(f"[Aahaar] AI intake worker loop error: {e}")
                self._stop.wait(self.interval)

        self._thread = threading.Thread(target=_loop, name="aahaar-ai-intake",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()