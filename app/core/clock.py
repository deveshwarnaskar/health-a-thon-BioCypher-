"""Clock helpers — the demo runs on Asia/Kolkata (IST) patient time.

Every timestamp in the store is a NAIVE string like '2026-09-12T07:05:00'
expressed in IST. Storing IST-naive (instead of UTC) keeps day grouping,
Morning/Afternoon/Evening slots and the patient-visible message times all
consistent, and matches the times patients actually report.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))


def now_local() -> datetime:
    """Current Asia/Kolkata time as a naive datetime (matching stored ts)."""
    return datetime.now(IST).replace(tzinfo=None)


def iso_now() -> str:
    return now_local().strftime("%Y-%m-%dT%H:%M:%S")


_MONTH_FMT = ["jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec"]


def fmt_ts_log(ts_s: Optional[str], now: Optional[datetime] = None) -> str:
    """'07:05' for today, '14 jul 07:05' for any other day.

    Uses the same IST-naive clock as the whole store, so a backdated reading
    confirms with the date the patient meant, not only the time.
    """
    s = str(ts_s or "")
    if len(s) < 16:
        return s
    hm = s[11:16]
    now = now or now_local()
    if s[:10] == now.strftime("%Y-%m-%d"):
        return hm
    try:
        d = datetime.strptime(s[:10], "%Y-%m-%d")
        return f"{d.day} {_MONTH_FMT[d.month - 1]} {hm}"
    except ValueError:
        return f"{s[:10]} {hm}"