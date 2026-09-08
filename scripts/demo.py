"""Usage:

    python -m scripts.demo            # 14-day simulated window + report
    python -m scripts.demo --days 7
    python -m scripts.demo --desktop  # also copy the PDF to the Windows Desktop

Drives the REAL pipeline end-to-end: seed -> simulate patient & caregiver
logging through the confirm loop -> metrics -> 2-page PDF report.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.core.datamodel import Store
from app.core.metrics import compute_window_metrics
from app.core.process import IngestService
from app.core.report import build_report_context
from app.core.seed import seed_demo
from app.report import charts as report_charts
from app.report import pdf as report_pdf
from app.server.whatsapp import SimulatorBackend

PATIENT_PHONE = "+919876501234"
CAREGIVER_PHONE = "+919876505678"

WEEKDAY_MEAL = "2 roti, dal, mixed sabzi"
WEEKEND_MEAL = "white rice, biryani, sweet juice"
FESTIVE_MEAL = "paratha, gulab jamun, soft drink"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--db", default=None)
    ap.add_argument("--desktop", action="store_true")
    args = ap.parse_args()

    days = min(max(args.days, 2), 21)
    today = date.today()
    db_path = args.db or "aahaar-demo.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    cfg = Settings(db_path=db_path, report_dir="reports")
    store = Store(db_path)
    ingest = IngestService(store, cfg)
    backend = SimulatorBackend(store, cfg)

    pid, wid = seed_demo(store, cfg, days=days,
                         phone=PATIENT_PHONE, caregiver_phone=CAREGIVER_PHONE)
    window = store.get_window(wid)
    start = date.fromisoformat(window["start_date"])
    end = date.fromisoformat(window["end_date"])

    rng = random.Random(2026)
    print(f"Demo patient {pid} · window {start} → {end}")

    day = start
    i = 0
    while day <= end and day <= today:
        festive = (i == 6) or (i == 12)
        weekend = day.weekday() >= 5
        missed_day = day.day in (3, 10)  # creates a sub-100% adherence
        sender = CAREGIVER_PHONE if (i % 3 == 0) else PATIENT_PHONE

        if not missed_day:
            meal_txt = FESTIVE_MEAL if festive else (WEEKEND_MEAL if weekend else WEEKDAY_MEAL)
            _send(ingest, backend, pid, sender, {"kind": "text", "text": meal_txt,
                                                 "ts": _ts(day, 9, 0)})
            _send(ingest, backend, pid, sender, {"kind": "text", "text": "yes",
                                                 "ts": _ts(day, 9, 1)})
            _send(ingest, backend, pid, sender, {"kind": "text",
                                                 "text": f"fasting {_fpg(rng, weekend, festive)}",
                                                 "ts": _ts(day, 7, 15)})
            _send(ingest, backend, pid, sender,
                  {"kind": "text", "text": f"post {_ppbg(rng, weekend, festive)}",
                   "ts": _ts(day, 14, 0)})
        day += timedelta(days=1)
        i += 1

    store.audit("system", "demo_windows_closed", "demo log finished")
    store.close_window(wid)

    metrics = compute_window_metrics(store, cfg, wid)
    ctx = build_report_context(store, cfg, wid)
    os.makedirs(cfg.report_dir, exist_ok=True)
    top, bottom = report_charts.render(ctx, cfg.report_dir)
    pdf_path = report_pdf.render(ctx, cfg.report_dir, top, bottom)

    print("\n— metrics —", json.dumps({
        "meals": metrics["meals_count"], "readings": metrics["readings_count"],
        "adherence": metrics["adherence_index"],
        "mean_fpg": metrics["mean_fpg"], "mean_ppbg": metrics["mean_ppbg"],
        "tir": metrics["tir"],
        "weekday_ppbg": metrics["weekday_ppbg"], "weekend_ppbg": metrics["weekend_ppbg"],
        "high_gi_share": metrics["high_gi_share"],
        "carb_volatility": metrics["carb_volatility"],
        "avoid": metrics["avoid_count"],
    }, indent=2))
    print("\nReport PDF:", pdf_path)

    if args.desktop:
        dest = "/mnt/c/Users/DELL/Desktop"
        if os.path.isdir(dest):
            shutil.copy(pdf_path, os.path.join(dest, "Aahaar-Doctor-Report-demo.pdf"))
            print("Copied to Desktop: Aahaar-Doctor-Report-demo.pdf")

    store.close()


def _ts(day: date, h: int, m: int) -> str:
    return datetime.combine(day, datetime.min.time().replace(hour=h, minute=m)).isoformat()


def _fpg(rng, weekend, festive):
    base = 178 if festive else (136 if weekend else 126)
    return max(95, round(base + rng.gauss(0, 7)))


def _ppbg(rng, weekend, festive):
    base = 238 if festive else (198 if weekend else 158)
    return max(120, round(base + rng.gauss(0, 10)))


def _send(ingest, backend, pid, sender, raw) -> None:
    for reply in ingest.handle({**{"patient_id": pid, "sender_phone": sender}, **raw}):
        backend.send(reply)


if __name__ == "__main__":
    main()