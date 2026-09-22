# GATE 05 — POST-COMPLETION RECONCILIATION

**THALI × P.L.A.T.E. Production Program — Test-Lineage Reconciliation**

- **Status:** PASS — no source-code correction required; no new commit created
- **Branch:** `feature/gate-05-infrastructure-adapters`
- **Gate 05 commit (unchanged):** `5503ad0` — `feat(infrastructure): establish persistence and infrastructure adapters`
- **Gate 05 tag (unchanged):** `gate-05-infrastructure-adapters-complete`

---

## 1. Discrepancy under reconciliation

| Bucket | Approved Gate 04 checkpoint | Gate 05 report (predecessor) | Delta |
| :--- | :---: | :---: | :---: |
| Gate 00 baseline | 57 | 57 | 0 |
| Gate 03 | 48 | 45 | **−3** |
| Gate 04 | 49 | 52 | **+3** |
| Predecessor subtotal | 154 | 154 | 0 |

The predecessor total (154) is identical in both reports. The only delta is a
**−3 / +3 re-bucketing between the Gate 03 and Gate 04 bands.**

## 2. Root cause — classification artifact, not lost or changed coverage

The Gate 03 gate document itself defines its count as
**"48 new Gate 03 tests (domain 45 + config 3)"**, i.e. the 48-test Gate 03
band included:

- **45 domain tests**: `tests/unit/domain/*` (7 files)
- **3 config tests**: `tests/unit/config/test_settings.py` (tests the Gate 03
  `config/` pydantic-settings boundary)

