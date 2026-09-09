"""Deterministic demo seeding — one patient + caregiver + an open window.

Phone numbers are *operator data*, never baked into the code: defaults read
AAHAAR_DEMO_PHONE / AAHAAR_DEMO_CAREGIVER (falling back to demo placeholders)
and a re-seed never overwrites numbers the operator already linked.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from ..config import Settings
from .datamodel import Store

_DEFAULT_PATIENT_PHONE = os.environ.get("AAHAAR_DEMO_PHONE", "+919876501234")
_DEFAULT_CAREGIVER_PHONE = os.environ.get("AAHAAR_DEMO_CAREGIVER", "+919876505678")


def seed_demo(store: Store, cfg: Settings, days: int = 14,
              name: str = "Sunita Devi", uh_id: str = "AH-2026-0042",
              phone: Optional[str] = None,
              caregiver_phone: Optional[str] = None) -> tuple[int, int]:
    phone = (phone or _DEFAULT_PATIENT_PHONE).strip()
    caregiver_phone = (caregiver_phone or _DEFAULT_CAREGIVER_PHONE).strip()
    today = date.today()
    start = today - timedelta(days=days - 1)
    existing = store.get_patient_by_uh(uh_id)
    if existing:
        # operator-linked numbers win over any env default on re-seed
        pid = existing["id"]
        phone = existing["phone"]
        cg = store.get_caregiver(pid)
        caregiver_phone = (cg or {}).get("phone") or caregiver_phone
    else:
        pid = store.add_patient(name, uh_id, phone)
        store.set_caregiver(pid, caregiver_phone, "Anil Kumar (son)")
        store.set_avoid_items(pid, "Dr. S. Sharma", ["soft drink", "gulab jamun", "sweet juice"])
    wid = store.open_window(pid, start.isoformat(), today.isoformat(),
                            caregiver_phone=caregiver_phone)
    store.audit("system", "seed", f"demo window {wid}")
    return pid, wid