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
from .parse import READING_TAG_LABELS, ParsedInput, describe_items, parse_inbound


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
            self.store.record_raw_inbound(
                None, sender, "unknown", raw_text, status="unregistered"
            )
            return [self._out(route="patient", kind="text", to=sender,
                              body="We could not find that profile. Please contact "
                                   "the clinic to link your number.")]
        pid = patient["id"]

        window = self.store.active_window_for(patient["id"]) or self.store.last_window_for(patient["id"])
        if not window:
            self.store.record_raw_inbound(
                None, sender, "patient", raw_text, status="no_active_window"
            )
            if parsed.kind == "refusal":
                return []
            return [self._out(route="patient", kind="text", to=sender,
                              body="You do not have an active logging window right now. "
                                   "It opens around your next visit.")]

        role, allowed = self._role(patient, window, sender)
        if not allowed:
            self.store.record_raw_inbound(
                window["id"], sender, "unauthorized", raw_text, status="unauthorized"
            )
            return [self._out(route="patient", kind="text", to=sender,
                              body="Please ask the clinic to link your number to a patient. "
                                   "To protect patient data, only the patient and their "
                                   "designated caregiver can log entries.")]

        # 100% audit of all patient speech / text (raw, unaltered)
        self.store.record_raw_inbound(
            window["id"], sender, role, raw_text, status="processed"
        )

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
                               "This goes into the doctor's report.")]

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