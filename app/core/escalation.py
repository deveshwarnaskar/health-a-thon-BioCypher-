"""Operational nudges — the ~9 PM 'anything missing today?' check.

Safety constraints baked in:
  * at most ONE nudge per window-day (idempotent, via a unique outbound key)
  * routed to the caregiver first, patient as fallback
  * purely operational wording: no numbers, no consequences, no advice
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..config import Settings
from .datamodel import Store
from .process import IngestService


def due_escalations(store: Store, cfg: Settings, now: Optional[datetime] = None) -> list[dict]:
    """Return escalation messages that should be sent right now.

    Each item: {"window_id", "to_phone", "route", "body", "unique_key"}.
    """
    now = now or datetime.now()
    if now.hour < cfg.esc_hour:
        return []
    today = now.date()
    out = []
    for w in store.list_windows():
        if w["status"] != "open":
            continue
        if not (w["start_date"] <= today.isoformat() <= w["end_date"]):
            continue
        meals = store.meals_for_window(w["id"], confirmed_only=False)
        readings = [r for r in store.readings_for_window(w["id"])
                    if r.get("status", "confirmed") != "pending"]
        has_meal = any(r["ts"][:10] == today.isoformat() for r in meals)
        has_reading = any(r["ts"][:10] == today.isoformat() for r in readings)
        if has_meal and has_reading:
            continue

        uid = f"esc-{w['id']}-{today.isoformat()}"
        if store.has_outbound_key(uid):
            continue

        patient = store.get_patient(w["patient_id"])
        cg = store.get_caregiver(w["patient_id"])
        cg_phone = (cg or {}).get("phone")
        p_phone = (patient or {}).get("phone")
        target = cg_phone or p_phone
        route = "caregiver" if (target and target == cg_phone) else "patient"
        if not target:
            continue

        missing = []
        if not has_meal:
            missing.append("meal photo")
        if not has_reading:
            missing.append("reading")
        body = ("Just a quick check: today's {0} hasn't come in yet. "
                "Whenever you can, a photo and a reading are enough. No need to reply "
                "to this message.").format(" and ".join(missing))
        out.append({"window_id": w["id"], "to_phone": target, "route": route,
                    "body": body, "unique_key": uid})
    return out