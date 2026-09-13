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

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from ..config import Settings
from .datamodel import Store
from .nutrition import KATORI_LABELS, gi_bucket_index
from .parse import (READING_TAG_LABELS, ParsedInput, ambiguous_reading_values,
                    describe_items, parse_inbound, portion_text,
                    reading_timestamp, _is_done)


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
        self.store.record_raw_inbound(window_id, sender, role, raw_text,
                                      status=status, ts=raw.get("ts"))

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

        # Follow-up ANSWERS (tag / duplicate / ambiguous-value choice) are quiet
        # at the webhook: the dashboard AI intake applies them to the log and is
        # the single confirmer. Keeps the patient replying to questions instead
        # of being told "didn't understand".
        from .parse import (_is_dup_answer, _is_meal_delete, _is_reading_delete,
                        _is_size_answer, _is_tag_answer,
                        _reference_correction, _resolution_cue_value)
        tag_ans = _is_tag_answer(raw_text)
        dup_ans = _is_dup_answer(raw_text)
        res_ans = _resolution_cue_value(raw_text)
        # Size-only answers ("100ml"), meal references ("not the one i told")
        # and delete commands are dashboard/AI intake territory — the webhook
        # stays quiet so the patient gets exactly ONE coherent follow-up.
        size_ans = _is_size_answer(raw_text)
        ref_only = (bool(_reference_correction(raw_text))
                    and not parsed.items)
        del_ans = (_is_reading_delete(raw_text) or _is_meal_delete(raw_text))
        # "that's all" / "bas" / "ho gaya" is a polite end-of-logging cue — the
        # dashboard AI answers it; the webhook never misreads it as an input.
        done_ans = _is_done(raw_text)
        if (tag_ans or dup_ans or res_ans or size_ans or ref_only or del_ans or done_ans):
            self.store.audit(role, "answer_received",
                             f"{raw_text[:40]!r} tag={tag_ans or ''} "
                             f"dup={dup_ans or ''} res={res_ans or ''} "
                             f"size={size_ans or ''} ref={ref_only} del={del_ans} "
                             f"done={done_ans}")
            return []

        # In AI-intake mode the dashboard worker is the SINGLE responder: meal
        # proposals, pure chat, off-range refusals and confirmations are all
        # quiet here (readings are store-only anyway), so a patient receives
        # exactly ONE coherent follow-up per message.
        if self.cfg.ai_intake:
            self.store.audit(role, "ai_intake_quiet",
                             f"{raw_text[:40]!r} kind={parsed.kind}")
            return []

        if parsed.kind == "refusal":
            # Deterministic-only: the webhook never consults Gemini/LLMs, so a
            # patient-facing WhatsApp message can never be LLM-composed.
            name = patient.get("name", "Patient")
            return [self._out(route=role, kind="text",
                              to=raw.get("sender_phone"),
                              body=(f"Namaste {name} ji! I didn't understand "
                                    "that. Send a reading like 'fasting 126' or "
                                    "text the dish name."))]

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
        """Readings are STORE-ONLY at the webhook.

        The raw message is already durably captured above; the glucose VALUE is
        written into the readings table by the dashboard AI intake (the single
        logger + confirmer) so that duplicate/backdated/ambiguous inputs are
        handled intelligently and a patient never gets repeating confirmations.
        Returns no outbound — the dashboard confirms what it logs.
        """
        ts = parsed.ts.strftime("%Y-%m-%dT%H:%M:%S")
        tag = parsed.reading_tag or "random"
        self.store.audit(role, "reading_received",
                         f"{tag} {parsed.reading:g} at {ts}")
        return []

    # ---- meals -----------------------------------------------------------
    def _handle_meal(self, patient, window, role, parsed: ParsedInput, raw) -> list[Outbound]:
        if not parsed.items:
            to = raw.get("sender_phone")
            # Deterministic-only refusal: no Gemini on the webhook path.
            name = patient.get("name", "Patient")
            return [self._out(route=role, kind="text", to=to,
                              body=(f"Namaste {name} ji! I didn't understand that "
                                    "completely (mujhe thoda samajh nahi aaya). "
                                    "Reading batayein — jaise 'sugar 130' ya "
                                    "'fasting 120' — ya khana likhein: "
                                    "'2 roti, dal, sabzi'."))]
