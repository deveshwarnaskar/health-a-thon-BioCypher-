"""Tests for Observability and Privacy-Preserving Structured Logging (Gate 05).

Verifies:
1. PHI/PII keys (phone, patient_name, uh_id) are redacted.
2. Credentials and secrets (password, token, api_key) are redacted.
3. Clinical analytics and prescriptions are redacted from raw logs.
4. Non-sensitive contextual metadata is preserved.
"""

from backend.infrastructure.observability.logging import sanitize_log_dict


def test_sanitize_redacts_credentials_and_secrets():
    data = {
        "event": "login_attempt",
        "user": "admin",
        "password": "supersecretpassword",
        "token": "bearer_jwt_token",
        "client_secret": "my_oauth_secret",
        "api_key": "ai_provider_key",
    }
    clean = sanitize_log_dict(data)

    assert clean["event"] == "login_attempt"
    assert clean["user"] == "admin"
    assert clean["password"] == "[REDACTED]"
    assert clean["token"] == "[REDACTED]"
    assert clean["client_secret"] == "[REDACTED]"
    assert clean["api_key"] == "[REDACTED]"


def test_sanitize_redacts_phi_and_pii():
    data = {
        "action": "ingest_observation",
        "patient_name": "Ramesh Kumar",
        "phone": "+919876543210",
        "uh_id": "UHID-99999",
        "carbs_grams": 65.5,
        "glycemic_index": "high",
        "medication": "Insulin Glargine",
        "instruction": "10 units at bedtime",
    }
    clean = sanitize_log_dict(data)

    assert clean["action"] == "ingest_observation"
    assert clean["patient_name"] == "[REDACTED]"
    assert clean["phone"] == "[REDACTED]"
    assert clean["uh_id"] == "[REDACTED]"
    assert clean["carbs_grams"] == "[REDACTED]"
    assert clean["glycemic_index"] == "[REDACTED]"
    assert clean["medication"] == "[REDACTED]"
    assert clean["instruction"] == "[REDACTED]"


def test_nested_dictionary_redaction():
    data = {
        "meta": {
            "status": "success",
            "auth": {
                "access_token": "secret_token_value",
            },
        }
    }
    clean = sanitize_log_dict(data)
    assert clean["meta"]["status"] == "success"
    assert clean["meta"]["auth"]["access_token"] == "[REDACTED]"
