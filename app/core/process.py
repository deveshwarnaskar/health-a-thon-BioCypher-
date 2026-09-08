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

        patient = self.store.get_patient(raw.get("patient_id"))
        if not patient:
            return [self._out(route="patient", kind="text", to=raw.get("sender_phone"),
                              body="We could not find that profile. Please contact the clinic.")]

        window = self.store.active_window_for(patient["id"])
        if not window:
            if parsed.kind == "refusal":
                return []
            return [self._out(route="patient", kind="text", to=raw.get("sender_phone"),
                              body="You do not have an active logging window right now. "
                                   "It opens around your next visit.")]

        role, allowed = self._role(patient, window, raw.get("sender_phone"))
        if not allowed:
            return [self._out(route="patient", kind="text", to=raw.get("sender_phone"),
                              body="Please ask the clinic to link your number to a patient. "
                                   "To protect patient data, only the patient and their "
                                   "designated caregiver can log entries.")]

        if parsed.kind == "refusal":
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

    # ---- routing helpers ----------------------------------------------
    def _role(self, patient: dict, window: dict, phone: Optional[str]) -> tuple[str, bool]:
        if not phone:
            return "patient", False
        phone = phone.strip()
        if phone == str(patient["phone"]).strip():
            return "patient", True
        cg = self.store.get_caregiver(patient["id"])
        if cg and phone == str(cg["phone"]).strip():
            return "caregiver", True
        bound = (window.get("caregiver_phone") or "").strip()
        if bound and phone == bound:
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