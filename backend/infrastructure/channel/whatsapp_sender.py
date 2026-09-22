"""WhatsApp Cloud API outbound sender (Gate 09 §14).

Infrastructure implementation of the ``ChannelSender`` port using only the
standard library (urllib) — no external SDK is introduced. Sends a template
message (or text fallback) through the Meta Graph API::

    POST https://graph.facebook.com/{version}/{phone_number_id}/messages

Translation of transport outcomes is intentional and PHI-free:
success → provider delivery id; 4xx → permanent; 5xx/timeout → retryable.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from backend.application.ops.contracts import DeliveryResult, OutboundMessage
from backend.application.ops.ports import ChannelSender

logger = logging.getLogger(__name__)


class WhatsAppChannelSender:
    """Meta WhatsApp Cloud API channel sender (urllib-only)."""

    GRAPH_BASE_URL = "https://graph.facebook.com"

    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        api_version: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        token = access_token
        p_id = phone_number_id
        version = api_version

        if token is None or p_id is None or version is None:
            try:
                from config.settings import Settings

                s = Settings()
                if token is None:
                    token = s.whatsapp.access_token
                if p_id is None:
                    p_id = s.whatsapp.phone_number_id
                if version is None:
                    version = s.whatsapp.api_version
            except Exception:
                pass

        self._access_token = token or ""
        self._phone_number_id = p_id or ""
        self._base_url = (base_url or self.GRAPH_BASE_URL).rstrip("/")
        self._api_version = version or "v25.0"
        self._timeout = timeout_seconds

    def send(self, message: OutboundMessage) -> DeliveryResult:
        if not self._access_token or not self._phone_number_id:
            logger.error("whatsapp credentials missing — delivery failed safe")
            return DeliveryResult(
                success=False,
                error_code="CREDENTIALS_MISSING",
                retryable=False,
            )

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.recipient_phone.lstrip("+").strip(),
        }

        interactive_type = message.template_params.get("interactive_type")
        if interactive_type == "button":
            # Interactive button message
            button_1 = message.template_params.get("button_1", "Yes / Haan")
            button_2 = message.template_params.get("button_2", "Cancel / Radd")
            payload["type"] = "interactive"
            payload["interactive"] = {
                "type": "button",
                "body": {"text": message.template_params.get("body", message.template_name)},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": message.template_params.get("button_1_id", "btn_confirm"),
                                "title": button_1[:20],
                            },
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": message.template_params.get("button_2_id", "btn_cancel"),
                                "title": button_2[:20],
                            },
                        },
                    ]
                },
            }
        elif message.template_name and message.template_name not in ("text", "direct", "raw"):
            # Template message
            body_params = [
                {"type": "text", "text": str(value)}
                for key, value in message.template_params.items()
                if not key.startswith("_") and key != "body"
            ]
            lang = message.template_params.get("_language", "en")
            payload["type"] = "template"
            components = []
            if body_params:
                components.append({"type": "body", "parameters": body_params})
            payload["template"] = {
                "name": message.template_name,
                "language": {"code": lang},
            }
            if components:
                payload["template"]["components"] = components
        else:
            # Plain text message
            payload["type"] = "text"
            payload["text"] = {
                "preview_url": False,
                "body": message.template_params.get("body", message.template_name),
            }

        url = f"{self._base_url}/{self._api_version}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "User-Agent": "THALI-PLATE/1.0",
        }
        if message.correlation_id:
            headers["X-Correlation-ID"] = str(message.correlation_id)

        if not url.startswith(("https://", "http://")):
            raise ValueError("URL must use http or https scheme")

        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # nosec B310
                raw_resp = response.read().decode("utf-8")
                body = json.loads(raw_resp) if raw_resp else {}
        except urllib.error.HTTPError as exc:
            status = exc.code
            meta_code = None
            meta_subcode = None
            fbtrace_id = None
            try:
                err_text = exc.read().decode("utf-8")
                err_json = json.loads(err_text)
                meta_err = err_json.get("error", {})
                meta_code = meta_err.get("code")
                meta_subcode = meta_err.get("error_subcode")
                fbtrace_id = meta_err.get("fbtrace_id")
            except Exception:
                pass

            # Classification: retryable vs permanent (PHI-safe logging)
            is_rate_limited = status == 429 or meta_code in (130429, 80007, 4)
            is_transient_service = status >= 500 or meta_code in (131009, 131016, 1, 2)
            retryable = is_rate_limited or is_transient_service

            err_code = (
                f"meta_code_{meta_code}"
                if meta_code is not None
                else f"provider_{'transient' if retryable else 'rejected'}_{status}"
            )

            logger.warning(
                "whatsapp outbound failed: status=%d meta_code=%s meta_subcode=%s fbtrace_id=%s retryable=%s",
                status,
                meta_code,
                meta_subcode,
                fbtrace_id,
                retryable,
            )
            self._record_failure(err_code)
            return DeliveryResult(success=False, error_code=err_code, retryable=retryable)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("whatsapp send transport failure: %s", type(exc).__name__)
            self._record_failure("transport_error")
            return DeliveryResult(success=False, error_code="transport_error", retryable=True)
        except json.JSONDecodeError as exc:
            logger.warning("whatsapp send unparseable response: %s", exc)
            self._record_failure("unparseable_response")
            return DeliveryResult(success=False, error_code="unparseable_response", retryable=True)

        messages = (body or {}).get("messages") or []
        provider_id = messages[0].get("id") if messages else None
        result = DeliveryResult(success=True, provider_delivery_id=provider_id)
        try:
            from backend.infrastructure.observability.metrics import get_metrics_registry

            reg = get_metrics_registry()
            reg.counter("whatsapp_deliveries_total").inc(outcome="success")
            reg.gauge("dependency_health_status").set(1, dependency="whatsapp")
        except Exception:
            pass
        return result

    def _record_failure(self, error_code: str) -> None:
        try:
            from backend.infrastructure.observability.metrics import get_metrics_registry

            reg = get_metrics_registry()
            reg.counter("whatsapp_deliveries_total").inc(outcome="failure")
            reg.gauge("dependency_health_status").set(0, dependency="whatsapp")
            reg.counter("dependency_failures_total").inc(dependency="whatsapp", error_type=error_code)
        except Exception:
            pass

    def download_media(self, media_id: str) -> tuple[bytes, str] | None:
        """Download media bytes and mime-type from Meta Graph API using the sender's access token."""
        if not self._access_token or not media_id:
            return None

        meta_url = f"{self._base_url}/{self._api_version}/{media_id}"
        req1 = urllib.request.Request(
            meta_url,
            headers={"Authorization": f"Bearer {self._access_token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req1, timeout=self._timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                download_url = data.get("url")
                mime_type = data.get("mime_type", "audio/ogg")
                if not download_url:
                    return None

            req2 = urllib.request.Request(
                download_url,
                headers={"Authorization": f"Bearer {self._access_token}"},
                method="GET",
            )
            with urllib.request.urlopen(req2, timeout=self._timeout) as resp2:
                media_bytes = resp2.read()
                return media_bytes, mime_type
        except Exception as exc:
            logger.warning("failed to download whatsapp media %s: %s", media_id, exc)
            return None


__all__ = ["WhatsAppChannelSender"]