"""Gate 03 — config.settings: safe defaults, no secrets, env override."""

from config.settings import Settings


def test_defaults_are_safe_and_secret_free():
    s = Settings()
    assert s.app.env == "development"
    assert s.database.url == ""
    assert s.redis.host == "localhost"
    assert s.redis.password is None
    assert s.storage.access_key_id == ""
    assert s.storage.secret_access_key == ""
    assert s.identity.client_secret == ""
    assert s.whatsapp.verify_token == ""
    assert s.ai.api_key == ""
    assert s.whatsapp.api_version == "v21.0"


def test_env_nested_override(monkeypatch):
    monkeypatch.setenv("THALI_APP__ENV", "staging")
    monkeypatch.setenv("THALI_REDIS__PORT", "6380")
    s = Settings()
    assert s.app.env == "staging"
    assert s.redis.port == 6380


def test_all_expected_config_sections_exist():
    s = Settings()
    assert set(s.model_dump().keys()) == {
        "app",
        "database",
        "redis",
        "storage",
        "identity",
        "whatsapp",
        "ai",
        "observability",
        "security",
    }