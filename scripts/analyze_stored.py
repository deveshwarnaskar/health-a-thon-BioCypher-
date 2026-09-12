"""Offline analysis of stored patient input (never runs inside the webhook).

The live WhatsApp/webhook path only stores raw patient input and replies with
the deterministic local refiner. This script runs the deep LLM (Gemini) over
already-captured messages in a batch and writes the refined interpretation back
into raw_inbound.refined_json — analysis happens here, later, not live.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.core.datamodel import Store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Offline Gemini analysis of stored raw inbound messages")
    ap.add_argument("--db", default=None, help="path to the SQLite DB (default: AAHAAR_DB env or aahaar.db)")
    ap.add_argument("--limit", type=int, default=200, help="max messages to analyze (default 200)")
    ap.add_argument("--dry-run", action="store_true", help="only list what would be analyzed, change nothing")
    ap.add_argument("--force", action="store_true", help="re-analyze messages that already have refined_json")
    args = ap.parse_args()

    cfg = Settings(db_path=args.db or Settings().db_path)
    if not cfg.ai_on_inbound:
        print("NOTE: AAHAAR_AI_ON_INBOUND is off; this script is the only place the LLM runs by design.")
    if not __import__("os").environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set — analysis will use the local refiner only.")
        return 2

    store = Store(cfg.db_path)
    from app.core.ai import analyze_patient_input

    rows = store.raw_inbound_all(limit=500)
    pending = []
    for r in rows:
        if not r.get("raw_text"):
            continue
        if bool(r.get("refined_json")) and not args.force:
            continue
        pending.append(r)
        if len(pending) >= args.limit:
            break

    print(f"Analyzing {len(pending)} stored messages (dry_run={args.dry_run})...")
    done = 0
    for r in pending:
        res = analyze_patient_input(str(r["raw_text"]),
                                    patient_name="Patient",
                                    cfg=cfg,
                                    force=True)
        payload = {
            "intent": res.intent,
            "confidence": res.confidence,
            "reading": res.reading,
            "reading_tag": res.reading_tag,
            "dishes": res.dishes,
            "conversational_reply": res.conversational_reply,
            "clarification_question": res.clarification_question,
            "analyzed_by": "gemini" if bool(__import__("os").environ.get("GEMINI_API_KEY")) else "local-refiner",
        }
        if args.dry_run:
            print(f"  [{r['id']}] {str(r['raw_text'])[:40]!r} -> {res.intent}")
            continue
        with store.tx() as c:
            c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                      (json.dumps(payload, ensure_ascii=False), r["id"]))
        done += 1
        print(f"  [{r['id']}] {str(r['raw_text'])[:40]!r} -> {res.intent}")
    print(f"Updated {done} rows.")
    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())