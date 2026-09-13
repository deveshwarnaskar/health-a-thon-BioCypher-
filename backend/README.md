# backend/ — THALI x P.L.A.T.E. Target Backend (Gate 02B scaffold)

This directory establishes the approved clean-architecture boundary for the
target system. It is scaffolding only; the operational prototype remains in
`app/` and is preserved unmodified.

## Layering

```
interfaces        HTTP / CLI entry points (FastAPI in later gates)
    |
    v
application       use cases: commands, queries, DTOs, ports, services
    |
    v
domain            entities, value objects, events, exceptions, repositories
```

```
infrastructure    persistence, identity, channel, ai, reporting, storage, cache
    |
    +-- implements application/domain ports
```

## Dependency rule

- `domain` is inward-facing and MUST NOT import infrastructure, FastAPI,
  SQLAlchemy, Redis, HTTP clients, Keycloak, ReportLab, Matplotlib, S3 SDKs,
  WhatsApp SDKs, Gemini SDKs, environment configuration, or the filesystem.
- `application` depends only on `domain` and its own ports.
- `interfaces` may depend on `application`; it must not import technology
  internals.
- `infrastructure` implements `application.ports` and `domain.repositories`;
  nothing may depend downward on `infrastructure` internals.

## Current status

- All modules are type/interface placeholders.
- No business logic is implemented in this package.
- No external services are required to import the baseline test suite.
- `backend.compatibility` will bridge legacy `app.*` behaviour in later gates.