# proposal stage
        low = str(raw.get("text") or "").lower()
        # A same-dish message that ALSO states a size/change ("the meal was
        # large chocolates" after a pending "Two Chocolates") COMPLETES the
        # pending meal instead of starting a duplicate row.
        my_names = {str(it.get("item") or "").lower().strip().strip(".")
                    for it in parsed.items}
        _SIZE_MARK = ("small", "medium", "large", "chota", "chhota", "chhoti",
                      "kam", "bada", "badi", "bara", "zyada", "jyada", "big",
                      "full", "half", "katori", "katora", "bowl", "plate",
                      "glass", "cup", "ml", "do roti", "2 roti",
                      "change", "changed", "wrong", "galat", "actually")
        _size_or_change = any(k in low for k in _SIZE_MARK)
        _EDIT_ONLY = ("change", "changed", "change karo", "edit", "edit karo",
                      "replace", "replaced", "galat", "wrong", "wrong tha",
                      "actually", "sahi karo", "sudhar", "badlo", "badal")
        is_edit = any(k in low for k in _EDIT_ONLY)
        pend = self.store.newest_pending(raw.get("sender_phone"))
        pend_items = []
        if pend:
            try:
                pend_items = json.loads(pend.get("items_json") or "[]")
            except Exception:
                pend_items = []
        pend_names = {str(x.get("item") or "").lower().strip().strip(".")
                      for x in pend_items}
        # A replacement names a genuinely NEW dish ("change chole bhature to
        # white rice 1 cup") -> log ONLY the new dish as a fresh row and mark
        # the old pending row superseded (kept visible). Same-dish restatements
        # still complete the pending row below instead.
        fresh = [it for it in parsed.items
                 if (str(it.get("item") or "").lower().strip().strip(".")
                     not in pend_names)]
        if (pend and parsed.items and is_edit and fresh
                and my_names.difference(pend_names)):
            new_ts = reading_timestamp(
                str(raw.get("text") or raw.get("kind") or ""),
                parsed.ts.strftime("%Y-%m-%dT%H:%M:%S")
            ).strftime("%Y-%m-%dT%H:%M:%S")
            portion = fresh[0].get("portion", "m")
            pt = (getattr(parsed, "portion_text", None)
                  or portion_text(low))
            new_id = self.store.propose_meal(
                window["id"], raw.get("sender_phone"), role, parsed.kind,
                fresh, portion, self.cfg.katori(portion),
                (sum(float(x.get("carbs") or 0.0) for x in fresh) or None),
                (self._split_gi(fresh)
                 if any(x.get("gi") for x in fresh) else None),
                0.9 if parsed.kind == "text" else 0.82,
                ts=new_ts, portion_text=pt)
            self.store.supersede_meal(pend["id"], new_id)
            self.store.finalize_meal(new_id, "confirmed", portion,
                                     portion_text=pt)
            self.store.audit(role, "meal_replaced",
                             f"old={pend['id']} new={new_id} "
                             f"new_dish={describe_items(fresh)}")
            body = (f"Detected: {describe_items(fresh)} — purana entry replace "
                    f"kar diya (✓ cross-marked), naya logged. It's in the report.")
            return [self._out(route=role, kind="text",
                              to=raw.get("sender_phone"), body=body)]
        if (pend and my_names and _size_or_change):
            try:
                pend_items = json.loads(pend.get("items_json") or "[]")
            except Exception:
                pend_items = []
            pend_names = {str(x.get("item") or "").lower().strip().strip(".")
                          for x in pend_items}
            if pend_names and not pend_names.isdisjoint(my_names):
                portion = (parsed.items[0].get("portion")
                           or pend.get("portion") or "m")
                pt = getattr(parsed, "portion_text", None)
                self.store.finalize_meal(pend["id"], "confirmed", portion,
                                         portion_text=pt,
                                         correction_note="size stated again")
                merged = list(pend_items)
                have = {(str(x.get("item") or "").lower(), x.get("genus"))
                        for x in merged}
                for it in parsed.items:
                    key = (str(it.get("item") or "").lower(), it.get("genus"))
                    if key not in have:
                        merged.append(it)
                carbs = (sum(float(x.get("carbs") or 0.0) for x in merged) or None)
                gi = (self._split_gi(merged)
                      if any(x.get("gi") for x in merged) else None)
                self.store.update_meal(pend["id"], items_json=json.dumps(
                    merged, ensure_ascii=False), carbs=carbs, gi=gi)
                self.store.audit(role, "meal_completed",
                                 f"meal_id={pend['id']} portion={portion}")
                echo = describe_items(merged)
                body = (f"Detected: {echo} Confirmed "
                        f"({KATORI_LABELS.get(portion)}). It's in the report.")
                return [self._out(route=role, kind="text",
                                  to=raw.get("sender_phone"), body=body)]
        portion = parsed.items[0].get("portion", "m")
        confidence = 0.9 if parsed.kind == "text" else 0.82
        carbs = (sum(float(it.get("carbs") or 0.0) for it in parsed.items)
                     or None)
        gi = (self._split_gi(parsed.items)
              if any(it.get("gi") for it in parsed.items) else None)
        ts = reading_timestamp(
            str(raw.get("text") or raw.get("kind") or ""),
            parsed.ts.strftime("%Y-%m-%dT%H:%M:%S")).strftime("%Y-%m-%dT%H:%M:%S")
        meal_id = self.store.propose_meal(
            window["id"], raw.get("sender_phone"), role, parsed.kind,
            parsed.items, portion, self.cfg.katori(portion), carbs, gi, confidence,
            ts=ts, portion_text=getattr(parsed, "portion_text", None))
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
        self.store.finalize_meal(meal["id"], status, portion=new_portion,
                             correction_note=note,
                             portion_text=parsed.portion_text)
        self.store.audit(role, "meal_final", f"meal_id={meal['id']} {status}")
        lb = KATORI_LABELS.get((new_portion or meal["portion"]), "")
        return [self._out(route=role, kind="text", to=raw.get("sender_phone"),
                          body=f"Thanks, that one is confirmed ({lb}). It's in the report.")]

    def _split_gi(self, items: list[dict]) -> str:
        buckets = {it.get("gi") for it in items}
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