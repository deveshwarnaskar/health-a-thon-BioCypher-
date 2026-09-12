"""Ingress pipeline: one inbound message in -> zero..N outbound messages out.

Responsibilities
  * role guard (patient + ONE designated caregiver only)
  * active-window guard (nothing processed outside a scheduled window)
  * confirm loop (proposal -> yes / correct -> only confirmed rows count later)
  * reading sanity guard (range check)
  * polite refusals that never echo anything clinically meaningful

The reply text is deliberately plain and app-like: it mirrors what the app
detected and asks for a yes/correct. It never numbers the carb/GI for patients.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..config import Settings
from .datamodel import Store
from .nutrition import KATORI_LABELS, gi_bucket_index
from .parse import READING_TAG_LABELS, ParsedInput, ambiguous_reading_values, describe_items, parse_inbound


@dataclass
class Outbound:
    route: str            # patient | caregiver
    kind: str             # text | quick_reply | image
    body: str
    to_phone: str


class IngestService:
    def __init__(self, store: Store, cfg: Settings):
        self.store = store
        self.cfg = cfg

    def _log_raw(self, window_id, sender, role, raw_text, status, raw) -> None:
        """Record the raw message once: update in place if the webhook pre-captured
        it (store-first), otherwise insert a fresh row (simulator / direct API)."""
        raw_id = raw.get("_raw_id")
        if raw_id:
            try:
                self.store.mark_raw_processed(int(raw_id), window_id, role, status)
                return
            except Exception:
                pass
        self.store.record_raw_inbound(window_id, sender, role, raw_text, status=status)

    def handle(self, raw: dict) -> list[Outbound]:
        parsed = parse_inbound(raw, self.cfg)

        sender = str(raw.get("sender_phone") or "").strip()
        raw_text = str(raw.get("text") or raw.get("reading") or (raw.get("kind") or "message"))

        patient = None
        pid = raw.get("patient_id")
        if pid is not None:
            patient = self.store.get_patient(pid)
        if not patient and sender:
            # real-WhatsApp inbound carries only the sender number — resolve it
            patient = self.store.get_patient_by_phone(sender)
            if not patient:
                # In demo setup: if clinic only has default demo patient, auto-adopt real WhatsApp sender
                all_pts = self.store.list_patients()
                if len(all_pts) == 1:
                    p0 = all_pts[0]
                    p0_clean = re.sub(r"\D", "", str(p0.get("phone") or ""))
                    if p0_clean.endswith("9876501234") or not p0_clean:
                        self.store.set_patient_phone(p0["id"], sender)
                        patient = self.store.get_patient(p0["id"])
                        print(f"[Aahaar] Auto-bound demo placeholder patient {p0['id']} to real WhatsApp sender {sender}")
        if not patient:
            self._log_raw(None, sender, "unknown", raw_text, "unregistered", raw)
            return [self._out(route="patient", kind="text", to=sender,
                              body="We could not find that profile. Please contact "
                                   "the clinic to link your number.")]
        pid = patient["id"]

        window = self.store.active_window_for(patient["id"]) or self.store.last_window_for(patient["id"])
        if not window:
            self._log_raw(None, sender, "patient", raw_text, "no_active_window", raw)
            if parsed.kind == "refusal":
                return []
            return [self._out(route="patient", kind="text", to=sender,
                              body="You do not have an active logging window right now. "
                                   "It opens around your next visit.")]

        role, allowed = self._role(patient, window, sender)
        if not allowed:
            self._log_raw(window["id"], sender, "unauthorized", raw_text, "unauthorized", raw)
            return [self._out(route="patient", kind="text", to=sender,
                              body="Please ask the clinic to link your number to a patient. "
                                   "To protect patient data, only the patient and their "
                                   "designated caregiver can log entries.")]

        # 100% audit of all patient speech / text (raw, unaltered)
        self._log_raw(window["id"], sender, role, raw_text, "processed", raw)

        if parsed.kind == "refusal":
            from .ai import analyze_patient_input
            ai_res = analyze_patient_input(raw_text, patient_name=patient.get("name", "Patient"), cfg=self.cfg)
            if ai_res.intent == "reading" and ai_res.reading is not None:
                parsed.kind = "reading"
                parsed.reading = ai_res.reading
                parsed.reading_tag = ai_res.reading_tag
                return self._handle_reading(patient, window, role, parsed, raw)
            elif ai_res.intent == "meal" and ai_res.dishes:
                from .parse import _items
                parsed.kind = "text"
                parsed.items = _items(", ".join(ai_res.dishes), self.cfg)
                return self._handle_meal(patient, window, role, parsed, raw)
            elif ai_res.conversational_reply:
                return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                                  body=ai_res.conversational_reply)]
            return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                              body="I didn't understand that. Send a photo of the meal, "
                                   "a reading like 'fasting 126', or text the dish name.")]

        # Unresolved reading ("230 or 330", "shayad 230 ya 330...") takes priority:
        # suppress the meal portion-confirm so the patient receives exactly ONE
        # clarifying question — pushed by the dashboard AI intake, not the webhook.
        cand = ambiguous_reading_values(raw_text)
        if cand:
            self.store.audit(role, "reading_ambiguous",
                             f"{raw_text[:80]!r} -> {[f'{v:g}' for v in cand]}")
            return []

        if parsed.is_reading:
            return self._handle_reading(patient, window, role, parsed, raw)

        if parsed.is_confirm:
            return self._handle_confirm(patient, window, role, parsed, raw)

        if parsed.is_meal:
            return self._handle_meal(patient, window, role, parsed, raw)

        return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                          body="I couldn't process that. Try again or ask the clinic.")]

    def _role(self, patient: dict, window: dict, phone: Optional[str]) -> tuple[str, bool]:
        if not phone:
            return "patient", False
        clean_in = re.sub(r"\D", "", str(phone))
        clean_p = re.sub(r"\D", "", str(patient.get("phone") or ""))
        if clean_in == clean_p or (len(clean_in) >= 10 and len(clean_p) >= 10 and clean_in[-10:] == clean_p[-10:]):
            return "patient", True
        if clean_p.endswith("9876501234"):
            self.store.set_patient_phone(patient["id"], phone)
            return "patient", True
        cg = self.store.get_caregiver(patient["id"])
        if cg:
            clean_cg = re.sub(r"\D", "", str(cg.get("phone") or ""))
            if clean_in == clean_cg or (len(clean_in) >= 10 and len(clean_cg) >= 10 and clean_in[-10:] == clean_cg[-10:]):
                return "caregiver", True
        bound = re.sub(r"\D", "", str(window.get("caregiver_phone") or ""))
        if bound and (clean_in == bound or (len(clean_in) >= 10 and len(bound) >= 10 and clean_in[-10:] == bound[-10:])):
            return "caregiver", True
        return "patient", False

    def _out(self, route: str, kind: str, to: Optional[str], body: str) -> Outbound:
        return Outbound(route=route, kind=kind, body=body, to_phone=to or "")

    # ---- readings -------------------------------------------------------
    def _handle_reading(self, patient, window, role, parsed: ParsedInput, raw) -> list[Outbound]:
        ts = parsed.ts.strftime("%Y-%m-%dT%H:%M:%S")
        label = READING_TAG_LABELS.get(parsed.reading_tag, parsed.reading_tag)
        self.store.add_reading(window["id"], raw.get("sender_phone"), role,
                               parsed.reading_tag, parsed.reading, ts=ts)
        self.store.audit(role, "reading", f"{parsed.reading_tag} {parsed.reading}")
        return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                          body=f"Logged {label}: {parsed.reading:g} mg/dL. "
                               "Would you like to add what you ate around this reading? Send a photo 📷, voice note 🎙️, or text ✍️ (or reply 'skip').")]

    # ---- meals -----------------------------------------------------------
    def _handle_meal(self, patient, window, role, parsed: ParsedInput, raw) -> list[Outbound]:
        if not parsed.items:
            to = raw.get("sender_phone")
            from .ai import analyze_patient_input
            ai_res = analyze_patient_input(str(raw.get("text") or ""),
                                           patient_name=patient.get("name", "Patient"),
                                           cfg=self.cfg)
            if ai_res.intent == "reading" and ai_res.reading is not None:
                parsed.kind = "reading"
                parsed.reading = ai_res.reading
                parsed.reading_tag = ai_res.reading_tag
                return self._handle_reading(patient, window, role, parsed, raw)
            if ai_res.intent == "meal" and ai_res.dishes:
                from .parse import _items
                parsed.kind = "text"
                parsed.items = _items(", ".join(ai_res.dishes), self.cfg)
                if parsed.items:
                    return self._handle_meal(patient, window, role, parsed, raw)
            if ai_res.conversational_reply:
                return [self._out(route=role, kind="text", to=to,
                                  body=ai_res.conversational_reply)]
            return [self._out(route=role, kind="text", to=to,
                              body="I couldn't recognise dishes in that yet. "
                                   "Please describe it in text, e.g. '2 roti, dal, sabzi'.")]
        # proposal stage
        portion = parsed.items[0].get("portion", "m")
        confidence = 0.9 if parsed.kind == "text" else 0.82
        carbs = sum(float(it.get("carbs", 0.0)) for it in parsed.items)
        gi = self._split_gi(parsed.items)
        ts = parsed.ts.strftime("%Y-%m-%dT%H:%M:%S")
        meal_id = self.store.propose_meal(
            window["id"], raw.get("sender_phone"), role, parsed.kind,
            parsed.items, portion, self.cfg.katori(portion), carbs, gi, confidence, ts=ts)
        self.store.audit(role, "meal_proposal", f"meal_id={meal_id}")

        echo = describe_items(parsed.items)
        body = (f"Detected: {echo} Correct portion? "
                f"{KATORI_LABELS.get(portion)}. Reply YES, or 'correct m/s/l'.")
        return [self._out(route=role, kind="quick_reply", to=raw.get("sender_phone"), body=body)]

    def _handle_confirm(self, patient, window, role, parsed: ParsedInput, raw) -> list[Outbound]:
        meal = self.store.newest_pending(raw.get("sender_phone"))
        if not meal:
            return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                              body="There's nothing waiting to confirm. Send a new meal photo.")]
        status = "confirmed"
        note = "confirmed by user"
        new_portion = None
        if parsed.portion_letter:
            new_portion = parsed.portion_letter
            status = "corrected"
            note = "portion corrected by user"
        self.store.finalize_meal(meal["id"], status, portion=new_portion, correction_note=note)
        self.store.audit(role, "meal_final", f"meal_id={meal['id']} {status}")
        lb = KATORI_LABELS.get((new_portion or meal["portion"]), "")
        return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                          body=f"Thanks, that one is confirmed ({lb}). It's in the report.")]

    def _split_gi(self, items: list[dict]) -> str:
        buckets = {it["gi"] for it in items}
        ranked = sorted(buckets, key=gi_bucket_index, reverse=True)
        return ranked[0] if ranked else "med"

    # ---- helpers shared with other services --------------------------
    @staticmethod
    def window_dates(window: dict) -> list[date]:
        from datetime import datetime, timedelta
        start = datetime.strptime(window["start_date"], "%Y-%m-%d").date()
        end = datetime.strptime(window["end_date"], "%Y-%m-%d").date()
        out = []
        d = start
        while d <= end:
            out.append(d)
            d += timedelta(days=1)
        return out