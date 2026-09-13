"""Decoupled AI intake worker.

Polls raw_inbound rows that have not yet been analysed by the intake notifier.
For each stored row it writes `refined_json` (intent, missing fields, the
suggested follow-up). Follow-up WhatsApp questions are NOT auto-sent: they are
released only from the dashboard (POST /api/v1/analyze/stored with send=true,
or the "Send follow-up via WhatsApp" checkbox). Sends go through the SAME
outbound channel the doctor composer uses (backend.send), one at a time with a
short pacing gap.

It is an independent consumer of the database: it never reads from or writes to
the Meta webhook request cycle, so enabling or disabling it cannot affect the
store-first webhook architecture. The same analysis is also available on demand
from the dashboard (POST /api/v1/analyze/stored).

Auto-start is opt-in via AAHAAR_AI_INTAKE=on (default off). The dashboard
trigger works even when the worker is off. Setting AAHAAR_AI_INTAKE_AUTO_SEND=on
(e.g. a lab/hackathon demo) makes the worker release follow-ups automatically.
"""
from __future__ import annotations

import json
import threading
from typing import Callable, Optional

from ..config import Settings
from .clock import fmt_ts_log, iso_now
from .datamodel import Store
from .intake_ai import (
    IntakeResult,
    _meal_items,
    _portion_stated,
    analyze_intake,
    portion_text,
)
from .parse import (PATIENT_TAG_LABELS, _is_change_text, _is_dup_answer,
                    _is_tag_negation, _tag_from_text, change_old_dish,
                    change_remainder, dish_mentions_phrase)
from .nutrition import KATORI_LABELS

# Threads started by any IntakeWorker.instance anywhere in this process. The
# webhook lane consults worker_active() so it goes store-only whenever a live
# intake worker exists — single responder by construction, no env required.
_worker_threads: set = set()


def worker_active() -> bool:
    return any(t.is_alive() for t in set(_worker_threads))


