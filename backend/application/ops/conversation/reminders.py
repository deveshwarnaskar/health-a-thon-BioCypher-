"""Deterministic reminder policy (spec §13, §28, §29).

The AI layer NEVER decides whether to message a patient. A deterministic
policy decides; the AI may only phrase the message afterwards. This mirrors
and complements the existing ``caregiver_companion`` heuristic (quiet hours
22:00-07:00 IST, cooldown 2.5h, duplicate suppression) with a reusable,
testable policy object the conversational layer can consult before generating
any proactive message.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), name="IST")

DEFAULT_QUIET_START = time(22, 0)
DEFAULT_QUIET_END = time(7, 0)
DEFAULT_COOLDOWN_MINUTES = 150  # 2.5h
MAX_CONSECUTIVE_PROMPTS = 3


def to_ist(dt: datetime) -> datetime:
    """Normalize an aware dt → IST wall clock."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def in_daily_window(
    dt: datetime,
    *,
    start: time = DEFAULT_QUIET_START,
    end: time = DEFAULT_QUIET_END,
) -> bool:
    """True if local ``dt`` falls inside a (possibly wrap-around) nightly window."""
    local = to_ist(dt).time()
    if start <= end:  # same-day window (never used by default)
        return start <= local < end
    # wrap-around window: e.g. 22:00 → 07:00
    return local >= start or local < end


@dataclass(frozen=True)
class QuietDecision:
    allowed: bool
    reason: str


class ReminderPolicy:
    """Pure policy: given a scheduled time + last prompt, may we message the patient?"""

    def __init__(
        self,
        *,
        quiet_start: time = DEFAULT_QUIET_START,
        quiet_end: time = DEFAULT_QUIET_END,
        cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
    ) -> None:
        self._quiet_start = quiet_start
        self._quiet_end = quiet_end
        self._cooldown = timedelta(minutes=cooldown_minutes)

    def allow_auto_prompt(
        self,
        now_utc: datetime,
        last_prompt_utc: datetime | None = None,
    ) -> QuietDecision:
        if in_daily_window(now_utc, start=self._quiet_start, end=self._quiet_end):
            return QuietDecision(
                allowed=False,
                reason=f"quiet_hours {self._quiet_start:%H:%M}-{self._quiet_end:%H:%M} IST",
            )
        if last_prompt_utc is not None:
            last = last_prompt_utc
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if now_utc.tzinfo is None:
                now_utc = now_utc.replace(tzinfo=timezone.utc)
            if now_utc - last < self._cooldown:
                return QuietDecision(
                    allowed=False,
                    reason="within cooldown window",
                )
        return QuietDecision(allowed=True, reason="ok")

    def is_quiet_hour(self, now_utc: datetime) -> bool:
        return in_daily_window(now_utc, start=self._quiet_start, end=self._quiet_end)


__all__ = [
    "IST",
    "ReminderPolicy",
    "QuietDecision",
    "to_ist",
    "in_daily_window",
    "DEFAULT_QUIET_START",
    "DEFAULT_QUIET_END",
]