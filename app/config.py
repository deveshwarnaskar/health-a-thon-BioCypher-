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


def _env_float(key: str, default: str) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return float(default)


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
    whatsapp: str = _env("AAHAAR_WHATSAPP", "simulator")
    # operator key guarding clinic-side number linking (env AAHAAR_OP_KEY)
    operator_key: str = _env("AAHAAR_OP_KEY", "aahaar-2026")
    # allow LLM/Gemini on the live inbound path (env AAHAAR_AI_ON_INBOUND).
    # Default OFF: the webhook stores raw patient input and replies via the
    # deterministic local refiner; Gemini analysis runs only offline afterwards.
    ai_on_inbound: bool = _env("AAHAAR_AI_ON_INBOUND", "").strip().lower() in ("1", "true", "on", "yes")

    # AI intake notifier (env AAHAAR_AI_INTAKE). Default OFF. When on, a small
    # background worker polls STORED raw_inbound rows (never the webhook), runs
    # the intake notifier, and sends follow-up questions through the same
    # outbound channel the doctor composer uses. Same run is available on demand
    # from the dashboard without this flag (POST /api/v1/analyze/stored).
    ai_intake: bool = _env("AAHAAR_AI_INTAKE", "").strip().lower() in ("1", "true", "on", "yes")
    ai_intake_interval: float = _env_float("AAHAAR_AI_INTAKE_INTERVAL", "15")
    # Background worker is analyze-only by default; follow-ups are released
    # from the dashboard ("Send follow-up via WhatsApp" checkbox / send=true).
    ai_intake_auto_send: bool = _env("AAHAAR_AI_INTAKE_AUTO_SEND", "").strip().lower() in ("1", "true", "on", "yes")
    # Short pacing gap between sequential WhatsApp follow-ups (one at a time).
    ai_intake_send_gap: float = _env_float("AAHAAR_AI_INTAKE_SEND_GAP", "0.5")

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