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
    _portion_stated,
    analyze_intake,
    portion_text,
)
from .parse import (PATIENT_TAG_LABELS, _is_dup_answer,
                    _is_tag_negation, _tag_from_text)
from .nutrition import KATORI_LABELS


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
        """Analyze stored rows; send a follow-up only when explicitly asked.

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
                    res = analyze_intake(r["raw_text"],
                                         patient_name=patient["name"] if patient else "Patient",
                                         cfg=self.cfg,
                                         msg_ts=str(r.get("ts") or ""))
                    self._save_refined(r["id"], res, followup_sent=False)
                    summary["analyzed"] += 1
            except Exception as e:
                print(f"[Aahaar] AI intake worker analyze error (raw_id={r.get('id')}): {e}")
                summary["skipped"] += 1
                continue

            self._maybe_register(r, res, sender)
            self._maybe_register_meal(r, res, sender)

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
            meal_ts=parsed.get("meal_ts"),
        )

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
            "meal_ts": res.meal_ts,
            "registered": bool(prev_registered) or bool(registered),
            "meal_registered": bool(prev_meal_registered),
        }
        if dup_pending is not None:
            payload["dup_pending"] = dup_pending
        with self.store.tx() as c:
            c.execute("UPDATE raw_inbound SET refined_json=? WHERE id=?",
                      (json.dumps(payload, ensure_ascii=False), int(raw_id)))

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

            if intent == "tag_answer":
                tag = _tag_from_text(res.raw_text) or "postprandial"
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
                if target:
                    old = float(target["value"] or 0.0)
                    new_tag = res.reading_tag or target.get("tag") or "postprandial"
                    new_ts = res.reading_ts or target.get("ts")
                    self.store.update_reading(target["id"], value=v, tag=new_tag,
                                              ts=new_ts, status="confirmed")
                    self.store.audit("ai_intake", "reading_corrected",
                                     f"raw_id={raw_row['id']} reading={target['id']} "
                                     f"{old:g}->{v:g}")
                    t = str(new_ts or "")
                    label = PATIENT_TAG_LABELS.get(new_tag, new_tag)
                    res.reply = (f"✅ Update ho gaya — {fmt_ts_log(t)}: {label} "
                                 f"{v:g} (pehle {old:g} tha).{self._invite()}")
                    res.should_reply = True
                    res.missing = []
                else:
                    ts = res.reading_ts or self._now_iso()
                    tag = (res.reading_tag or "").strip() or "postprandial"
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
                    self.store.add_reading(wid, sender, "patient", "postprandial", v, ts=ts)
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
                    self.store.resolve_reading(pend["id"], v, res.reading_tag or "postprandial")
                    self.store.audit("ai_intake", "reading_resolved",
                                     f"raw_id={raw_row['id']} reading={pend['id']} -> {v:g}")
                    res.reply = self._confirm_reading(
                        v, res.reading_tag or "postprandial", ts)
                else:
                    tag = (res.reading_tag or "").strip() or "postprandial"
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
                self.store.add_reading(wid, sender, "patient", "postprandial",
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
                tag = (res.reading_tag or "").strip() or "postprandial"
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
        return " Aur kuch log karna hai — sugar ya khana?"

    def _tag_question(self) -> str:
        return ("Ye kab ka reading tha — fasting, khane ke 2 ghante baad, "
                "ya random?")

    def _confirm_reading(self, value: float, tag: Optional[str], ts_s: Optional[str]) -> str:
        hm = fmt_ts_log(str(ts_s or ""))
        if tag:
            label = PATIENT_TAG_LABELS.get(tag, tag)
            return f"✅ Logged sugar {value:g} ({label}) — {hm}.{self._invite()}"
        return f"✅ Logged sugar {value:g} ({PATIENT_TAG_LABELS['postprandial']}) — {hm}.{self._invite()}"

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
            # stays untouched.
            if any(self._same_dish_set(m.get("items_json"), want)
                   for m in self.store.meals_for_window(wid, confirmed_only=False)
                   if str(m.get("ts") or "")[:10] == ts[:10]):
                if res.intent == "meal":
                    res.reply = ""
                    res.should_reply = False
                self._mark_flag(raw_row["id"], "meal_registered")
                return
            portion = res.meal_portion or items[0].get("portion", "m") or "m"
            # Carb/GI numbers are deliberately NOT written anymore — the record
            # keeps only what the patient said (food + size).
            carbs = (sum(float(it.get("carbs") or 0.0) for it in items)
                     or None)
            gi = self._split_gi(items) if any(it.get("gi") for it in items) else None
            # The patient-stated size verbatim ("200ml", "2 bowls"). Never
            # invented: only stored when the message actually names it.
            portion_txt = portion_text(low) or None
            _STRONG_CHANGE = ("change", "changed", "replace", "replaced",
                              "galat", "wrong", "sudhar", "update",
                              "badlo", "badal", "sahi karo")
            is_change = (any(k in low for k in _STRONG_CHANGE)
                         or "actually" in low)
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
            # A meal-change message ("actually ate dinner, not lunch" / "change
            # the meal") keeps the previous row and marks it superseded, so both
            # versions stay visible at the same time.
            if is_change:
                old = self.store.meal_at_time(wid, ts)
                if not old and any(k in low for k in _STRONG_CHANGE):
                    prior = [m for m in self.store.meals_for_window(
                                 wid, confirmed_only=False)
                             if m.get("sender_phone") == sender
                             and m.get("status") != "superseded"
                             and m.get("id") != meal_id]
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
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()