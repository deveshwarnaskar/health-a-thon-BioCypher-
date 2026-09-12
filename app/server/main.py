"""FastAPI wiring — thin HTTP skin over the pure-Python core.

Endpoints
  GET  /healthz                        liveness
  POST /api/v1/inbound                 neutral intake (used by the simulator + testing)
  POST /api/v1/webhooks/whatsapp       Meta webhook (verify + inbound messages)
  GET  /api/v1/patients/{id}/metrics   latest-window metrics JSON
  GET  /api/v1/patients/{id}/report    report context JSON
  POST /api/v1/patients/{id}/report/build   render 2-page PDF + PNGs
  POST /api/v1/demo/seed               seed demo patient + window
  POST /api/v1/demo/day                simulate one more logging day
  /    static dashboard (vanilla JS, no build)
"""
from __future__ import annotations

import os

from fastapi import BackgroundTasks, FastAPI, Header, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import Settings, get_settings
from ..core.datamodel import Store
from ..core.escalation import due_escalations
from ..core.metrics import latest_metrics
from ..core.report import latest_report_context
from ..core.seed import seed_demo
from ..core.process import IngestService
from ..core.ai_worker import IntakeWorker
from .whatsapp import CloudBackend, SimulatorBackend

settings: Settings = get_settings()

import re

_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-\+]{5,20}$")


def _valid_phone(s: str) -> bool:
    s = (s or "").strip()
    return bool(s and _PHONE_RE.match(s))


_webhook_history: list[dict] = []


def _record_webhook_event(store, event_type: str, ip: str, detail: dict, status: str):
    """Record a webhook event both in-memory (fast lookup) and in SQLite so the
    count / last-event survives every redeploy and multi-worker restart.
    """
    from datetime import datetime
    entry = {
        "ts": datetime.now().isoformat(),
        "event_type": event_type,
        "client_ip": ip,
        "status": status,
        "detail": detail,
    }
    _webhook_history.insert(0, entry)
    if len(_webhook_history) > 30:
        _webhook_history.pop()
    try:
        store.record_webhook_event(event_type, ip, status, detail)
    except Exception as exc:
        print(f"[Aahaar] persist webhook event failed: {exc}")


def _parse_whe(row: dict | None) -> dict | None:
    """Parse the JSON detail blob from a persisted webhook_events row."""
    if not row:
        return row
    detail = row.get("detail")
    if isinstance(detail, str):
        try:
            import json as _json
            row["detail"] = _json.loads(detail)
        except Exception:
            pass
    return row


def _make_backend(store: Store):
    if settings.whatsapp == "cloud":
        return CloudBackend(store, settings)
    return SimulatorBackend(store, settings)


