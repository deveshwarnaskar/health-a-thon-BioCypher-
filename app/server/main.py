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

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..config import Settings, get_settings
from ..core.datamodel import Store
from ..core.escalation import due_escalations
from ..core.metrics import latest_metrics
from ..core.report import latest_report_context
from ..core.seed import seed_demo
from ..core.process import IngestService
from .whatsapp import CloudBackend, SimulatorBackend

settings: Settings = get_settings()


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

    # first-run convenience: seed a demo patient so the dashboard has data
    if not store.list_patients():
        seed_demo(store, settings, days=14)
        store.audit("system", "auto_seed", "empty DB seeded with demo patient")

    app = FastAPI(title="Aahaar", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": "0.1.0", "channel": backend.name}

    @app.post("/api/v1/inbound")
    def inbound(raw: dict):
        replies = ingest.handle(raw)
        backend.send_bulk(replies)
        return {"replies": [r.body for r in replies], "logged": len(replies)}

    @app.get("/api/v1/webhooks/whatsapp")
    def webhook_verify(
        mode: str | None = Query(default=None, alias="hub.mode"),
        token: str | None = Query(default=None, alias="hub.verify_token"),
        challenge: str | None = Query(default=None, alias="hub.challenge"),
    ):
        if isinstance(backend, CloudBackend) and backend.verify({"hub.mode": mode,
                                                                 "hub.verify_token": token}):
            return Response(challenge or "")
        return JSONResponse({"ok": False}, status_code=403)

    @app.post("/api/v1/webhooks/whatsapp")
    async def webhook_inbound(request: Request):
        payload = await request.json()
        if not isinstance(backend, CloudBackend):
            return {"ok": False, "note": "channel is simulator"}
        for unit in backend.parse_webhook(payload):
            replies = ingest.handle(unit)
            backend.send_bulk(replies)
        return {"ok": True}

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
            })
        return out

    @app.get("/api/v1/patients/{pid}/log")
    def patient_log(pid: int):
        w = store.last_window_for(pid)
        return {
            "outbound": store.outbound_log(w["id"] if w else None),
            "audit": store.audit_log(),
        }

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