# apps/admin-web — Administrative Web Console

**GATE 02B — application boundary only. No UI is implemented.**

## Purpose

Administrative web console for tenant/facility operations and system
administration.

## Not implemented (later gates)

- Tenant management
- Facility management
- User management
- Audit UI
- AI governance UI

## Boundary rule

`apps/admin-web` must not duplicate logic from `backend/*`; it is a thin
operator-facing client over the target API.