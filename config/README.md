# config/ — Target Configuration Boundary

**GATE 02B — boundary only.**

## Status

The runtime configuration is **unchanged** and continues to live in
`app/config.py` (`Settings` dataclass, `AAHAAR_*` environment variables).
No `pydantic-settings` dependency is installed at Gate 02B.

## Purpose

Future home of the environment-based configuration schema for the target
system (database URLs, Keycloak realm, Redis, S3, channel credentials).
Configuration migration belongs to the next gate.

## Not done at Gate 02B

- No replacement of `app/config.py`.
- No runtime configuration behavior change.
- No new configuration dependencies installed.