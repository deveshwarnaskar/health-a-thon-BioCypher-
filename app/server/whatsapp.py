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

    def subscribe_waba(self, waba_id: Optional[str] = None) -> dict:
        return {"success": True, "waba_id": waba_id or "simulator-waba", "message": "Simulator backend: WABA webhook subscribed."}

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
                    unit = {"sender_phone": str(from_).strip(),
                            "message_id": str(msg.get("id") or ""),
                            "ts": datetime.now().isoformat()}
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
    last_dispatch_status: dict = {"status": "simulator_ready", "ts": None}

    def send(self, out: Outbound) -> bool:
        wid = self._window_id_for(out.to_phone)
        self.store.record_outbound(wid, out.route, out.kind, out.body)
        print(f"[Aahaar -> {out.to_phone}] ({out.kind}) {out.body}")
        self.last_dispatch_status = {
            "status": "success",
            "ts": datetime.now().isoformat(),
            "http_code": 200,
            "error": None,
            "to": out.to_phone,
        }
        return True

    def test_send(self, to_phone: str, message: str = "Test ping from Aahaar") -> dict:
        return {
            "success": True,
            "http_code": 200,
            "to": to_phone,
            "response": f"Simulated delivery: {message}",
        }

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
        self.waba_id = os.environ.get("META_WABA_ID", "")
        self.last_dispatch_status: dict = {
            "status": "idle",
            "ts": None,
            "http_code": None,
            "error": None,
            "to": None,
        }

    @property
    def ready(self) -> bool:
        return bool(self.phone_id and self.token)

    def test_send(self, to_phone: str, message: str = "Test ping from Aahaar") -> dict:
        clean_to = re.sub(r"\D", "", str(to_phone))
        if not self.ready:
            return {
                "success": False,
                "error": "CloudBackend not ready: META_PHONE_ID or META_TOKEN is not configured.",
                "phone_id_set": bool(self.phone_id),
                "token_set": bool(self.token),
            }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_to,
            "type": "text",
            "text": {"body": message},
        }
        url = GRAPH + f"/{self.phone_id}/messages"
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=8) as r:
                body = r.read().decode()
                try:
                    data = json.loads(body)
                except Exception:
                    data = body
                self.last_dispatch_status = {
                    "status": "success",
                    "ts": datetime.now().isoformat(),
                    "http_code": r.status,
                    "error": None,
                    "to": clean_to,
                }
                return {
                    "success": r.status == 200,
                    "http_code": r.status,
                    "to": clean_to,
                    "response": data,
                }
        except urllib.error.HTTPError as e:
            err_msg = ""
            try:
                err_msg = e.read().decode()
            except Exception:
                pass
            try:
                err_json = json.loads(err_msg)
            except Exception:
                err_json = err_msg or str(e)
            self.last_dispatch_status = {
                "status": "error",
                "ts": datetime.now().isoformat(),
                "http_code": e.code,
                "error": err_json,
                "to": clean_to,
            }
            return {
                "success": False,
                "http_code": e.code,
                "to": clean_to,
                "error": err_json,
            }
        except Exception as e:
            self.last_dispatch_status = {
                "status": "exception",
                "ts": datetime.now().isoformat(),
                "http_code": None,
                "error": str(e),
                "to": clean_to,
            }
            return {
                "success": False,
                "http_code": None,
                "to": clean_to,
                "error": str(e),
            }

    def subscribe_waba(self, waba_id: Optional[str] = None) -> dict:
        if not self.ready:
            return {"success": False, "error": "CloudBackend not ready: missing META_PHONE_ID or META_TOKEN"}

        detected_waba = (waba_id or self.waba_id or "").strip() or None
        diag: dict = {}

        def _get_meta(path: str) -> tuple[Optional[dict], Optional[str]]:
            try:
                url = GRAPH + path
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    return json.loads(r.read().decode()), None
            except urllib.error.HTTPError as e:
                err_text = ""
                try:
                    err_text = e.read().decode()
                    return None, json.loads(err_text)
                except Exception:
                    return None, err_text or str(e)
            except Exception as e:
                return None, str(e)

        # Step 0: Verify phone connectivity
        if self.phone_id:
            pinfo, perr = _get_meta(f"/{self.phone_id}?fields=id,display_phone_number,verified_name,status")
            if pinfo:
                diag["phone_info"] = pinfo
            elif perr:
                diag["phone_err"] = perr

        # Step 1: Inspect token details (scopes, app_id, user_id, target_ids)
        app_id = None
        user_id = None
        tinfo, terr = _get_meta(f"/debug_token?input_token={self.token}")
        if tinfo:
            diag["token_details"] = tinfo
            tdata = tinfo.get("data", {})
            app_id = tdata.get("app_id")
            user_id = tdata.get("user_id")
            if not detected_waba:
                for sc in tdata.get("granular_scopes", []):
                    if sc.get("target_ids"):
                        detected_waba = str(sc["target_ids"][0])
                        diag["detected_via"] = "granular_scopes"
                        break
        elif terr:
            diag["token_err"] = terr

        # Step 2: Query /me?fields=businesses
        if not detected_waba:
            me_info, me_err = _get_meta("/me?fields=id,name,businesses{id,name,owned_whatsapp_business_accounts{id,name}}")
            if me_info:
                diag["me_info"] = me_info
                for b in me_info.get("businesses", {}).get("data", []):
                    wlist = b.get("owned_whatsapp_business_accounts", {}).get("data", [])
                    if wlist and wlist[0].get("id"):
                        detected_waba = str(wlist[0]["id"])
                        diag["detected_via"] = "me.businesses.owned_waba"
                        break
            elif me_err:
                diag["me_err"] = me_err

        # Step 3: Query /me/businesses edge directly
        if not detected_waba:
            biz_info, biz_err = _get_meta("/me/businesses")
            if biz_info:
                diag["biz_list"] = biz_info.get("data", [])
                for b in biz_info.get("data", []):
                    bid = b.get("id")
                    if not bid:
                        continue
                    w_info, _ = _get_meta(f"/{bid}/owned_whatsapp_business_accounts")
                    if w_info and w_info.get("data"):
                        detected_waba = str(w_info["data"][0]["id"])
                        diag["detected_via"] = f"biz_{bid}_owned_waba"
                        break
            elif biz_err:
                diag["biz_err"] = biz_err

        # Step 4: Query /{app_id}/whatsapp_business_accounts if app_id known
        if not detected_waba and app_id:
            app_waba, app_err = _get_meta(f"/{app_id}/whatsapp_business_accounts")
            if app_waba and app_waba.get("data"):
                detected_waba = str(app_waba["data"][0]["id"])
                diag["detected_via"] = "app_waba"
            elif app_err:
                diag["app_waba_err"] = app_err

        # Step 5: Query /{user_id}/businesses if user_id known
        if not detected_waba and user_id:
            u_biz, u_err = _get_meta(f"/{user_id}/businesses")
            if u_biz and u_biz.get("data"):
                diag["user_biz"] = u_biz.get("data")
                for b in u_biz.get("data", []):
                    bid = b.get("id")
                    if not bid:
                        continue
                    w_info, _ = _get_meta(f"/{bid}/owned_whatsapp_business_accounts")
                    if w_info and w_info.get("data"):
                        detected_waba = str(w_info["data"][0]["id"])
                        diag["detected_via"] = f"user_biz_{bid}_owned_waba"
                        break
            elif u_err:
                diag["user_biz_err"] = u_err

        if not detected_waba:
            return {
                "success": False,
                "need_waba_id": True,
                "error": "Could not auto-detect WABA ID. Please copy your WhatsApp Business Account ID from Meta Developer Portal -> WhatsApp -> API Setup, enter it into the WABA ID field, and click Subscribe.",
                "diagnostics": diag,
            }

        # Step 6: Call POST /{detected_waba}/subscribed_apps to register webhooks
        try:
            url = GRAPH + f"/{detected_waba}/subscribed_apps"
            req = urllib.request.Request(url, data=b"", headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                res_body = r.read().decode()
                try:
                    res_json = json.loads(res_body)
                except Exception:
                    res_json = res_body
                return {
                    "success": True,
                    "waba_id": detected_waba,
                    "response": res_json,
                    "message": f"Successfully subscribed Meta App to WhatsApp Business Account {detected_waba} webhooks!",
                    "diagnostics": diag,
                }
        except urllib.error.HTTPError as e:
            err = ""
            try:
                err = e.read().decode()
            except Exception:
                pass
            try:
                err_json = json.loads(err)
            except Exception:
                err_json = err or str(e)
            return {
                "success": False,
                "waba_id": detected_waba,
                "http_code": e.code,
                "error": err_json,
                "diagnostics": diag,
            }
        except Exception as e:
            return {
                "success": False,
                "waba_id": detected_waba,
                "error": str(e),
                "diagnostics": diag,
            }

    def send(self, out: Outbound) -> bool:
        to = self._bind_route_phone(out, self.phone_ids)
        clean_to = re.sub(r"\D", "", str(to))
        # Always record outbound in clinic database for real-time audit and doctor dashboard
        self.store.record_outbound(self._window_id_for(to), out.route, out.kind, out.body)
        if not self.ready:
            print("[Aahaar] cloud backend not configured — message dropped from Meta dispatch:", out.body[:60])
            self.last_dispatch_status = {
                "status": "dropped_not_ready",
                "ts": datetime.now().isoformat(),
                "error": "CloudBackend not configured (missing phone_id or token)",
                "to": clean_to,
            }
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
        to = payload.get("to")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                success = (r.status == 200)
                self.last_dispatch_status = {
                    "status": "success" if success else "error",
                    "ts": datetime.now().isoformat(),
                    "http_code": r.status,
                    "error": None,
                    "to": to,
                }
                return success
        except urllib.error.HTTPError as e:
            err_msg = ""
            try:
                err_msg = e.read().decode()
            except Exception:
                pass
            print(f"[Aahaar] cloud send HTTP {e.code} failed: {err_msg or e}")
            self.last_dispatch_status = {
                "status": "error",
                "ts": datetime.now().isoformat(),
                "http_code": e.code,
                "error": err_msg or str(e),
                "to": to,
            }
            return False
        except Exception as e:
            print("[Aahaar] cloud send failed:", e)
            self.last_dispatch_status = {
                "status": "exception",
                "ts": datetime.now().isoformat(),
                "http_code": None,
                "error": str(e),
                "to": to,
            }
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