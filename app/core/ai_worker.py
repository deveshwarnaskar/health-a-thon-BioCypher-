"""Decoupled AI intake worker.

Polls raw_inbound rows that have not yet been analysed by the intake notifier.
For each stored row it writes `refined_json` and, when a follow-up is actually
needed, sends a short notifier question through the SAME outbound channel the
doctor composer uses (backend.send).

It is an independent consumer of the database: it never reads from or writes to
the Meta webhook request cycle, so enabling or disabling it cannot affect the
store-first webhook architecture. The same analysis is also available on demand
from the dashboard (POST /api/v1/analyze/stored).

Auto-start is opt-in via AAHAAR_AI_INTAKE=on (default off). The dashboard
trigger works even when the worker is off.
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

    def run_once(self, limit: int = 10, should_send: bool = True) -> dict:
        """Analyze stored (not yet refined) rows; send follow-ups when needed."""
        summary = {"analyzed": 0, "sent": 0, "skipped": 0}
        try:
            rows = self.store.raw_inbound_all(limit=1000)
        except Exception as e:
            print(f"[Aahaar] AI intake worker DB read error: {e}")
            return summary
        pending = [r for r in rows
                   if (r.get("raw_text") or "") and not (r.get("refined_json") or "")]
        pending.sort(key=lambda r: r.get("id") or 0)
        for r in pending[:max(1, int(limit))]:
            sender = str(r.get("sender_phone") or "").strip()
            try:
                patient = self.store.get_patient_by_phone(sender) if sender else None
                res = analyze_intake(r["raw_text"],
                                     patient_name=patient["name"] if patient else "Patient",
                                     cfg=self.cfg)
                self._save_refined(r["id"], res)
                summary["analyzed"] += 1
            except Exception as e:
                print(f"[Aahaar] AI intake worker analyze error (raw_id={r.get('id')}): {e}")
                summary["skipped"] += 1
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
                    try:
                        self.store.audit("ai_intake", "followup_sent",
                                         f"raw_id={r['id']}")
                    except Exception:
                        pass
                else:
                    summary["skipped"] += 1

        self.last_run = datetime.now().isoformat()
        self.last_summary = summary
        return summary

    def _save_refined(self, raw_id: int, res: IntakeResult) -> None:
        payload = {
            "intent": res.intent,
            "missing": res.missing,
            "reply": res.reply,
            "should_reply": res.should_reply,
            "confidence": res.confidence,
            "analyzed_by": res.analyzed_by,
        }
        with self.store.tx() as c:
            c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                      (json.dumps(payload, ensure_ascii=False), int(raw_id)))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _loop() -> None:
            while not self._stop.is_set():
                try:
                    self.run_once()
                except Exception as e:
                    print(f"[Aahaar] AI intake worker loop error: {e}")
                self._stop.wait(self.interval)

        self._thread = threading.Thread(target=_loop, name="aahaar-ai-intake",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()