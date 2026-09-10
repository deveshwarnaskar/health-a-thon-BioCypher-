"""Channel abstraction: the pipeline talks to *a* WhatsApp backend, never calls
Meta directly.

Two plug-ins:
  * SimulatorBackend — zero-config, logs everything to the `outbound` table and
    prints a neat console transcript; perfect for the demo and the tests.
  * CloudBackend      — real Meta WhatsApp Cloud API over HTTPS. Only used when
    AAHAAR_WHATSAPP=cloud and a token + phone number ID are configured (Phase 5).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

from ..config import Settings
from ..core.datamodel import Store
from ..core.process import Outbound

GRAPH = "https://graph.facebook.com/v21.0"


class _Base:
    def __init__(self, store: Store, cfg: Settings, phone_ids: Optional[dict] = None):
        self.store = store
        self.cfg = cfg
        self.phone_ids = phone_ids or {}

    def _window_id_for(self, phone: str) -> Optional[int]:
        p = self.store.get_patient_by_phone(phone)
        if not p:
            return None
        w = self.store.last_window_for(p["id"])
        return w["id"] if w else None

    def _bind_route_phone(self, out: Outbound, phone_ids: dict) -> str:
        return str(phone_ids.get(out.to_phone, out.to_phone))

    def parse_webhook(self, payload: dict) -> list[dict]:
        """Flatten Meta's webhook payload into the pipeline's neutral wire-format."""
        out = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") != "messages":
                    continue
                value = change.get("value", {})
                contacts = value.get("contacts") or []
                contact_wa = contacts[0].get("wa_id") if contacts else None
                for msg in value.get("messages", []):
                    from_ = msg.get("from") or contact_wa
                    if not from_:
                        continue
                    kind = msg.get("type")
                    unit = {"sender_phone": str(from_).strip(), "ts": datetime.now().isoformat()}
                    if kind == "text":
                        unit["kind"] = "text"
                        unit["text"] = msg.get("text", {}).get("body", "")
                    elif kind == "image":
                        if msg.get("image", {}).get("id") and hasattr(self, "_media_exists") and self._media_exists(msg["image"]["id"]):
                            unit["kind"] = "photo"
                            unit["photo_path"] = self.download_media(msg["image"]["id"]) if hasattr(self, "download_media") else None
                        else:
                            unit["kind"] = "photo"
                            unit["photo_path"] = None
                    elif kind == "voice":
                        unit["kind"] = "text"
                        unit["text"] = "(voice — STT plug-in)"
                    elif kind == "button":
                        unit["kind"] = "text"
                        unit["text"] = msg.get("button", {}).get("text", "")
                    elif kind == "interactive":
                        inter = msg.get("interactive", {})
                        btn = inter.get("button_reply", {}).get("title") or inter.get("list_reply", {}).get("title", "")
                        unit["kind"] = "text"
                        unit["text"] = btn
                    else:
                        continue
                    out.append(unit)
        return out


class SimulatorBackend(_Base):
    name = "simulator"

    def send(self, out: Outbound) -> bool:
        wid = self._window_id_for(out.to_phone)
        self.store.record_outbound(wid, out.route, out.kind, out.body)
        print(f"[Aahaar -> {out.to_phone}] ({out.kind}) {out.body}")
        return True

    def send_bulk(self, outs: list[Outbound]) -> int:
        n = 0
        for o in outs:
            n += 1 if self.send(o) else 0
        return n


class CloudBackend(_Base):
    """Minimal Meta WhatsApp Cloud API client (test-environment friendly).

    Configuration (environment variables, set before launch):
        AAHAAR_WHATSAPP=cloud
        META_PHONE_ID       the sender test number ID from the phone tile
        META_TOKEN          the 24-hour access token from the get-started flow
        META_VERIFY         a string you choose for webhook verification
    """
    name = "cloud"

    def __init__(self, store, cfg, phone_ids=None):
        super().__init__(store, cfg, phone_ids)
        self.phone_id = os.environ.get("META_PHONE_ID", "")
        self.token = os.environ.get("META_TOKEN", "")
        self.verify_token = os.environ.get("META_VERIFY", "aahaar-verify")

    @property
    def ready(self) -> bool:
        return bool(self.phone_id and self.token)

    def send(self, out: Outbound) -> bool:
        to = self._bind_route_phone(out, self.phone_ids)
        clean_to = re.sub(r"\D", "", str(to))
        # Always record outbound in clinic database for real-time audit and doctor dashboard
        self.store.record_outbound(self._window_id_for(to), out.route, out.kind, out.body)
        if not self.ready:
            print("[Aahaar] cloud backend not configured — message dropped from Meta dispatch:", out.body[:60])
            return False
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_to,
            "type": "text",
            "text": {"body": out.body},
        }
        return self._post(f"/{self.phone_id}/messages", payload)

    def send_bulk(self, outs: list[Outbound]) -> int:
        n = 0
        for o in outs:
            n += 1 if self.send(o) else 0
        return n

    def verify(self, query: dict) -> bool:
        return (query.get("hub.mode") == "subscribe"
                and query.get("hub.verify_token") == self.verify_token)



    def download_media(self, media_id: str, path: Optional[str] = None) -> Optional[str]:
        url = self._get(f"/{media_id}")
        if not url:
            return None
        path = path or f"/tmp/aahaar-media-{media_id}.bin"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=20) as r:
            with open(path, "wb") as f:
                f.write(r.read())
        return path

    def _post(self, path: str, payload: dict) -> bool:
        url = GRAPH + path
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status == 200
        except urllib.error.HTTPError as e:
            err_msg = ""
            try:
                err_msg = e.read().decode()
            except Exception:
                pass
            print(f"[Aahaar] cloud send HTTP {e.code} failed: {err_msg or e}")
            return False
        except Exception as e:
            print("[Aahaar] cloud send failed:", e)
            return False

    def _get(self, path: str) -> Optional[str]:
        url = GRAPH + path
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return urllib.parse.unquote(r.read().decode())
        except urllib.error.URLError as e:
            print("[Aahaar] cloud fetch failed:", e)
            return None

    def _media_exists(self, media_id: str) -> bool:
        # prototypes: media fetch happens at ingest; treat id presence as enough
        return bool(media_id)