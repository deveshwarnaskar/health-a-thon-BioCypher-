"""Seed the demo patient against YOUR real WhatsApp number for the Phase 5 live test.

Run the server afterwards with the cloud channel (see docs/WHATSAPP_DEMO.md for the
click-by-click Meta walkthrough).

Usage:
    python3 -m scripts.seed_real --phone +9198XXXXXXX [--window 14] [--db aahaar-demo.db]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import Settings
from app.core.datamodel import Store
from app.core.seed import seed_demo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phone", required=True,
                    help="your real WhatsApp number, international format, e.g. +919812345678")
    ap.add_argument("--window", "--days", dest="days", type=int, default=14)
    ap.add_argument("--db", default="aahaar-demo.db")
    args = ap.parse_args()

    if os.path.exists(args.db):
        os.remove(args.db)
    store = Store(args.db)
    pid, wid = seed_demo(store, Settings(db_path=args.db), days=args.days,
                         phone=args.phone, caregiver_phone=args.phone)
    print(f"Patient {pid}, window {wid}: 'patient' phone = {args.phone} (same number is caregiver)")
    print(f"Now run the server with AAHAAR_WHATSAPP=cloud and a fresh META_TOKEN "
          f"(walkthrough: docs/WHATSAPP_DEMO.md).")
    store.close()


if __name__ == "__main__":
    main()