The Gate 05 report moved exactly those **3 config tests** from the "Gate 03"
bucket into the "Gate 04" bucket (52 = 41 application + 8 architecture + 3
config; the Gate 04 gate document's own 49 = 41 application + 8 architecture).
No test file, test name, or test body changed. The re-bucket is a reporting
convention: the Gate 05 author counted `tests/unit/config/*` under the
application-side band instead of the domain-side band.

Verified byte-for-byte:

```
git diff --name-only bb04699 5503ad0 -- tests/
  -> returns ONLY the 13 newly added Gate 05 files
  -> zero modifications to tests/test_linking.py, tests/test_pipeline.py,
     tests/conftest.py, tests/unit/config/*, tests/unit/domain/*,
     tests/unit/application/*, tests/unit/architecture/*
```

## 3. What happened to the 48 approved Gate 03 tests

All 48 remain present and unchanged at their original paths:

| Original Gate 03 test file | Current path (identical) | Tests | Status |
| :--- | :--- | :---: | :--- |
| gate-03 `tests/unit/domain/test_ai_review_artifact.py` | same | 9 | UNCHANGED / PASS |
| gate-03 `tests/unit/domain/test_domain_event.py` | same | 6 | UNCHANGED / PASS |
| gate-03 `tests/unit/domain/test_glucose_value.py` | same | 6 | UNCHANGED / PASS |
| gate-03 `tests/unit/domain/test_katori_volume.py` | same | 6 | UNCHANGED / PASS |
| gate-03 `tests/unit/domain/test_medication_plan.py` | same | 5 | UNCHANGED / PASS |
| gate-03 `tests/unit/domain/test_patient_facing_projection.py` | same | 5 | UNCHANGED / PASS |
| gate-03 `tests/unit/domain/test_phone_number.py` | same | 8 | UNCHANGED / PASS |
| gate-03 `tests/unit/config/test_settings.py` | same | 3 | UNCHANGED / PASS (re-bucketed in Gate 05 report only) |
| **Total** | | **48** | |

## 4. What happened to the 49 approved Gate 04 tests

All 49 remain present and unchanged at their original paths:

| Original Gate 04 test file | Current path (identical) | Tests | Status |
| :--- | :--- | :---: | :--- |
| `tests/unit/application/test_commands.py` | same | 10 | UNCHANGED / PASS |
| `tests/unit/application/test_ai_review_boundary.py` | same | 8 | UNCHANGED / PASS |
| `tests/unit/application/test_dto_boundaries.py` | same | 6 | UNCHANGED / PASS |
| `tests/unit/application/test_events_and_determinism.py` | same | 5 | UNCHANGED / PASS |
| `tests/unit/application/test_unit_of_work.py` | same | 5 | UNCHANGED / PASS |
| `tests/unit/application/test_medication_authority.py` | same | 7 | UNCHANGED / PASS |
| `tests/unit/architecture/test_import_boundaries.py` | same | 8 | UNCHANGED / PASS |
| **Total** | | **49** | |

## 5. Renamed / moved / merged / split / deleted / newly classified

| Event | Tests affected | Detail |
| :--- | :--- | :--- |
| Renamed | 0 | none |
| Moved | 0 | none (paths identical since creation) |
| Merged | 0 | none |
| Split | 0 | none |
| Deleted | 0 | none |
| **Newly classified** | **3** | `tests/unit/config/test_settings.py` (3 tests) — created and approved under Gate 03 (per the Gate 03 doc), re-bucketed under the Gate 04 band in the Gate 05 report. Reporting-only; files untouched. |

## 6. Proof that no approved coverage was lost

1. `git diff --name-only bb04699 5503ad0 -- tests/` lists only the **13 new**
   Gate 05 test files (11 unit + 2 integration). No predecessor file changed.
2. Per-checkpoint collection counts (verified by `pytest --collect-only` at
   `d38373e`, `bb04699`, `5503ad0`):
   - Gate 03 checkpoint: 105 total = 57 (linking 16 + pipeline 41) + 48 (45 domain + 3 config)
   - Gate 04 checkpoint: 154 total = 105 predecessor + 49 (41 application + 8 architecture)
   - Gate 05: 209 total = 57 + 45 + 52 + 52 unit + 3 integration
3. Combined suite re-run on the working tree: **209 passed, 0 failures**
   (see section 8).

## 7. Exact classification consensus

| Band | Tests | Definition used for reconciliation |
| :--- | :---: | :--- |
| Gate 00 baseline | **57** | `tests/test_linking.py` (16) + `tests/test_pipeline.py` (41) |
| Gate 03 approved | **48** | `tests/unit/domain/*` (45) + `tests/unit/config/test_settings.py` (3) — matches the Gate 03 doc's own "(domain 45 + config 3)" |
| Gate 04 approved | **49** | `tests/unit/application/*` (41) + `tests/unit/architecture/test_import_boundaries.py` (8) — matches the Gate 04 doc's own breakdown |
| Gate 05 unit | **52** | `tests/unit/infrastructure/*` (11 files) |
| Gate 05 integration | **3** | `tests/integration/test_alembic_migrations.py` (2) + `tests/integration/test_postgres_repositories.py` (1) |
| **Total** | **209** | |

Truth table — all three checkpoints are internally consistent:

```
Gate 03: 57  + 48                       = 105   (approved)
Gate 04: 57  + 48 + 49                  = 154   (approved)
Gate 05: 57  + 45 + 52 + 52 + 3         = 209   (approved total; bands differ only by the 3-test config re-bucket)
```

The Gate 05 report's **209 total and 154 predecessor total are correct**;
its per-band split (45/52) is a defensible but different convention from the
Gate 04-approved convention (48/49). This is a documentation/classification
delta, explicitly **not** a test modification or coverage loss.

## 8. Complete suite re-run

```
$ .venv/bin/pytest tests -q
209 passed, 89 warnings in 4.34s
```

- **57** Gate 00 baseline: 16 linking + 41 pipeline — PASS
- **45** domain + **3** config (original 48 Gate 03) — PASS
- **41** application + **8** architecture (original 49 Gate 04) — PASS
- **52** Gate 05 infrastructure unit (11 files) — PASS
- **3** Gate 05 integration (alembic × 2, postgres RLS × 1) — PASS against a
  live PostgreSQL 17.11
- **Total: 209 passed, 0 failures**

## 9. Conclusion — no correction required

No source-code, configuration, or test change is required. The discrepancy is a
**classification artifact** (the 3 `tests/unit/config/test_settings.py` tests
moved between reporting bands). Gate 05 commit `5503ad0` and tag
`gate-05-infrastructure-adapters-complete` remain **unchanged**. Per gate
policy, no new commit is created. To align future reports with the approvals,
subsequent gate documentation should state predecessor bands as
**"Gate 03: 45 domain + 3 config = 48"** or adopt one convention consistently.

---

## PostgreSQL tenant-context lifecycle & pooling evidence

### Implementation path (code)

```
request/context
  -> SqlAlchemyUnitOfWork(session_factory, tenant_id)     uow/sqlalchemy_uow.py:24
       ._apply_tenant_context() -> set_config('app.current_tenant_id', :tid, true)
                                   (parameterized; dialect == 'postgresql' guard)  :56-64
  -> per-transaction repositories (7) instantiated with self.tenant_id          :47-54
  -> application in_transaction(uow, body)  (commit once / rollback on error)    application/services/_transaction.py:15-22
       commit  -> session.commit()   (ends transaction)
       error   -> uow.rollback()     (ends transaction)                         sqlalchemy_uow.py:66-72
  -> safe pool return                    (connection released back to QueuePool)
```

`set_config(..., is_local = true)` is PostgreSQL's **transaction-local** `SET
LOCAL` equivalent: it is automatically cleared at the end of the transaction
(commit **or** rollback). RLS policies additionally fail closed when the
setting is empty.

```
USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
WITH CHECK (same)
```

### Pooled-connection leak verification (non-superuser role, live PG 17.11)

Scratch database migrated to `head` (Alembic), `pool_size=1, max_overflow=0`
(QueuePool) so every session reuses the **same physical backend connection**,
role `thali_app_test_role` (`NOSUPERUSER NOBYPASSRLS`):

| # | Check | Result |
| :---: | :--- | :--- |
| 1 | Backend reachable (`pg_backend_pid`) | PASS |
| 2 | Same pooled physical connection reused across Tenant-A then Tenant-B UoWs (identical `pg_backend_pid`), commits did not carry tenant state into the next transaction | PASS |
| 3 / 3a | `SET ROLE thali_app_test_role` effective; `rolsuper = false` (RLS engine, not owner privilege) | PASS |
| 4 | **Unset tenant context** → `count(patients) = 0` (fail-closed) | PASS |
| 5 | **Tenant-A visibility** → context `tenant_a` → its own row visible (count 1) | PASS |
| 6 | **Tenant-B visibility** → context `tenant_b` → its own row visible (count 1) | PASS |
| 7 | **Cross-tenant read** → `tenant_a` context on Tenant-B's row → 0 rows | PASS |
| 8 | **Cross-tenant write** → `tenant_a` context inserting a row with `tenant_id = tenant_b` → rejected: `new row violates row-level security policy for table "patients"` (WITH CHECK) | PASS |
| 9a | Context active **inside** its own transaction (count 1) | PASS |
| 9b | After `COMMIT`, still on the **same pooled connection**: `current_setting('app.current_tenant_id') = ''`, next statement returns **0 rows** → no leak into the following transaction | PASS |

**11 / 11 checks passed.** Conclusion: the transaction-local tenant setting is
cleared at transaction end, RLS fails closed without context, and a recycled
pooled connection cannot observe a previous tenant's context.

### Suite-level integration evidence

```
tests/integration/test_alembic_migrations.py::...upgrade_and_downgrade_sqlite        PASSED
tests/integration/test_alembic_migrations.py::...postgres_if_available               PASSED
tests/integration/test_postgres_repositories.py::...repository_and_rls_isolation     PASSED
```

`test_postgres_repositories.py` runs the non-superuser role directly and asserts
tenant-A visibility (1 row), tenant-B visibility (1 row), cross-tenant read
blocked, and the fail-closed unset context (0 rows), all under
`SET ROLE thali_app_test_role`.

---

## Afterword — STOP

Reconciliation complete. **No commit or tag was created or moved.**
Proceeding to **Gate 06 is NOT permitted** until the responsible stakeholder
approves this reconciliation.