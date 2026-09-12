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
                                         cfg=self.cfg)
                    self._save_refined(r["id"], res, followup_sent=False)
                    summary["analyzed"] += 1
            except Exception as e:
                print(f"[Aahaar] AI intake worker analyze error (raw_id={r.get('id')}): {e}")
                summary["skipped"] += 1
                continue

            self._maybe_register(r, res, sender)

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
        )

    def _save_refined(self, raw_id: int, res: IntakeResult,
                      followup_sent: bool = False,
                      registered: bool = False) -> None:
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
            "registered": bool(registered),
        }
        with self.store.tx() as c:
            c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                      (json.dumps(payload, ensure_ascii=False), int(raw_id)))

    def _maybe_register(self, raw_row: dict, res: IntakeResult, sender: str) -> None:
        """Store the AI-deduced reading into the readings table (window-scoped).

        Dashboard-driven and off-webhook: only unambiguous (resolved) values are
        ever written; ambiguous ones ("230 or 330") wait for the patient. Never
        duplicated — guarded by the row marker and by an existing-reading check.
        """
        try:
            if res.reading_status != "resolved" or res.reading_value is None:
                return
            fj = raw_row.get("refined_json") or ""
            if fj:
                try:
                    if json.loads(fj).get("registered"):
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
            value = float(res.reading_value)
            tag = res.reading_tag or "postprandial"
            for rd in self.store.readings_for_window(window["id"]):
                try:
                    if abs(float(rd.get("value") or 0.0) - value) < 0.5:
                        self._mark_registered(raw_row["id"])
                        return
                except (TypeError, ValueError):
                    continue
            self.store.add_reading(window["id"], sender, "patient", tag, value)
            self.store.audit("ai_intake", "reading_registered",
                             f"raw_id={raw_row['id']} {tag} {value:g}")
            self._mark_registered(raw_row["id"])
        except Exception as e:
            print(f"[Aahaar] AI intake register error: {e}")

    def _mark_registered(self, raw_id: int) -> None:
        try:
            with self.store.tx() as c:
                row = c.execute(
                    "SELECT refined_json FROM raw_inbound WHERE id=?",
                    (int(raw_id),)).fetchone()
                if not row or not row["refined_json"]:
                    return
                p = json.loads(row["refined_json"])
                p["registered"] = True
                c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                          (json.dumps(p, ensure_ascii=False), int(raw_id)))
        except Exception as e:
            print(f"[Aahaar] AI intake mark-registered error: {e}")

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