class IntakeWorker:
    def __init__(self, store: Store, cfg: Settings, send_func: Callable,
                 interval: float = 15.0):
        self.store = store
        self.cfg = cfg
        self.send = send_func
        self.interval = max(5.0, float(interval))
        self.last_run: Optional[str] = None
        self.last_summary: dict = {"analyzed": 0, "sent": 0, "skipped": 0}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def run_once(self, limit: int = 10, should_send: bool = False,
                 send_gap: float = 0.5) -> dict:
        """Analyze stored rows; optionally send one safe follow-up per row.

        Analyze-only (the default) never touches WhatsApp. When should_send is
        true, messages that still need a follow-up (should_reply and not yet
        sent) are released one at a time with `send_gap` seconds between them.
        """
        import time
        summary = {"analyzed": 0, "sent": 0, "skipped": 0}
        try:
            rows = self.store.raw_inbound_all(limit=1000)
        except Exception as e:
            print(f"[Aahaar] AI intake worker DB read error: {e}")
            return summary
        pending = self._pending_rows(rows)
        for r in pending[:max(1, int(limit))]:
            sender = str(r.get("sender_phone") or "").strip()
            try:
                fj = r.get("refined_json") or ""
                if fj:
                    res = self._from_stored(r["raw_text"], fj)
                else:
                    patient = self.store.get_patient_by_phone(sender) if sender else None
                    # This executes after database capture, never in the Meta
                    # webhook request. Gemini (when permitted) reads the stored
                    # message plus this patient's recent-log context and writes
                    # the reply; Gemini failures return None internally and
                    # analyze_intake safely retains the local result.
                    res = analyze_intake(
                        r["raw_text"],
                        patient_name=patient["name"] if patient else "Patient",
                        cfg=self.cfg,
                        msg_ts=str(r.get("ts") or ""),
                        use_llm=bool(getattr(self.cfg, "ai_intake_use_gemini", True)),
                        context=self._build_context(sender, patient),
                    )
                    self._save_refined(r["id"], res, followup_sent=False)
                    summary["analyzed"] += 1
            except Exception as e:
                print(f"[Aahaar] AI intake worker analyze error (raw_id={r.get('id')}): {e}")
                summary["skipped"] += 1
                continue

            gem_text = res.reply
            gem_replied = bool(str(res.analyzed_by or "").startswith("gemini:")
                               and (res.reply or "").strip())
            self._maybe_register(r, res, sender)
            self._maybe_register_meal(r, res, sender)

            # Gemini wrote the reply — the deterministic DB ops above may have
            # overwritten res.reply with their own confirms; Gemini's wording
            # is what the patient gets. Without Gemini the worker's confirm is
            # the safe fallback.
            if gem_replied:
                res.reply = gem_text
                res.should_reply = True

            if res.should_reply and not res.reply:
                self._save_refined(r["id"], res, followup_sent=True)
                continue

            if res.should_reply and res.reply and sender and should_send:
                try:
                    from ..core.process import Outbound
                    ok = bool(self.send(Outbound(route="patient", kind="text",
                                                 body=res.reply, to_phone=sender)))
                except Exception as e:
                    print(f"[Aahaar] AI intake worker send error: {e}")
                    ok = False
                if ok:
                    summary["sent"] += 1
                    self._save_refined(r["id"], res, followup_sent=True)
                    try:
                        self.store.audit("ai_intake", "followup_sent",
                                         f"raw_id={r['id']}")
                    except Exception:
                        pass
                    time.sleep(max(0.0, float(send_gap)))
                else:
                    summary["skipped"] += 1

        self.last_run = iso_now()
        self.last_summary = summary
        return summary

    def _pending_rows(self, rows: list[dict]) -> list[dict]:
        """Rows still worth a visit: never analysed, or analysed but still
        waiting for their follow-up to be released."""
        pending = []
        for r in rows:
            raw = r.get("raw_text") or ""
            if not raw:
                continue
            fj = r.get("refined_json") or ""
            if not fj:
                pending.append(r)
                continue
            try:
                parsed = json.loads(fj)
            except Exception:
                pending.append(r)
                continue
            if parsed.get("should_reply") and not parsed.get("followup_sent"):
                pending.append(r)
        pending.sort(key=lambda r: r.get("id") or 0)
        return pending

    def _from_stored(self, raw_text: str, fj: str) -> IntakeResult:
        parsed = json.loads(fj)
        return IntakeResult(
            intent=parsed.get("intent", "unknown"),
            missing=list(parsed.get("missing") or []),
            reply=parsed.get("reply", ""),
            should_reply=bool(parsed.get("should_reply")),
            raw_text=raw_text,
            confidence=float(parsed.get("confidence") or 0.0),
            analyzed_by=parsed.get("analyzed_by", "stored"),
            reading_value=parsed.get("reading_value"),
            reading_tag=parsed.get("reading_tag"),
            reading_candidates=list(parsed.get("reading_candidates") or []),
            reading_status=parsed.get("reading_status", "none"),
            reading_ts=parsed.get("reading_ts"),
            meal_items=list(parsed.get("meal_items") or []),
            meal_portion=parsed.get("meal_portion"),
            meal_portion_text=parsed.get("meal_portion_text"),
            meal_ts=parsed.get("meal_ts"),
            multi_readings=list(parsed.get("multi_readings") or []),
            language=parsed.get("language", "hi"),
        )

    def _build_context(self, sender: str, patient: Optional[dict]) -> dict:
        """Recent-log context given to Gemini so its reply is state-accurate."""
        ctx: dict = {}
        try:
            if not patient:
                return ctx
            window = (self.store.active_window_for(patient["id"])
                      or self.store.last_window_for(patient["id"]))
            if not window or not window.get("id"):
                return ctx
            wid = window["id"]
            try:
                mine = [r for r in self.store.readings_for_window(wid)
                        if r.get("sender_phone") == sender]
            except Exception:
                mine = []
            confirmed = sorted(
                [r for r in mine if r.get("status") == "confirmed"],
                key=lambda r: r.get("ts") or "", reverse=True)
            ctx["recent_readings"] = [
                {"value": r.get("value"), "tag": r.get("tag"),
                 "ts": r.get("ts")} for r in confirmed[:4]]
            ctx["pending_readings"] = [
                {"value": r.get("value"), "ts": r.get("ts")}
                for r in mine if r.get("status") == "pending"]
            try:
                meals = self.store.meals_for_window(wid, confirmed_only=True)
                ctx["recent_meals"] = [
                    {"items_json": m.get("items_json"), "ts": m.get("ts")}
                    for m in meals[-3:]]
            except Exception:
                pass
            dup = self._find_dup_pending(sender)
            if dup:
                ctx["dup_pending"] = {"value": dup.get("value"), "ts": dup.get("ts")}
        except Exception as e:
            print(f"[Aahaar] AI intake context error: {e}")
        return ctx

    def _save_refined(self, raw_id: int, res: IntakeResult,
                      followup_sent: bool = False,
                      registered: bool = False) -> None:
        prev_registered = prev_meal_registered = False
        dup_pending = None
        try:
            row = self.store.conn.execute(
                "SELECT refined_json FROM raw_inbound WHERE id=?",
                (int(raw_id),)).fetchone()
            if row and row["refined_json"]:
                prev = json.loads(row["refined_json"])
                prev_registered = bool(prev.get("registered"))
                prev_meal_registered = bool(prev.get("meal_registered"))
                dup_pending = prev.get("dup_pending")
        except Exception:
            pass
        payload = {
            "intent": res.intent,
            "missing": res.missing,
            "reply": res.reply,
            "should_reply": res.should_reply,
            "confidence": res.confidence,
            "analyzed_by": res.analyzed_by,
            "followup_sent": bool(followup_sent),
            "reading_value": res.reading_value,
            "reading_tag": res.reading_tag,
            "reading_candidates": list(res.reading_candidates or []),
            "reading_status": res.reading_status,
            "reading_ts": res.reading_ts,
            "meal_items": list(res.meal_items or []),
            "meal_portion": res.meal_portion,
            "meal_portion_text": res.meal_portion_text,
            "meal_ts": res.meal_ts,
            "multi_readings": list(res.multi_readings or []),
            "language": res.language,
            "registered": bool(prev_registered) or bool(registered),
            "meal_registered": bool(prev_meal_registered),
        }
        if dup_pending is not None:
            payload["dup_pending"] = dup_pending
        with self.store.tx() as c:
            c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                      (json.dumps(payload, ensure_ascii=False), int(raw_id)))

    def _strengthen_reply(self, res: IntakeResult, text: str,
                          silent: bool = False) -> None:
        """Deterministic wording fills a gap ONLY when Gemini left it open.

        When Gemini (res.analyzed_by = 'gemini:...') already wrote the reply,
        its natural sentence is the patient-facing truth and is never replaced
        by the deterministic confirm below; DB actions are still applied.
        """
        if res.reply and str(res.reply or "").strip():
            return
        if silent:
            res.reply = ""
            res.should_reply = False
        else:
            res.reply = text

    def _maybe_register(self, raw_row: dict, res: IntakeResult, sender: str) -> None:
        """Write the AI-decided reading into the readings table (window-scoped).

        Off-webhook and dashboard-driven. Handles:
          * tag answers   -> apply the reading-context tag in place, CONFIRM it;
          * tag negations -> "fasting nhi thi" never logs the denied tag;
          * corrections   -> "130 not 120" updates the latest reading + confirms;
          * dup answers   -> "new" registers the earlier blocked value, else skip;
          * resolutions   -> confirm an ambiguous (pending) reading to its value;
          * ambiguous     -> keep a status='pending' row (never guess a number);
          * single value  -> confirm it; WITHOUT before/after context it stays
                            'needs confirmation' (pending) until the patient
                            tells the context (duplicates then ask instead).
        Every action that changes the log sends a short confirmation to the
        patient. Never duplicated — guarded by row markers + existing reads.
        """
        try:
            if not sender:
                return
            patient = self.store.get_patient_by_phone(sender)
            if not patient:
                return
            window = (self.store.active_window_for(patient["id"])
                      or self.store.last_window_for(patient["id"]))
            if not window or not window.get("id"):
                return
            wid = window["id"]
            name = (patient.get("name") or "ji").strip() or "ji"
            intent = res.intent

            # same-row idempotency
            fj = raw_row.get("refined_json") or ""
            if fj:
                try:
                    if json.loads(fj).get("registered"):
                        return
                except Exception:
                    pass

            sender_rows = [r for r in self.store.readings_for_window(wid)
                           if r.get("sender_phone") == sender]
            confirmed = [r for r in sender_rows if r.get("status") == "confirmed"]
            pending = [r for r in sender_rows if r.get("status") == "pending"]
            latest_conf = (confirmed and sorted(
                confirmed, key=lambda r: r.get("ts") or "", reverse=True)[0]) or None
            latest_pend = (pending and sorted(
                pending, key=lambda r: r.get("ts") or "", reverse=True)[0]) or None
            target = latest_pend or latest_conf

            if intent == "reading_delete":
                # Delete the reading the message points at (its own day/time
                # word wins), else the latest logged one.
                del_target = None
                if res.reading_ts:
                    day = str(res.reading_ts)[:10]
                    dated = [r for r in sender_rows
                             if str(r.get("ts") or "")[:10] == day]
                    if dated:
                        del_target = sorted(
                            dated, key=lambda r: r.get("ts") or "",
                            reverse=True)[0]
                if del_target is None:
                    del_target = latest_conf or latest_pend
                if del_target:
                    dval = float(del_target["value"] or 0.0)
                    self.store.delete_reading(del_target["id"])
                    self.store.audit(
                        "ai_intake", "reading_deleted",
                        f"raw_id={raw_row['id']} reading={del_target['id']} "
                        f"{dval:g} at {del_target.get('ts') or ''}")
                    res.reply = (f"✅ Reading delete ho gaya ({dval:g}, "
                                 f"{fmt_ts_log(str(del_target.get('ts') or ''))})."
                                 f"{self._invite()}")
                else:
                    res.reply = (f"{name} ji, delete karne ko koi reading "
                                 "nahi mili.")
                res.should_reply = True
                res.missing = []
                self._mark_registered(raw_row["id"])
                return

            if intent == "multi_reading" and res.multi_readings:
                # Register each reported value; skip same-day+same-hour+same
                # value duplicates so re-scans never double-log.
                parts = []
                for mr in res.multi_readings:
                    mv = float(mr.get("value") or 0.0)
                    mtag = str(mr.get("tag") or "").strip() or "random"
                    mts = str(mr.get("ts_str") or self._now_iso())
                    same = [r for r in sender_rows
                            if str(r.get("ts") or "")[:10] == mts[:10]
                            and str(r.get("ts") or "")[11:13] == mts[11:13]
                            and abs(float(r.get("value") or 0.0) - mv) < 0.5]
                    if same:
                        parts.append(f"{mv:g} (already, same time)")
                        continue
                    self.store.add_reading(wid, sender, "patient", mtag, mv,
                                           ts=mts)
                    parts.append(
                        f"{mv:g} ({PATIENT_TAG_LABELS.get(mtag, mtag)})")
                self.store.audit(
                    "ai_intake", "readings_registered",
                    f"raw_id={raw_row['id']} count={len(res.multi_readings)}")
                res.reply = ("✅ Sugar log ho gayi: "
                             + ", ".join(parts) + "." + self._invite())
                res.should_reply = True
                res.missing = []
                self._mark_registered(raw_row["id"])
                return

            if intent == "tag_answer":
                tag = _tag_from_text(res.raw_text) or "random"
                if tag == "pre":
                    # Before-meal pickings are discouraged, never logged.
                    res.reply = ("Ji, khane se pehle ka prick zaruri nahi hota. "
                                 "Fasting, khane ke 2 ghante baad, ya random — "
                                 "ye tin me se bata dijiye, aur value de dijiye.")
                    res.should_reply = True
                    res.missing = []
                    self._mark_registered(raw_row["id"])
                    return
                if target:
                    self.store.set_reading_tag(target["id"], tag)
                    if target.get("status") == "pending":
                        self.store.resolve_reading(
                            target["id"], float(target["value"]), tag)
                    self.store.audit("ai_intake", "reading_tagged",
                                     f"raw_id={raw_row['id']} reading={target['id']} "
                                     f"({'pending ' if latest_pend else ''}{tag})")
                    label = PATIENT_TAG_LABELS.get(tag, tag)
                    res.reply = self._confirm_reading(
                        float(target["value"]), tag, str(target.get("ts") or ""))
                    res.should_reply = True
                    res.missing = []
                else:
                    res.reply = (f"{name} ji, abhi koi sugar logged nahi hai — "
                                 "pehle sugar value bataiye.")
                    res.should_reply = True
                self._mark_registered(raw_row["id"])
                return

            if intent == "tag_negation":
                denied = _is_tag_negation(res.raw_text)
                kept = target and target.get("tag") and target["tag"] != denied
                if kept:
                    label = PATIENT_TAG_LABELS.get(target["tag"], target["tag"])
                    res.reply = f"✅ Theek hai — {label} hi logged hai."
                    res.should_reply = True
                else:
                    if target and target.get("tag") == denied:
                        self.store.set_reading_tag(target["id"], "")
                    denied_label = PATIENT_TAG_LABELS.get(denied, denied or "wo")
                    res.reply = (f"{name} ji, theek hai — {denied_label} nahi. "
                                 "Phir ye kab ka tha — fasting, khane ke 2 ghante "
                                 "baad, ya random?")
                    res.should_reply = True
                    res.missing = ["reading_tag"]
                self.store.audit("ai_intake", "tag_negated",
                                 f"raw_id={raw_row['id']} denied={denied or ''} "
                                 f"kept={target.get('tag') if kept else ''}")
                self._mark_registered(raw_row["id"])
                return

            if intent == "correction" and res.reading_value is not None:
                v = float(res.reading_value)
                # A dated edit ("kal 8am wala galat tha, 140 tha") targets the
                # reading on THAT day. When a specific time was given, prefer
                # the reading closest to that hour/minute; fall back to the
                # latest on the day. When sender-scoped rows miss the target
                # (seeded data uses different sender) fall back to the whole
                # window — the user said "change X reading", which implies the
                # reading exists.
                tgt = None
                if res.reading_ts:
                    day = str(res.reading_ts)[:10]
                    r_hour = str(res.reading_ts)[11:13]
                    r_min  = str(res.reading_ts)[14:16]
                    # First look among this sender's own rows.
                    dated = [r for r in sender_rows
                             if str(r.get("ts") or "")[:10] == day]
                    if not dated:
                        # Wider window: covers seeded data and cross-sender edits.
                        dated = [r for r in self.store.readings_for_window(wid)
                                 if str(r.get("ts") or "")[:10] == day]
                    if dated and r_hour:
                        same_hour = [r for r in dated
                                     if str(r.get("ts") or "")[11:13] == r_hour]
                    else:
                        same_hour = []
                    if same_hour and r_min:
                        same_min = [r for r in same_hour
                                    if str(r.get("ts") or "")[14:16] == r_min]
                        if same_min:
                            same_hour = same_min
                    if same_hour:
                        tgt = sorted(same_hour, key=lambda r: r.get("ts") or "",
                                     reverse=True)[0]
                    if tgt is None and dated:
                        tgt = sorted(dated, key=lambda r: r.get("ts") or "",
                                     reverse=True)[0]
                if tgt is None:
                    tgt = latest_pend or latest_conf
                if tgt:
                    old = float(tgt["value"] or 0.0)
                    new_tag = (res.reading_tag or tgt.get("tag") or "random")
                    new_ts = res.reading_ts or tgt.get("ts")
                    self.store.update_reading(tgt["id"], value=v, tag=new_tag,
                                              ts=new_ts, status="confirmed")
                    self.store.audit("ai_intake", "reading_corrected",
                                     f"raw_id={raw_row['id']} reading={tgt['id']} "
                                     f"{old:g}->{v:g}")
                    t = str(new_ts or "")
                    label = PATIENT_TAG_LABELS.get(new_tag, new_tag)
                    res.reply = (f"✅ Update ho gaya — {fmt_ts_log(t)}: {label} "
                                 f"{v:g} (pehle {old:g} tha).{self._invite()}")
                    res.should_reply = True
                    res.missing = []
                else:
                    ts = res.reading_ts or self._now_iso()
                    tag = (res.reading_tag or "").strip() or "random"
                    self.store.add_reading(wid, sender, "patient", tag, v, ts=ts)
                    self.store.audit("ai_intake", "reading_registered",
                                     f"raw_id={raw_row['id']} {tag} {v:g} at {ts}")
                    res.reply = self._confirm_reading(v, tag, ts)
                    res.should_reply = True
                    res.missing = []
                self._mark_registered(raw_row["id"])
                return

            if intent == "dup_answer":
                ans = _is_dup_answer(res.raw_text)
                dup = self._find_dup_pending(sender)
                if ans == "new" and dup:
                    v = float(dup["value"])
                    ts = str(dup.get("ts") or self._now_iso())
                    self.store.add_reading(wid, sender, "patient", "random", v, ts=ts)
                    self.store.audit("ai_intake", "reading_registered",
                                     f"raw_id={raw_row['id']} confirmed-dup {v:g} at {ts}")
                    res.reply = self._confirm_reading(v, None, ts)
                    res.should_reply = True
                    res.missing = []
                else:
                    self.store.audit("ai_intake", "duplicate_skipped",
                                     f"raw_id={raw_row['id']} ans={ans or ''}")
                    res.reply = ""
                    res.should_reply = False
                self._mark_registered(raw_row["id"])
                return

            if intent == "resolution" and res.reading_value is not None:
                v = float(res.reading_value)
                ts = res.reading_ts or self._now_iso()
                pend = self.store.pending_reading_near(sender, wid)
                if pend:
                    self.store.resolve_reading(pend["id"], v, res.reading_tag or "random")
                    self.store.audit("ai_intake", "reading_resolved",
                                     f"raw_id={raw_row['id']} reading={pend['id']} -> {v:g}")
                    res.reply = self._confirm_reading(
                        v, res.reading_tag or "random", ts)
                else:
                    tag = (res.reading_tag or "").strip() or "random"
                    self.store.add_reading(wid, sender, "patient", tag, v, ts=ts)
                    self.store.audit("ai_intake", "reading_registered",
                                     f"raw_id={raw_row['id']} {tag} {v:g} at {ts}")
                    res.reply = self._confirm_reading(v, tag, ts)
                res.should_reply = True
                res.missing = []
                self._mark_registered(raw_row["id"])
                return

            if intent == "reading" and res.reading_status == "ambiguous" and res.reading_candidates:
                cand = sorted(float(x) for x in res.reading_candidates)
                existing = self.store.pending_reading_near(sender, wid)
                if existing and existing.get("candidates_json"):
                    try:
                        if sorted(float(x) for x in
                                  json.loads(existing["candidates_json"])) == cand:
                            self._mark_registered(raw_row["id"])
                            return
                    except Exception:
                        pass
                ts = res.reading_ts or self._now_iso()
                self.store.add_reading(wid, sender, "patient", "random",
                                       cand[0] if cand else 0.0,
                                       ts=ts, status="pending",
                                       candidates_json=json.dumps(cand),
                                       raw_id=int(raw_row["id"]))
                self.store.audit("ai_intake", "reading_pending",
                                 f"raw_id={raw_row['id']} candidates={cand}")
                self._mark_registered(raw_row["id"])
                return

            if res.reading_status == "resolved" and res.reading_value is not None:
                v = float(res.reading_value)
                tag = (res.reading_tag or "").strip() or "random"
                ts = res.reading_ts or self._now_iso()
                # If the very same single value is already pending (an earlier
                # message that asked about a duplicate), this is its "naya hai"
                # answer, not an extra log.
                for pd in pending:
                    if (not pd.get("candidates_json")
                            and abs(float(pd.get("value") or 0.0) - v) < 0.5):
                        res.reply = ""
                        res.should_reply = False
                        self._mark_registered(raw_row["id"])
                        return
                target_day = (ts or "")[:10]
                dup = None
                for rd in confirmed:
                    if str(rd.get("ts") or "")[:10] == target_day:
                        try:
                            if abs(float(rd.get("value") or 0.0) - v) < 0.5:
                                dup = rd
                                break
                        except (TypeError, ValueError):
                            continue
                if dup:
                    self.store.audit("ai_intake", "duplicate_asked",
                                     f"raw_id={raw_row['id']} value={v:g} "
                                     f"matches reading {dup['id']}")
                    res.reply = (f"{name} ji, sugar {v:g} is already logged for "
                                 f"{fmt_ts_log(ts)} — naya hai ya mistake? "
                                 "('naya' / 'mistake')")
                    res.should_reply = True
                    res.missing = ["duplicate"]
                    self._store_dup_pending(raw_row["id"], v, ts)
                    self._mark_registered(raw_row["id"])
                    return
                self.store.add_reading(wid, sender, "patient", tag, v, ts=ts)
                self.store.audit("ai_intake", "reading_registered",
                                 f"raw_id={raw_row['id']} {tag} {v:g} at {ts}")
                self._mark_registered(raw_row["id"])
                return
        except Exception as e:
            print(f"[Aahaar] AI intake register error: {e}")

    def _invite(self) -> str:
        # "Is that all?" is the patient-side courtesy question; it replaces the
        # old open invite so "that's all" / "bas" now reads as a normal answer.
        return " Is that all — aur kuch log karna hai (sugar ya khana)?"

    def _tag_question(self) -> str:
        return ("Ye kab ka reading tha — fasting, khane ke 2 ghante baad, "
                "ya random?")

    def _confirm_reading(self, value: float, tag: Optional[str], ts_s: Optional[str]) -> str:
        hm = fmt_ts_log(str(ts_s or ""))
        if tag:
            label = PATIENT_TAG_LABELS.get(tag, tag)
            return f"✅ Logged sugar {value:g} ({label}) — {hm}.{self._invite()}"
        return (f"✅ Logged sugar {value:g} "
                f"({PATIENT_TAG_LABELS.get('random', 'random')}) — {hm}.{self._invite()}")

    def _store_dup_pending(self, raw_id: int, value: float, ts: Optional[str]) -> None:
        try:
            with self.store.tx() as c:
                row = c.execute("SELECT refined_json FROM raw_inbound WHERE id=?",
                                (int(raw_id),)).fetchone()
                if not row or not row["refined_json"]:
                    return
                p = json.loads(row["refined_json"])
                p["dup_pending"] = {"value": float(value), "ts": str(ts or "")}
                c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                          (json.dumps(p, ensure_ascii=False), int(raw_id)))
        except Exception as e:
            print(f"[Aahaar] AI intake store dup-pending error: {e}")

    def _find_dup_pending(self, sender: str) -> Optional[dict]:
        try:
            for r in self.store.raw_inbound_all(limit=1000):
                if str(r.get("sender_phone") or "") != sender:
                    continue
                fj = r.get("refined_json") or ""
                if not fj:
                    continue
                p = json.loads(fj)
                d = p.get("dup_pending")
                if isinstance(d, dict) and d.get("value") is not None:
                    return d
        except Exception as e:
            print(f"[Aahaar] AI intake find dup-pending error: {e}")
        return None

    def _mark_registered(self, raw_id: int) -> None:
        self._mark_flag(raw_id, "registered")

    def _maybe_register_meal(self, raw_row: dict, res: IntakeResult,
                             sender: str) -> None:
        """Store the AI-recognized MEAL into the meals table (window-scoped).

        Off-webhook and dashboard-driven, like the reading registration.
        Only registers when dishes were actually recognized. Never duplicated:
        guarded by the row marker AND by dedup against a meal the deterministic
        webhook already proposed for the same dish set on the SAME DAY (ordinary
        meal messages keep their normal proposal+confirm loop; for ambiguous-
        reading messages the deterministic confirm is suppressed, so this becomes
        the only logger). The meal's timestamp honours the day/time the text
        refers to ("yesterday i ate...", "14 july lunch") via res.meal_ts,
        falling back to the message's own receive time. A "same thing / wahi /
        dono / phirse" message with no dish names inherits the dish set of the
        patient's latest logged meal so repeats backdate cleanly.
        """
        try:
            items = list(res.meal_items or [])
            # A change/replacement names TWO dishes: the OLD one to supersede
            # and the NEW one actually eaten. Extract the old dish and rebuild
            # the meal from the text with the change-phrase REMOVED, so the old
            # dish is never merged into the replacement ("i ate kitkat instead
            # of the chocolate i told you" -> kitkat only, supersede chocolate).
            old_phrase = change_old_dish(str(res.raw_text or ""))
            if old_phrase and _is_change_text(str(res.raw_text or "")):
                rem = change_remainder(str(res.raw_text or ""))
                revived = list(_meal_items(rem, self.cfg)) if rem else []
                if revived:
                    items = revived
                    res.meal_items = items
            fj = raw_row.get("refined_json") or ""
            if fj:
                try:
                    if json.loads(fj).get("meal_registered"):
                        return
                except Exception:
                    pass
            if not sender:
                return
            patient = self.store.get_patient_by_phone(sender)
            if not patient:
                return
            window = (self.store.active_window_for(patient["id"])
                      or self.store.last_window_for(patient["id"]))
            if not window or not window.get("id"):
                return
            wid = window["id"]

            # A portion answer ('small', 'small choco', '200ml') finalizes the
            # patient's pending meal instead of bouncing to a confused clarify.
            if res.intent == "meal_confirm":
                pend = self.store.newest_pending(sender)
                if not pend:
                    res.reply = ("Ji, abhi ko pending khana nahi hai — pehle "
                                 "khana bataiye.")
                    res.should_reply = True
                    res.missing = []
                    return
                low2 = str(res.raw_text or "").lower()
                ptext = portion_text(low2) or res.meal_portion or None
                self.store.finalize_meal(pend["id"], "confirmed",
                                         res.meal_portion, portion_text=ptext)
                if res.meal_items:
                    cur = json.loads(pend.get("items_json") or "[]")
                    have = {(str(x.get("item") or "").lower(), x.get("genus"))
                            for x in cur}
                    for it in res.meal_items:
                        key = (str(it.get("item") or "").lower(), it.get("genus"))
                        if key not in have:
                            cur.append(it)
                    new_carbs = (sum(float(x.get("carbs") or 0.0) for x in cur)
                                 or None)
                    new_gi = (self._split_gi(cur)
                              if any(x.get("gi") for x in cur) else None)
                    self.store.update_meal(pend["id"], items_json=json.dumps(
                        cur, ensure_ascii=False), carbs=new_carbs, gi=new_gi)
                plabel = KATORI_LABELS.get(res.meal_portion or "m", "Medium")
                res.reply = (f"✅ Khana {plabel} log ho gaya."
                             f"{self._invite()}")
                res.should_reply = True
                res.missing = []
                self._mark_flag(raw_row["id"], "meal_registered")
                return

            # The patient asks to delete a logged meal ("ye khana delete karo",
            # "500ml khana was wrong khud delete karo").
            if res.intent == "meal_delete":
                del_meal = None
                if res.meal_ts:
                    day = str(res.meal_ts)[:10]
                    dated = [m for m in self.store.meals_for_window(
                                 wid, confirmed_only=False)
                             if m.get("sender_phone") == sender
                             and str(m.get("ts") or "")[:10] == day]
                    if dated:
                        del_meal = sorted(
                            dated, key=lambda m: m.get("ts") or "",
                            reverse=True)[0]
                if del_meal is None:
                    latest = (self.store.meals_for_window(
                        wid, confirmed_only=False)) or []
                    mine = [m for m in reversed(latest)
                            if m.get("sender_phone") == sender
                            and m.get("status") != "superseded"]
                    del_meal = mine[0] if mine else None
                if del_meal:
                    self.store.delete_meal(del_meal["id"])
                    self.store.audit(
                        "ai_intake", "meal_deleted",
                        f"raw_id={raw_row['id']} meal={del_meal['id']} "
                        f"ts={del_meal.get('ts') or ''}")
                    res.reply = ("✅ Khana delete ho gaya."
                                 f"{self._invite()}")
                else:
                    res.reply = (f"{name} ji, delete karne ko koi khana "
                                 "log nahi hua.")
                res.should_reply = True
                res.missing = []
                self._mark_flag(raw_row["id"], "meal_registered")
                return

            # A reference/correction ("not the one i told", "the meal i told
            # was wrong") with no new dish is answered from the pending/previous
            # meal — never guessed into a fabricated dish.
            if res.intent == "meal_reference":
                pend = self.store.newest_pending(sender)
                if pend:
                    pname = ", ".join(
                        str(x.get("item") or "")
                        for x in json.loads(pend.get("items_json") or "[]"))
                    res.reply = (f"Ji, {pname or 'wo khana'} sahi hai? "
                                 "Agar aapne wo hi khaya hai to small, medium "
                                 "ya large bata dijiye.")
                    res.should_reply = True
                    res.missing = ["portion"]
                else:
                    prev = None
                    latest = (self.store.meals_for_window(
                        wid, confirmed_only=False)) or []
                    mine = [m for m in reversed(latest)
                            if m.get("sender_phone") == sender]
                    if mine:
                        prev = next((m for m in mine
                                     if m.get("status") != "superseded"), None)
                    if prev and prev.get("items_json"):
                        try:
                            pname = ", ".join(
                                str(x.get("item") or "")
                                for x in json.loads(prev["items_json"]))
                        except Exception:
                            pname = ""
                        res.reply = (f"Ji aapne {pname or 'wo khana'} khaya "
                                     "tha — kya isme kuch change karna hai, "
                                     "ya delete bataiye?")
                    else:
                        res.reply = (f"{name} ji, saaf kijiye — kaun sa "
                                     "khana change/delete karna hai?")
                    res.should_reply = True
                    res.missing = []
                self._mark_flag(raw_row["id"], "meal_registered")
                return

            # The meal takes the same day/time the text refers to ("yesterday i
            # ate...", "14 july lunch"); if the message was also a reading, its
            # backdated reading_ts counts too ("...ate the same thing, reading
            # was 220" -> both go to yesterday).
            ts = (res.meal_ts or res.reading_ts
                  or str(raw_row.get("ts") or self._now_iso()))
            low = str(res.raw_text or "").lower()

            # "same thing / wahi khana / do the same / phirse" inheritance: the
            # message repeats a previously-logged meal, so reuse its dish set
            # (carbs/GI included) at the backdated time. Applied when no dishes
            # were named OR when the only "dish" is the text-classifier's long
            # sentence fallback (e.g. "yea yesterday i forgot to tell...").
            _SAME_REF = ("same thing", "same khana", "same khaana", "same food",
                         "same dishes", "same meal", "same", "wahi", "wohi",
                         "dono", "phirse", "phir se")
            inherited: list = []
            if any(k in low for k in _SAME_REF):
                try:
                    latest = self.store.meals_for_window(
                        wid, confirmed_only=False) or []
                    prev = next((m for m in reversed(latest)
                                 if m.get("items_json")
                                 and json.loads(m["items_json"])), None)
                    if prev:
                        inherited = json.loads(prev["items_json"])
                except Exception:
                    inherited = []
            if not items:
                items = list(inherited)
            elif inherited and all(it.get("known") is False for it in items):
                # The only "dishes" were the classifier's fallback guesses for a
                # "same thing / wahi" repeat message -> reuse the real dish set.
                items = list(inherited)
            if not items:
                return
            want = {(str(it.get("item") or "").lower(), it.get("genus"),
                     it.get("portion") or "m") for it in items}
            # Dedup against meals on the SAME DAY as the target ts only, so a
            # backdated "same thing yesterday" copy is logged while today's row
            # stays untouched. A replacement ("instead of X") always registers —
            # it is a new eat event, never a mistaken repeat of the old row.
            if not (old_phrase and _is_change_text(str(res.raw_text or ""))):
                if any(self._same_dish_set(m.get("items_json"), want)
                       for m in self.store.meals_for_window(
                           wid, confirmed_only=False)
                       if str(m.get("ts") or "")[:10] == ts[:10]):
                    if res.intent == "meal":
                        res.reply = ""
                        res.should_reply = False
                    self._mark_flag(raw_row["id"], "meal_registered")
                    return
            portion = res.meal_portion or items[0].get("portion", "m") or "m"
            # A same-dish message that ALSO states a size ("the meal was large
            # chocolates" after a pending "Two Chocolates", or "120 and the meal
            # was large chocolates") COMPLETES the pending meal - the answer
            # renames/clarifies THAT dish instead of starting a duplicate.
            # Plain repeats ("2 roti dal sabzi" twice) never match: they carry
            # no size/change word and keep the normal proposal+confirm loop.
            _STRONG_CHANGE = ("change", "changed", "replace", "replaced",
                              "galat", "wrong", "sudhar", "update",
                              "badlo", "badal", "sahi karo",
                              "not the one", "i told", "told",
                              "pehle bola", "bola tha", "jo bola",
                              "instead of", "insteadof", "instead")
            is_change = (any(k in low for k in _STRONG_CHANGE)
                         or "actually" in low)
            pend = self.store.newest_pending(sender)
            pend_items = []
            if pend:
                try:
                    pend_items = json.loads(pend.get("items_json") or "[]")
                except Exception:
                    pend_items = []
            pend_names = {str(x.get("item") or "").lower().strip().strip(".")
                          for x in pend_items}
            my_names = {str(it.get("item") or "").lower().strip().strip(".")
                        for it in items}

            # A "change X to Y" that names a genuinely NEW dish is a REPLACEMENT,
            # never an expansion: log ONLY the new dish as a fresh meal row and
            # mark the old one superseded (kept visible with a strikethrough).
            # The old row is found BY NAME (the dish the patient actually
            # replaced) and falls back to the newest pending proposal.
            victim = pend
            victim_names = pend_names
            if old_phrase and is_change and items:
                latest = (self.store.meals_for_window(
                    wid, confirmed_only=False)) or []
                victim = next(
                    (m for m in reversed(latest)
                     if m.get("sender_phone") == sender
                     and m.get("status") != "superseded"
                     and m.get("items_json")
                     and dish_mentions_phrase(
                         [str(x.get("item") or "")
                          for x in json.loads(m["items_json"])],
                         old_phrase)), None) or pend
                if victim and victim.get("items_json"):
                    try:
                        vraw = json.loads(victim["items_json"])
                    except Exception:
                        vraw = []
                    victim_names = {str(x.get("item") or "").lower()
                                    .strip().strip(".")
                                    for x in vraw}
            if ((pend or old_phrase) and items and is_change
                    and res.intent in ("meal", "reading")
                    and any(n not in victim_names for n in my_names)):
                fresh = [it for it in items
                         if (str(it.get("item") or "").lower().strip().strip(".")
                             not in victim_names)]
                if fresh:
                    fresh_names = ", ".join(str(it.get("item")) for it in fresh)
                    repl_portion = (res.meal_portion
                                    or items[0].get("portion", "m")
                                    or (victim or {}).get("portion") or "m")
                    repl_txt = (res.meal_portion_text
                                or portion_text(low) or None)
                    new_id = self.store.propose_meal(
                        wid, sender, "patient", "ai",
                        fresh, repl_portion, self.cfg.katori(repl_portion),
                        (sum(float(it.get("carbs") or 0.0) for it in fresh)
                         or None),
                        self._split_gi(fresh)
                        if any(it.get("gi") for it in fresh) else None,
                        float(res.confidence), ts=ts, portion_text=repl_txt)
                    if victim:
                        self.store.supersede_meal(victim["id"], new_id)
                    self.store.finalize_meal(new_id, "confirmed",
                                             repl_portion,
                                             portion_text=repl_txt)
                    self.store.audit(
                        "ai_intake", "meal_replaced",
                        f"raw_id={raw_row['id']} old="
                        f"{victim['id'] if victim else '-'} "
                        f"new={new_id} new_dish={fresh_names} ts={ts}")
                    old_dish = ", ".join(sorted(str(x) for x in victim_names))
                    res.reply = (
                        f"✅ {old_dish or 'wo'} wala entry badal kar {fresh_names} "
                        f"({KATORI_LABELS.get(repl_portion, 'Medium')}) update kar "
                        f"diya — purana entry cross-mark ho gaya."
                        f"{self._invite()}")
                    res.should_reply = True
                    res.missing = []
                    self._mark_flag(raw_row["id"], "meal_registered")
                    return

            if (pend and items and res.intent in ("meal", "reading")
                    and (_portion_stated(low, res.meal_portion) or is_change)
                    and pend_names and my_names
                    and not pend_names.isdisjoint(my_names)):
                    pend_portion = (res.meal_portion
                                    or items[0].get("portion")
                                    or pend.get("portion") or "m")
                    pend_txt = res.meal_portion_text or portion_text(low) or None
                    self.store.finalize_meal(pend["id"], "confirmed",
                                             pend_portion,
                                             portion_text=pend_txt)
                    if items and pend_items:
                        have = {(str(x.get("item") or "").lower(),
                                 x.get("genus")) for x in pend_items}
                        for it in items:
                            key = (str(it.get("item") or "").lower(), it.get("genus"))
                            if key not in have:
                                pend_items.append(it)
                        self.store.update_meal(
                            pend["id"], items_json=json.dumps(
                                pend_items, ensure_ascii=False))
                    self.store.audit(
                        "ai_intake", "meal_completed",
                        f"raw_id={raw_row['id']} meal={pend['id']} "
                        f"portion={pend_portion} ts={ts}")
                    plabel = KATORI_LABELS.get(pend_portion or "m", "Medium")
                    res.reply = (f"✅ Khana {plabel} log ho gaya."
                                 f"{self._invite()}")
                    res.should_reply = True
                    res.missing = []
                    self._mark_flag(raw_row["id"], "meal_registered")
                    return
            # Carb/GI numbers are deliberately NOT written anymore — the record
            # keeps only what the patient said (food + size).
            carbs = (sum(float(it.get("carbs") or 0.0) for it in items)
                     or None)
            gi = self._split_gi(items) if any(it.get("gi") for it in items) else None
            # The patient-stated size verbatim ("200ml", "2 bowls"). Never
            # invented: only stored when the message actually names it.
            portion_txt = portion_text(low) or None

            meal_id = self.store.propose_meal(
                wid, sender, "patient", "ai",
                items, portion, self.cfg.katori(portion), carbs, gi,
                float(res.confidence), ts=ts, portion_text=portion_txt)
            # The patient already named a size in this same message ("2 katori
            # rice", "small choco + sugar 200") -> complete now: confirm the row
            # so it shows in the Day Log immediately (size-word, any letter or
            # verbatim text all count).
            if (_portion_stated(low, res.meal_portion)):
                made_portion = res.meal_portion or items[0].get("portion", "m") or "m"
                self.store.finalize_meal(meal_id, "confirmed", made_portion,
                                         portion_text=portion_txt)
            # A real change message supersedes the replaced meal; the "same
            # dish, same time" webhook proposal above has already returned
            # early, so a plain repeat never double-logs here.
            if is_change:
                old = self.store.meal_at_time(wid, ts)
                if not old and any(k in low for k in _STRONG_CHANGE + ("actually",)):
                    prior = [
                        m for m in self.store.meals_for_window(
                            wid, confirmed_only=False)
                        if m.get("sender_phone") == sender
                        and m.get("status") != "superseded"
                        and m.get("id") != meal_id
                        and str(m.get("ts") or "")[:10] == ts[:10]]
                    old = prior[-1] if prior else None
                if old and old.get("id") != meal_id:
                    self.store.supersede_meal(old["id"], meal_id)
                    self.store.audit("ai_intake", "meal_superseded",
                                     f"raw_id={raw_row['id']} old={old['id']} "
                                     f"new={meal_id} ts={ts}")
            names = ", ".join(str(it.get("item") or it) for it in items)
            self.store.audit("ai_intake", "meal_registered",
                             f"raw_id={raw_row['id']} meal_id={meal_id} "
                             f"ts={ts} {names}")
            self._mark_flag(raw_row["id"], "meal_registered")
        except Exception as e:
            print(f"[Aahaar] AI intake meal-register error: {e}")

    def _mark_flag(self, raw_id: int, key: str) -> None:
        try:
            with self.store.tx() as c:
                row = c.execute(
                    "SELECT refined_json FROM raw_inbound WHERE id=?",
                    (int(raw_id),)).fetchone()
                if not row or not row["refined_json"]:
                    return
                p = json.loads(row["refined_json"])
                p[key] = True
                c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                          (json.dumps(p, ensure_ascii=False), int(raw_id)))
        except Exception as e:
            print(f"[Aahaar] AI intake mark-registered error: {e}")

    @staticmethod
    def _split_gi(items: list[dict]) -> str:
        from .nutrition import gi_bucket_index
        buckets = {it.get("gi", "med") for it in items}
        ranked = sorted(buckets, key=gi_bucket_index, reverse=True)
        return ranked[0] if ranked else "med"

    @staticmethod
    def _now_iso() -> str:
        return iso_now()

    @staticmethod
    def _same_dish_set(items_json: Optional[str], want: set) -> bool:
        try:
            have = {(str(x.get("item") or "").lower(), x.get("genus"),
                     x.get("portion") or "m")
                    for x in json.loads(items_json or "[]")}
            return bool(have) and have == want
        except Exception:
            return False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _loop() -> None:
            auto_send = bool(getattr(self.cfg, "ai_intake_auto_send", False))
            send_gap = float(getattr(self.cfg, "ai_intake_send_gap", 0.5))
            while not self._stop.is_set():
                try:
                    self.run_once(limit=10, should_send=auto_send,
                                  send_gap=send_gap)
                except Exception as e:
                    print(f"[Aahaar] AI intake worker loop error: {e}")
                self._stop.wait(self.interval)

        self._thread = threading.Thread(target=_loop, name="aahaar-ai-intake",
                                        daemon=True)
        _worker_threads.add(self._thread)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()