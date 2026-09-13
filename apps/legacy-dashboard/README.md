# apps/legacy-dashboard — Legacy Aahaar Vanilla JS Dashboard

**GATE 02B — boundary reserved; physical files NOT moved.**

## Status

The existing dashboard remains **fully operational in place** at
`app/static/` (`index.html`, `app.js`, `style.css`). It is served by the live
FastAPI app in `app/server/main.py` and must keep working for the baseline
tests and live demo.

## Deliberately NOT done at Gate 02B

- `app/static/*` is **not physically moved** into this directory.
- No import or route redirection of live traffic.

Physical movement will occur only after the compatibility boundary is proven
in a later gate, at which point this directory becomes the archived home of the
dashboard, isolated as **legacy/debug only**.

## Tracking

- `docs/migration/GATE_02B_SCAFFOLDING.md` records this deferral and the
  precondition (compatibility verification) for the move.