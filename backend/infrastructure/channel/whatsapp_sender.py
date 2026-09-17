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
        api_version: str = "v21.0",
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._access_token = access_token or ""
        self._phone_number_id = phone_number_id or ""
        self._base_url = base_url or self.GRAPH_BASE_URL
        self._api_version = api_version
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
            "to": message.recipient_phone,
        }
        if message.channel_type == "WHATSAPP":
            if message.template_name and message.template_params:
                payload["type"] = "template"
                payload["template"] = {
                    "name": message.template_name,
                    "language": {"code": "en"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": str(value)}
                                for value in message.template_params.values()
                            ],
                        }
                    ],
                }
            else:
                payload["type"] = "text"
                payload["text"] = {"body": message.template_params.get("body", message.template_name)}
        else:
            payload["type"] = "text"
            payload["text"] = {"body": message.template_params.get("body", message.template_name)}

        url = f"{self._base_url}/{self._api_version}/{self._phone_number_id}/messages"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                response.raise_for_status() if hasattr(response, "raise_for_status") else None
        except urllib.error.HTTPError as exc:
            status = exc.code
            if 400 <= status < 500:
                return DeliveryResult(success=False, error_code=f"provider_rejected_{status}", retryable=False)
            return DeliveryResult(success=False, error_code=f"provider_transient_{status}", retryable=True)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("whatsapp send transient failure: %s", exc)
            return DeliveryResult(success=False, error_code="transport_error", retryable=True)
        except json.JSONDecodeError as exc:
            logger.warning("whatsapp send unparseable response: %s", exc)
            return DeliveryResult(success=False, error_code="unparseable_response", retryable=True)

        messages = (body or {}).get("messages") or []
        provider_id = messages[0].get("id") if messages else None
        return DeliveryResult(success=True, provider_delivery_id=provider_id)


__all__ = ["WhatsAppChannelSender"]