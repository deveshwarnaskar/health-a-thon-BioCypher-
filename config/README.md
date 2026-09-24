# config/ — Target Configuration Boundary

**GATE 03 — production configuration schema introduced (not yet consumed by
the legacy prototype).**

## Status

- `config/settings.py` provides a pydantic-settings / Pydantic v2 `Settings`
  model covering: application, database, Redis, object storage, identity
  provider, WhatsApp/Meta, AI, observability, and security configuration.
- The runtime configuration of the legacy prototype is **unchanged** and still
  lives in `app/config.py`. Legacy Aahaar does **not** depend on this layer.
- `config/example.env` documents the environment variable contract with safe
  placeholders. No real credentials are stored in source control.
- No service is created, connected, or pinged at import or load time.

## Usage (target system, later gates)

```python
from config.settings import Settings

cfg = Settings()
cfg.app.env            # -> "development"
cfg.database.url       # -> "" until a database URL is injected via env
```

Environment variables use the `THALI_` prefix with `__` nested delivery,
e.g. `THALI_REDIS__HOST`.

## Not done at Gate 03

- No replacement of `app/config.py` (deferred to the runtime switchover gate).
- No database, Redis, S3, Keycloak, or AI connection.
- No secret material.
- No integration with the legacy or target application code.