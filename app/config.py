"""Central configuration for the Aahaar prototype.

All behaviour-switch flags live here so the demo, tests and the server can be
run with different plug-ins (mock vision, mock channel, real channel) without
touching the pipeline code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    # --- target range for time-in-range -------------------------------
    glucose_low: float = 70.0
    glucose_high: float = 180.0

    # --- calibrated katori portions (ml) -------------------------------
    katori_ml: tuple[float, float, float] = (150.0, 220.0, 350.0)

    # --- plug-in switches ----------------------------------------------
    mock_vision: bool = True     # when a real model isn't plugged in
    # channel backend: "simulator" | "cloud"
    whatsapp: str = "simulator"

    # --- physical paths ------------------------------------------------
    db_path: str = _env("AAHAAR_DB", "aahaar.db")
    static_dir: str = os.path.join(os.path.dirname(__file__), "static")
    report_dir: str = "reports"

    # --- operational nudges --------------------------------------------
    esc_hour: int = 21            # 9 PM missed-logging escalation
    esc_max_per_day: int = 1      # never nudge more than once a day
    window_lens_days: tuple[int, ...] = (7, 14, 21)

    def katori(self, letter: str) -> float:
        idx = {"s": 0, "m": 1, "l": 2}.get((letter or "m").strip().lower(), 1)
        return self.katori_ml[idx]


def get_settings() -> Settings:
    return Settings()