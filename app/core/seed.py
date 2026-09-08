"""Deterministic demo seeding — one patient + caregiver + an open window."""
from __future__ import annotations

from datetime import date, timedelta

from ..config import Settings
from .datamodel import Store


def seed_demo(store: Store, cfg: Settings, days: int = 14,
              name: str = "Sunita Devi", uh_id: str = "AH-2026-0042",
              phone: str = "+91 98XXXXXXXX", caregiver_phone: str = "+91 99XXXXXXXX") -> tuple[int, int]:
    today = date.today()
    start = today - timedelta(days=days - 1)
    pid = store.add_patient(name, uh_id, phone)
    store.set_caregiver(pid, caregiver_phone, "Anil Kumar (son)")
    store.set_avoid_items(pid, "Dr. S. Sharma", ["soft drink", "gulab jamun", "sweet juice"])
    wid = store.open_window(pid, start.isoformat(), today.isoformat(),
                            caregiver_phone=caregiver_phone)
    store.audit("system", "seed", f"demo window {wid}")
    return pid, wid