"""Unit tests for Meta WhatsApp Cloud API Sender and Webhook parsing."""

from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.application.ops.contracts import OutboundMessage
from backend.infrastructure.channel.whatsapp_sender import WhatsAppChannelSender
from backend.interfaces.http.v2.webhooks.router import _parse_delivery


class TestWhatsAppChannelSender:
    """Tests for outbound WhatsApp Cloud API sending using urllib."""

    def test_missing_credentials_fails_safe(self):
        sender = WhatsAppChannelSender(access_token="", phone_number_id="")
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": "Hello"},
        )
        res = sender.send(msg)
        assert res.success is False
        assert res.error_code == "CREDENTIALS_MISSING"
        assert res.retryable is False

    @patch("urllib.request.urlopen")
    def test_successful_text_send(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "messaging_product": "whatsapp",
            "contacts": [{"input": "919876543210", "wa_id": "919876543210"}],
            "messages": [{"id": "wamid.HBgLMDExMQ=="}],
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        sender = WhatsAppChannelSender(
            access_token="test-token",
            phone_number_id="1273367152534156",
            api_version="v25.0",
        )
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": "Glucose reading 140 mg/dL recorded."},
            correlation_id="corr-123",
        )

        res = sender.send(msg)
        assert res.success is True
        assert res.provider_delivery_id == "wamid.HBgLMDExMQ=="

        # Verify request parameters
        req = mock_urlopen.call_args[0][0]
        assert req.get_full_url() == "https://graph.facebook.com/v25.0/1273367152534156/messages"
        assert req.headers["Authorization"] == "Bearer test-token"
        assert req.headers["X-correlation-id"] == "corr-123"

        payload = json.loads(req.data.decode("utf-8"))
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "919876543210"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Glucose reading 140 mg/dL recorded."

    @patch("urllib.request.urlopen")
    def test_interactive_button_payload_formatting(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "messages": [{"id": "wamid.BUTTON123"}],
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        sender = WhatsAppChannelSender(
            access_token="test-token",
            phone_number_id="1273367152534156",
            api_version="v25.0",
        )
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={
                "body": "Confirm meal: 2 roti dal?",
                "interactive_type": "button",
                "button_1": "Yes / Haan",
                "button_2": "Cancel / Radd",
                "button_1_id": "confirm_yes",
                "button_2_id": "confirm_cancel",
            },
        )

        res = sender.send(msg)
        assert res.success is True

        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["type"] == "interactive"
        assert payload["interactive"]["type"] == "button"
        assert payload["interactive"]["body"]["text"] == "Confirm meal: 2 roti dal?"
        buttons = payload["interactive"]["action"]["buttons"]
        assert len(buttons) == 2
        assert buttons[0]["reply"]["title"] == "Yes / Haan"
        assert buttons[1]["reply"]["title"] == "Cancel / Radd"

    @patch("urllib.request.urlopen")
    def test_meta_rate_limit_error_is_retryable(self, mock_urlopen):
        error_body = json.dumps({
            "error": {
                "message": "(#130429) Rate limit hit",
                "type": "OAuthException",
                "code": 130429,
                "fbtrace_id": "trace-rate-limit",
            }
        }).encode("utf-8")

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://graph.facebook.com/v25.0/messages",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=io.BytesIO(error_body),
        )

        sender = WhatsAppChannelSender(access_token="token", phone_number_id="123")
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": "Hello"},
        )
        res = sender.send(msg)
        assert res.success is False
        assert res.retryable is True
        assert res.error_code == "meta_code_130429"

    @patch("urllib.request.urlopen")
    def test_meta_expired_token_error_is_permanent(self, mock_urlopen):
        error_body = json.dumps({
            "error": {
                "message": "Error validating access token: Session has expired",
                "type": "OAuthException",
                "code": 190,
                "error_subcode": 463,
                "fbtrace_id": "trace-token-expired",
            }
        }).encode("utf-8")

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://graph.facebook.com/v25.0/messages",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(error_body),
        )

        sender = WhatsAppChannelSender(access_token="token", phone_number_id="123")
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": "Hello"},
        )
        res = sender.send(msg)
        assert res.success is False
        assert res.retryable is False
        assert res.error_code == "meta_code_190"

    @patch("urllib.request.urlopen")
    def test_meta_undeliverable_template_required_is_permanent(self, mock_urlopen):
        error_body = json.dumps({
            "error": {
                "message": "(#131026) Message undeliverable",
                "type": "OAuthException",
                "code": 131026,
                "fbtrace_id": "trace-undeliverable",
            }
        }).encode("utf-8")

        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://graph.facebook.com/v25.0/messages",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=io.BytesIO(error_body),
        )

        sender = WhatsAppChannelSender(access_token="token", phone_number_id="123")
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": "Hello"},
        )
        res = sender.send(msg)
        assert res.success is False
        assert res.retryable is False
        assert res.error_code == "meta_code_131026"

    @patch("urllib.request.urlopen")
    def test_transport_timeout_is_retryable(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        sender = WhatsAppChannelSender(access_token="token", phone_number_id="123")
        msg = OutboundMessage(
            message_id=uuid4(),
            tenant_id=uuid4(),
            recipient_phone="+919876543210",
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": "Hello"},
        )
        res = sender.send(msg)
        assert res.success is False
        assert res.retryable is True
        assert res.error_code == "transport_error"


class TestWebhookDeliveryParsing:
    """Tests for inbound Webhook delivery parsing with rich Meta payloads."""

    APP_SECRET = "test-secret"

    def test_parse_inbound_text_message(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1622425102928569",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550254483",
                                    "phone_number_id": "1273367152534156",
                                },
                                "messages": [
                                    {
                                        "from": "919876543210",
                                        "id": "wamid.HBgLMDExMQ==",
                                        "timestamp": "1710000000",
                                        "text": {"body": "140 fasting"},
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

        raw = json.dumps(payload).encode("utf-8")
        delivery = _parse_delivery(raw, self.APP_SECRET)

        assert delivery.provider_message_id == "wamid.HBgLMDExMQ=="
        assert delivery.source_phone == "919876543210"
        assert delivery.event_type == "message_received"
        assert delivery.text == "140 fasting"
        assert delivery.recipient_phone_number_id == "1273367152534156"
        assert delivery.timestamp == 1710000000
        assert delivery.message_type == "text"

    def test_parse_interactive_button_reply(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "1273367152534156"},
                                "messages": [
                                    {
                                        "from": "919876543210",
                                        "id": "wamid.BTN_REPLY",
                                        "timestamp": "1710000010",
                                        "type": "interactive",
                                        "interactive": {
                                            "type": "button_reply",
                                            "button_reply": {
                                                "id": "confirm_yes",
                                                "title": "Yes / Haan",
                                            },
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        raw = json.dumps(payload).encode("utf-8")
        delivery = _parse_delivery(raw, self.APP_SECRET)

        assert delivery.provider_message_id == "wamid.BTN_REPLY"
        assert delivery.source_phone == "919876543210"
        assert delivery.text == "Yes / Haan"
        assert delivery.message_type == "interactive"
        assert delivery.interactive_reply_id == "confirm_yes"

    def test_parse_media_image_message(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "1273367152534156"},
                                "messages": [
                                    {
                                        "from": "919876543210",
                                        "id": "wamid.MEDIA_IMG",
                                        "timestamp": "1710000020",
                                        "type": "image",
                                        "image": {
                                            "id": "media-file-999",
                                            "mime_type": "image/jpeg",
                                            "caption": "plate of food",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        raw = json.dumps(payload).encode("utf-8")
        delivery = _parse_delivery(raw, self.APP_SECRET)

        assert delivery.provider_message_id == "wamid.MEDIA_IMG"
        assert delivery.message_type == "image"
        assert delivery.media_id == "media-file-999"
        assert delivery.caption == "plate of food"
        assert delivery.text == "plate of food"

    def test_parse_status_delivered_receipt(self):
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "1273367152534156"},
                                "statuses": [
                                    {
                                        "id": "wamid.STATUS_MSG",
                                        "status": "delivered",
                                        "timestamp": "1710000030",
                                        "recipient_id": "919876543210",
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        raw = json.dumps(payload).encode("utf-8")
        delivery = _parse_delivery(raw, self.APP_SECRET)

        assert delivery.provider_message_id == "wamid.STATUS_MSG"
        assert delivery.event_type == "status_received"
        assert delivery.source_phone == "919876543210"
        assert delivery.message_type == "status"


class TestIntentFirewall:
    """Tests for IntentFirewall classification and guidance messages."""

    def test_glucose_reading_classification(self):
        from backend.infrastructure.parsing.intent_firewall import IntentFirewall, IntentType

        v = IntentFirewall.evaluate("140 fasting")
        assert v.intent == IntentType.GLUCOSE_LOG
        assert v.is_supported is True

        v2 = IntentFirewall.evaluate("aaj subah 8 am 135")
        assert v2.intent == IntentType.GLUCOSE_LOG
        assert v2.is_supported is True

    def test_meal_logging_classification(self):
        from backend.infrastructure.parsing.intent_firewall import IntentFirewall, IntentType

        v = IntentFirewall.evaluate("2 roti aur dal sabzi")
        assert v.intent == IntentType.MEAL_LOG
        assert v.is_supported is True

    def test_confirm_classification(self):
        from backend.infrastructure.parsing.intent_firewall import IntentFirewall, IntentType

        for text in ("yes", "haan", "ha", "theek hai", "ji haan", "done"):
            v = IntentFirewall.evaluate(text)
            assert v.intent == IntentType.CONFIRM
            assert v.is_supported is True

    def test_cancel_classification(self):
        from backend.infrastructure.parsing.intent_firewall import IntentFirewall, IntentType

        for text in ("cancel", "radd", "chhod do", "cancel meal"):
            v = IntentFirewall.evaluate(text)
            assert v.intent == IntentType.CANCEL
            assert v.is_supported is True
            assert v.guidance_message is not None

    def test_help_classification(self):
        from backend.infrastructure.parsing.intent_firewall import IntentFirewall, IntentType

        for text in ("help", "madad", "kaise use karein", "commands"):
            v = IntentFirewall.evaluate(text)
            assert v.intent == IntentType.HELP
            assert v.is_supported is True
            assert v.guidance_message is not None

    def test_unsupported_queries_blocked(self):
        from backend.infrastructure.parsing.intent_firewall import IntentFirewall, IntentType

        unsupported_inputs = (
            "can you write a poem about autumn leaves?",
            "what is the weather like in Mumbai today?",
            "def quicksort(arr): return arr",
            "tell me a joke about doctors",
            "who is the president of France?",
            "buy bitcoin or ethereum cryptocurrency",
        )
        for text in unsupported_inputs:
            v = IntentFirewall.evaluate(text)
            assert v.intent == IntentType.UNSUPPORTED
            assert v.is_supported is False
            assert "health assistant" in v.guidance_message.lower()