def create_app(cfg: Settings | None = None, db_path: str | None = None):
    global settings
    if cfg is not None:
        settings = cfg
    path = db_path or settings.db_path
    store = Store(path)
    backend = _make_backend(store)
    ingest = IngestService(store, settings)

    def _intake_send(out):
        try:
            return backend.send(out)
        except Exception as e:
            print("[Aahaar] AI intake send failed:", e)
            return False

    # Decoupled AI intake notifier: reads STORED raw_inbound rows (never the
    # webhook) and sends follow-up questions through the same outbound channel
    # the doctor composer uses. On-demand via POST /api/v1/analyze/stored;
    # optional background poller only when AAHAAR_AI_INTAKE=on.
    intake_worker = IntakeWorker(store, settings, send_func=_intake_send,
                                 interval=getattr(settings, "ai_intake_interval", 15.0))
    if settings.ai_intake:
        intake_worker.start()
        store.audit("system", "ai_intake_start", "AI intake worker enabled")

    # first-run convenience: seed a demo patient so the dashboard has data
    if not store.list_patients():
        seed_demo(store, settings, days=14)
        store.audit("system", "auto_seed", "empty DB seeded with demo patient")

    app = FastAPI(title="Aahaar", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": "0.1.0", "channel": backend.name}

    @app.get("/api/v1/debug/status")
    def debug_status():
        is_cloud = isinstance(backend, CloudBackend)
        phone_id = getattr(backend, "phone_id", "") if is_cloud else "simulator"
        token = getattr(backend, "token", "") if is_cloud else "simulator"
        masked_token = f"{token[:6]}...{token[-4:]}" if len(token) > 12 else ("set" if token else "not_set")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        masked_gemini = f"{gemini_key[:4]}...{gemini_key[-4:]}" if len(gemini_key) > 8 else ("set" if gemini_key else "not_set")

        from ..core.ai import get_last_ai_status
        ai_stat = get_last_ai_status()
        last_dispatch = getattr(backend, "last_dispatch_status", {})
        recent_inbounds = store.raw_inbound_all(limit=5)

        return {
            "ok": True,
            "channel": backend.name,
            "cloud_ready": backend.ready if is_cloud else True,
            "meta_phone_id": (f"...{phone_id[-4:]}" if len(phone_id) > 4 else phone_id) if is_cloud else "simulator",
            "meta_token_configured": bool(token) if is_cloud else True,
            "meta_token_masked": masked_token,
            "gemini_api_key_configured": bool(gemini_key),
            "gemini_key_masked": masked_gemini,
            "ai_status": ai_stat,
            "ai_intake": {
                "enabled": bool(settings.ai_intake),
                "interval": getattr(settings, "ai_intake_interval", 15.0),
                "auto_send": bool(getattr(settings, "ai_intake_auto_send", False)),
                "on_read": bool(getattr(settings, "ai_intake_on_read", True)),
                "on_read_send": bool(getattr(settings, "ai_intake_on_read_send", True)),
                "send_gap": float(getattr(settings, "ai_intake_send_gap", 0.5)),
                "last_run": intake_worker.last_run,
                "last_summary": intake_worker.last_summary,
            },
            "last_dispatch": last_dispatch,
            "recent_raw_inbound_count": len(recent_inbounds),
            "recent_inbounds": recent_inbounds[:3],
            "webhook_events_count": store.webhook_event_count(),
            "last_webhook_event": _parse_whe(store.recent_webhook_events(limit=1)[0] if store.webhook_event_count() else None),
        }

    @app.get("/api/v1/debug/webhooks")
    def debug_webhooks():
        """Inspection endpoint showing exact HTTP callbacks received from Meta WhatsApp."""
        import json as _json
        events = store.recent_webhook_events(limit=50)
        # JSON-encode the detail blob that was stored as text
        for e in events:
            if isinstance(e.get("detail"), str):
                try:
                    e["detail"] = _json.loads(e["detail"])
                except Exception:
                    pass
        return {
            "total_events": store.webhook_event_count(),
            "events": events,
            "meta_verify_token": getattr(backend, "verify_token", "aahaar-verify"),
            "expected_callback_url": "https://aahaar-573f.onrender.com/api/v1/webhooks/whatsapp",
        }

    @app.post("/api/v1/debug/test-gemini")
    def debug_test_gemini(payload: dict | None = None):
        payload = payload or {}
        api_key = payload.get("api_key")
        from ..core.ai import test_gemini_api
        res = test_gemini_api(api_key=api_key)
        status_code = 200 if res.get("success") else 400
        return JSONResponse(res, status_code=status_code)

    @app.post("/api/v1/debug/test-whatsapp")
    def debug_test_whatsapp(payload: dict):
        phone = str(payload.get("phone") or "").strip()
        message = str(payload.get("message") or "Hello from Aahaar diagnostics ping! Your WhatsApp integration is connected.").strip()
        if not phone:
            return JSONResponse({"error": "phone required"}, status_code=400)
        res = backend.test_send(phone, message) if hasattr(backend, "test_send") else {"error": "test_send not supported"}
        status_code = 200 if res.get("success") else 502
        return JSONResponse(res, status_code=status_code)

    @app.post("/api/v1/debug/meta/subscribe")
    def debug_meta_subscribe(payload: dict | None = None):
        payload = payload or {}
        waba_id = str(payload.get("waba_id") or "").strip() or None
        if hasattr(backend, "subscribe_waba"):
            res = backend.subscribe_waba(waba_id=waba_id)
            status_code = 200 if res.get("success") else 400
            store.audit("system", "meta_subscribe_attempt", f"waba={res.get('waba_id')} success={res.get('success')}")
            return JSONResponse(res, status_code=status_code)
        return JSONResponse({"success": False, "error": "Backend does not support subscribe_waba"}, status_code=400)

    @app.post("/api/v1/inbound")
    def inbound(raw: dict, background_tasks: BackgroundTasks):
        replies = ingest.handle(raw)
        background_tasks.add_task(backend.send_bulk, replies)
        return {"replies": [r.body for r in replies], "logged": len(replies)}

    @app.get("/api/v1/webhooks/whatsapp")
    def webhook_verify(
        request: Request,
        mode: str | None = Query(default=None, alias="hub.mode"),
        token: str | None = Query(default=None, alias="hub.verify_token"),
        challenge: str | None = Query(default=None, alias="hub.challenge"),
    ):
        client_ip = request.client.host if request.client else "unknown"
        verified = isinstance(backend, CloudBackend) and backend.verify({"hub.mode": mode,
                                                                 "hub.verify_token": token})
        _record_webhook_event(store, "GET_VERIFY", client_ip, {
            "mode": mode,
            "token_match": verified,
            "challenge_len": len(challenge or ""),
        }, "verified" if verified else "rejected")
        store.audit("webhook", "verify_challenge", f"ip={client_ip} mode={mode} verified={verified}")
        if verified:
            return Response(challenge or "")
        return JSONResponse({"ok": False}, status_code=403)

    @app.post("/api/v1/webhooks/whatsapp")
    async def webhook_inbound(request: Request, background_tasks: BackgroundTasks):
        client_ip = request.client.host if request.client else "unknown"
        try:
            payload = await request.json()
        except Exception as e:
            _record_webhook_event(store, "POST_INBOUND", client_ip, {"error": str(e)}, "invalid_json")
            return JSONResponse({"ok": False, "error": "invalid json"}, status_code=400)

        units = backend.parse_webhook(payload) if hasattr(backend, "parse_webhook") else []
        # Store-first: durable capture BEFORE any processing, idempotent by Meta message id.
        for unit in units:
            src = unit.get("text") or unit.get("photo_path") or f"({unit.get('kind', 'message')})"
            raw_id, duplicate = store.record_raw_received(
                unit.get("sender_phone", ""), src, unit.get("message_id", ""))
            unit["_raw_id"] = raw_id
            unit["_duplicate"] = duplicate
        changes = (payload.get("entry") or [{}])[0].get("changes") or [{}]
        field = changes[0].get("field") if changes else None
        value = changes[0].get("value") or {}
        has_messages = "messages" in value
        has_statuses = "statuses" in value
        duplicates = sum(1 for u in units if u.get("_duplicate"))

        _record_webhook_event(store, "POST_INBOUND", client_ip, {
            "units_count": len(units),
            "duplicates_skipped": duplicates,
            "units": units,
            "field": field,
            "has_messages": has_messages,
            "has_statuses": has_statuses,
        }, "processed" if units else ("status_receipt" if has_statuses else "ignored_field"))
        store.audit("webhook", "inbound_post",
                    f"ip={client_ip} units={len(units)} dup={duplicates} msgs={has_messages} statuses={has_statuses}")

        def _process_unit(u: dict):
            if u.get("_duplicate"):
                return
            try:
                replies = ingest.handle(u)
                backend.send_bulk(replies)
            except Exception as e:
                print(f"[Aahaar] background webhook processing error: {e}")

        for unit in units:
            background_tasks.add_task(_process_unit, unit)
        return {"ok": True, "processed": len(units)}

    @app.get("/api/v1/patients/{pid}/metrics")
    def patient_metrics(pid: int):
        m = latest_metrics(store, settings, pid)
        if not m:
            return JSONResponse({"error": "no window"}, status_code=404)
        return m

    @app.get("/api/v1/patients/{pid}/report")
    def patient_report(pid: int):
        ctx = latest_report_context(store, settings, pid)
        if not ctx:
            return JSONResponse({"error": "no window"}, status_code=404)
        return ctx

    @app.get("/api/v1/patients")
    def patients():
        out = []
        for p in store.list_patients():
            w = store.last_window_for(p["id"])
            cg = store.get_caregiver(p["id"])
            out.append({
                "id": p["id"], "name": p["name"], "uh_id": p["uh_id"],
                "window": (w or {}).get("status"),
                "caregiver": (cg or {}).get("name"),
                "patient_phone": p.get("phone"),
                "caregiver_phone": (cg or {}).get("phone"),
            })
        return out

    @app.post("/api/v1/patients")
    def create_patient(payload: dict, x_aahaar_key: str | None = Header(default=None)):
        """Register a new patient profile with their own phone, logging window, and WhatsApp thread."""
        if (x_aahaar_key or "") != settings.operator_key:
            return JSONResponse({"error": "invalid operator key"}, status_code=403)
        name = str(payload.get("name") or "").strip()
        phone = str(payload.get("phone") or "").strip()
        if not name:
            return JSONResponse({"error": "patient name required"}, status_code=400)
        if not _valid_phone(phone):
            return JSONResponse({"error": "valid phone required"}, status_code=400)
        import random
        from datetime import date, timedelta
        uh_id = payload.get("uh_id") or f"AH-2026-{random.randint(1000, 9999)}"
        pid = store.add_patient(name, uh_id, phone)
        today = date.today()
        wid = store.open_window(pid, today.isoformat(), (today + timedelta(days=14)).isoformat())
        cg_phone = str(payload.get("caregiver_phone") or "").strip()
        if cg_phone and _valid_phone(cg_phone):
            store.set_caregiver_phone(pid, cg_phone)
        try:
            from ..core.process import Outbound
            welcome_msg = (
                f"Namaste {name} ji! Your clinic has connected your Aahaar Glycemic tracker. "
                f"You can send your blood sugar readings (e.g. 'sugar 120') or photos/text of your meals "
                f"(e.g. '2 roti and dal') anytime here. We will prepare your summary for the doctor."
            )
            backend.send(Outbound(route="patient", kind="text", body=welcome_msg, to_phone=phone))
        except Exception as e:
            print("[Aahaar] new patient welcome failed:", e)

        store.audit("operator", "create_patient", f"created patient {pid} ({name}, {phone})")
        return {"ok": True, "id": pid, "name": name, "uh_id": uh_id, "phone": phone, "window_id": wid}

    @app.post("/api/v1/patients/{pid}/linked")
    def link_patient(pid: int, payload: dict,
                     x_aahaar_key: str | None = Header(default=None)):
        if (x_aahaar_key or "") != settings.operator_key:
            return JSONResponse({"error": "invalid operator key"}, status_code=403)
        patient = store.get_patient(pid)
        if not patient:
            return JSONResponse({"error": "no patient"}, status_code=404)
        p_phone = str(payload.get("patient_phone") or "").strip()
        if not _valid_phone(p_phone):
            return JSONResponse({"error": "patient_phone must be a phone number"},
                                status_code=400)
        store.set_patient_phone(pid, p_phone)
        cg_phone = None
        if "caregiver_phone" in payload:
            cg_phone = str(payload["caregiver_phone"] or "").strip()
            if cg_phone:
                if not _valid_phone(cg_phone):
                    return JSONResponse({"error": "caregiver_phone must be a phone number"},
                                        status_code=400)
                store.set_caregiver_phone(pid, cg_phone)
            else:
                store.clear_caregiver(pid)
        store.audit("operator", "link",
                    f"patient {pid} phones updated (patient={p_phone})")
        # Send automated welcome WhatsApp message to patient
        try:
            from ..core.process import Outbound
            welcome_msg = (
                f"Namaste {patient['name']} ji! Your clinic has connected your Aahaar Glycemic tracker. "
                f"You can send your blood sugar readings (e.g. 'sugar 120') or photos/text of your meals "
                f"(e.g. '2 roti and dal') anytime here. We will prepare your summary for the doctor."
            )
            backend.send(Outbound(route="patient", kind="text", body=welcome_msg, to_phone=p_phone))
        except Exception as e:
            print("[Aahaar] link welcome dispatch failed:", e)

        return {"ok": True, "patient_phone": p_phone,
                "caregiver_phone": cg_phone}

    @app.post("/api/v1/patients/{pid}/message")
    def send_direct_message(pid: int, payload: dict,
                            x_aahaar_key: str | None = Header(default=None)):
        """Doctor sends an instant WhatsApp message directly to the patient."""
        if (x_aahaar_key or "") != settings.operator_key:
            return JSONResponse({"error": "invalid operator key"}, status_code=403)
        patient = store.get_patient(pid)
        if not patient or not patient.get("phone"):
            return JSONResponse({"error": "patient has no linked phone number"}, status_code=400)
        body = str(payload.get("message") or "").strip()
        if not body:
            return JSONResponse({"error": "message is empty"}, status_code=400)
        from ..core.process import Outbound
        ok = backend.send(Outbound(route="patient", kind="text", body=body, to_phone=patient["phone"]))
        store.audit("doctor", "direct_message", f"sent to {patient['phone']}: {body[:40]}")
        return {"ok": ok, "sent_to": patient["phone"]}

    @app.get("/api/v1/inbound/live")
    def live_inbound(limit: int = 40):
        """Live feed of all incoming WhatsApp and simulator messages for clinic visibility."""
        if settings.ai_intake_on_read:
            try:
                intake_worker.run_once(
                    limit=8, should_send=settings.ai_intake_on_read_send,
                    send_gap=float(getattr(settings, "ai_intake_send_gap", 0.5)))
            except Exception as e:
                print("[Aahaar] live feed auto-analysis error:", e)
        msgs = store.raw_inbound_all(limit=limit)
        enriched = []
        for m in msgs:
            sender = m.get("sender_phone") or ""
            p_match = store.get_patient_by_phone(sender) if sender else None
            ai_hint = None
            rj = m.get("refined_json") or ""
            if rj:
                try:
                    import json as _json
                    aj = _json.loads(rj)
                    ai_hint = {
                        "intent": aj.get("intent"),
                        "reply": aj.get("reply"),
                        "should_reply": aj.get("should_reply"),
                        "analyzed_by": aj.get("analyzed_by"),
                    }
                except Exception:
                    ai_hint = None
            enriched.append({
                "id": m["id"],
                "ts": m["ts"],
                "sender_phone": sender,
                "role": m.get("role", "patient"),
                "raw_text": m.get("raw_text", ""),
                "status": m.get("status", "received"),
                "patient_id": p_match["id"] if p_match else None,
                "patient_name": p_match["name"] if p_match else "Unlinked / Unknown",
                "ai": ai_hint,
            })
        return {"messages": enriched}

    @app.get("/api/v1/analyze/status")
    def analyze_status():
        """Status of the decoupled AI intake notifier."""
        return {
            "ok": True,
            "enabled": bool(settings.ai_intake),
            "interval": getattr(settings, "ai_intake_interval", 15.0),
            "auto_send": bool(getattr(settings, "ai_intake_auto_send", False)),
            "on_read": bool(getattr(settings, "ai_intake_on_read", True)),
            "on_read_send": bool(getattr(settings, "ai_intake_on_read_send", True)),
            "send_gap": float(getattr(settings, "ai_intake_send_gap", 0.5)),
            "last_run": intake_worker.last_run,
            "last_summary": intake_worker.last_summary,
            "note": "Reads stored raw_inbound only; never runs inside the Meta webhook. Analysis + follow-up push to the patient happen on dashboard reads (send=true, one per message).",
        }

    @app.post("/api/v1/analyze/stored")
    def analyze_stored(payload: dict | None = None, limit: int = 25,
                       x_aahaar_key: str | None = Header(default=None)):
        """On-demand, dashboard-triggered intake analysis over STORED messages.

        Fully decoupled from the WhatsApp webhook: reads raw_inbound rows from
        the DB, writes refined_json, and (when send=true) puts the short
        follow-up question through the same outbound channel the doctor uses.
        """
        if (x_aahaar_key or "") != settings.operator_key:
            return JSONResponse({"error": "invalid operator key"}, status_code=403)
        payload = payload or {}
        limit = max(1, min(int(payload.get("limit") or limit), 200))
        # Analyze-only by default; follow-ups release only when send=true.
        send = bool(payload.get("send", False))
        summary = intake_worker.run_once(
            limit=limit, should_send=send,
            send_gap=float(getattr(settings, "ai_intake_send_gap", 0.5)))
        return {"ok": True, **summary}

    @app.get("/api/v1/patients/{pid}/log")
    def patient_log(pid: int):
        w = store.last_window_for(pid)
        wid = w["id"] if w else None
        p = store.get_patient(pid)
        phone = p.get("phone") if p else None
        return {
            "inbound": store.raw_inbound_log(wid, sender_phone=phone),
            "outbound": store.outbound_log(wid),
            "audit": store.audit_log(),
        }

    @app.post("/api/v1/patients/{pid}/clear-chat")
    def clear_patient_chat(pid: int):
        patient = store.get_patient(pid)
        if not patient:
            return JSONResponse({"error": "not found"}, status_code=404)
        w = store.last_window_for(pid)
        wid = w["id"] if w else None
        with store.tx() as c:
            if wid:
                c.execute("DELETE FROM raw_inbound WHERE window_id=?", (wid,))
                c.execute("DELETE FROM outbound WHERE window_id=?", (wid,))
            phone = patient.get("phone")
            if phone:
                clean = re.sub(r"\D", "", str(phone))
                if clean:
                    c.execute(
                        "DELETE FROM raw_inbound WHERE window_id IS NULL AND (sender_phone LIKE ? OR sender_phone LIKE ?)",
                        (f"%{clean[-10:]}%", f"%{phone}%")
                    )
        store.audit("doctor", "clear_chat", f"cleared chat thread for patient {pid}")
        return {"ok": True, "patient_id": pid}

    @app.post("/api/v1/patients/{pid}/report/build")
    def build_report(pid: int):
        try:
            from ..report import pdf as report_pdf
            from ..report import charts as report_charts
        except ImportError as e:
            return JSONResponse({"error": f"report renderer missing: {e}"}, status_code=500)
        ctx = latest_report_context(store, settings, pid)
        if not ctx:
            return JSONResponse({"error": "no window"}, status_code=404)
        os.makedirs(settings.report_dir, exist_ok=True)
        top_png, bottom_png = report_charts.render(ctx, settings.report_dir)
        pdf_path = report_pdf.render(ctx, settings.report_dir, top_png, bottom_png)
        return {"pdf": pdf_path,
                "top_png": top_png, "bottom_png": bottom_png,
                "metrics": ctx}

    @app.get("/api/v1/patients/{pid}/report/charts")
    def report_charts(pid: int, which: str = "top"):
        if which not in ("top", "bottom"):
            return JSONResponse({"error": "unknown chart"}, status_code=400)
        ctx = latest_report_context(store, settings, pid)
        if not ctx:
            return JSONResponse({"error": "no window"}, status_code=404)
        fn = f"chart-{which}-{pid}.png"
        p = os.path.join(settings.report_dir, fn)
        if not os.path.exists(p):
            return JSONResponse({"error": "report not built yet"}, status_code=404)
        return FileResponse(p, media_type="image/png")

    @app.get("/api/v1/patients/{pid}/report/preview")
    def report_preview(pid: int):
        from ..report.html_preview import render_html
        ctx = latest_report_context(store, settings, pid)
        if not ctx:
            return JSONResponse({"error": "no window"}, status_code=404)
        # make sure the chart PNGs exist so the embedded images never 404
        c_top = os.path.join(settings.report_dir, f"chart-top-{pid}.png")
        c_bot = os.path.join(settings.report_dir, f"chart-bottom-{pid}.png")
        if not (os.path.exists(c_top) and os.path.exists(c_bot)):
            from ..report import charts as report_charts
            os.makedirs(settings.report_dir, exist_ok=True)
            report_charts.render(ctx, settings.report_dir)
        img_base = f"/api/v1/patients/{pid}/report/charts"
        html = render_html(ctx, img_base)
        return {"html": html, "built": os.path.exists(
            os.path.join(settings.report_dir,
                         f"Aahaar-Doctor-Report-{pid}-{ctx['window']['start']}.pdf"))}

    @app.get("/api/v1/patients/{pid}/report/file")
    def report_file(pid: int):
        ctx = latest_report_context(store, settings, pid)
        if not ctx:
            return JSONResponse({"error": "no window"}, status_code=404)
        keep = ctx["window"]
        fn = f"Aahaar-Doctor-Report-{pid}-{keep['start']}.pdf"
        p = os.path.join(settings.report_dir, fn)
        if not os.path.exists(p):
            return JSONResponse({"error": "report not built yet"}, status_code=404)
        return FileResponse(p, media_type="application/pdf", filename=fn)

    @app.post("/api/v1/demo/seed")
    def demo_seed(days: int = 14):
        pid, wid = seed_demo(store, settings, days=days)
        return {"patient_id": pid, "window_id": wid}

    @app.post("/api/v1/nudges")
    def nudges_now():
        due = due_escalations(store, settings)
        for d in due:
            backend.send_bulk([OutboundLike(d)])
        return {"sent": len(due)}

    static_dir = getattr(settings, "static_dir", None)
    if static_dir and os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")

    app.state.store = store
    app.state.backend = backend
    app.state.ingest = ingest
    return app


class OutboundLike:
    """Minimal adapter so nudge dicts can be sent via a backend without geometry."""

    def __init__(self, d: dict):
        self.route = d["route"]
        self.kind = "text"
        self.body = d["body"]
        self.to_phone = d["to_phone"]


app = create_app()