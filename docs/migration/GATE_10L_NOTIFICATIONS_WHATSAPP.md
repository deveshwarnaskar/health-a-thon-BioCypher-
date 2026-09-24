# Gate 10L Implementation Report — Notifications + WhatsApp Integration

## 1. Baseline
- **Base Tag:** `gate-10k-w-admin-web-sealed`
- **Base Commit:** `47c4c1217d5809efff272d7fc32483c61a2674fd`
- **Branch:** `feature/gate-10l-notifications-whatsapp`
- **Implementation Commit:** `14bfc493538805ec96348aba8bb99851a682bb8e`
- **Sealing Tag:** `gate-10l-notifications-whatsapp-sealed`

---

## 2. File Changes (Diff Scope)

### Added Files
1. `backend/domain/entities/notification.py` — Notification domain entity, lifecycle states, and forbidden field enforcement.
2. `backend/infrastructure/persistence/alembic/versions/0006_notifications.py` — Migration 0006 for `notifications` table and RLS policy `tenant_isolation_notifications`.
3. `backend/infrastructure/persistence/models/notification_models.py` — SQLAlchemy ORM model for notifications.
4. `backend/infrastructure/persistence/repositories/notification_repo.py` — Concrete SQLAlchemy implementation of `NotificationRepository`.
5. `backend/application/services/notification_service.py` — Application service for creating/dispatching notifications.
6. `backend/application/ops/scheduler.py` — Deterministic ReminderScheduler engine for due tasks and adherence notifications.
7. `backend/interfaces/http/v2/notifications/router.py` — FastAPI router for `/api/v2/notifications`.
8. `apps/mobile/src/services/schemas/notifications.ts` — Zod schemas with strict mode for notifications.
9. `apps/mobile/src/services/api/endpoints/notifications.ts` — Mobile API client functions for notifications.
10. `apps/mobile/test/unit/notifications-schemas.test.ts` — Mobile unit tests for notification schemas and strictness.
11. `tests/api/test_gate_10l_notifications_whatsapp.py` — 28 comprehensive backend integration/API tests (requirements A–Z).
12. `tests/integration/test_gate_10l_notifications_rls.py` — Live PostgreSQL RLS cross-tenant isolation tests.
13. `docs/migration/GATE_10L_NOTIFICATIONS_WHATSAPP.md` — This report and audit evidence.

### Modified Files
1. `backend/domain/entities/__init__.py` — Export `Notification`, `NotificationStatus`, `NotificationChannel`, `NotificationType`.
2. `backend/application/ports/repositories.py` — Declare `NotificationRepository` port.
3. `backend/application/ports/unit_of_work.py` — Add `notifications` repository property to `UnitOfWork` protocol.
4. `backend/infrastructure/persistence/models/__init__.py` — Register `NotificationModel`.
5. `backend/infrastructure/persistence/mappings/mappers.py` — Add `notification_to_domain` and `notification_to_model` mappers.
6. `backend/infrastructure/persistence/repositories/__init__.py` — Export `SqlAlchemyNotificationRepository`.
7. `backend/infrastructure/persistence/uow/sqlalchemy_uow.py` — Wire `notifications` repository into `SqlAlchemyUnitOfWork`.
8. `backend/infrastructure/channel/whatsapp_sender.py` — Fail-safe WhatsApp sender with `CREDENTIALS_MISSING` handling.
9. `backend/application/ops/handlers.py` — Delivery and intake handlers updating notification status and denying deactivated patients.
10. `backend/infrastructure/persistence/ops/tenant_resolver.py` — Tenant resolver filtering only active patients.
11. `backend/interfaces/cli/worker.py` — Wiring for worker background dispatcher.
12. `backend/interfaces/http/v2/router.py` — Mount notifications router under `/api/v2`.
13. `backend/interfaces/http/v2/schemas/__init__.py` — Export notification schemas.
14. `backend/interfaces/http/v2/schemas/models.py` — Add Pydantic v2 schemas for notifications (`NotificationResponse`, etc.).
15. `backend/interfaces/http/v2/security/authorization.py` — Add `READ_NOTIFICATIONS` and `MANAGE_NOTIFICATIONS` permissions & role mappings.
16. `apps/mobile/src/services/schemas/index.ts` — Export notification schemas.
17. `apps/mobile/src/services/api/endpoints/index.ts` — Export notification endpoints.
18. `tests/api/test_dto_asymmetry.py` — Add DTO asymmetry and field sanitization tests for notifications.
19. `tests/integration/test_alembic_migrations.py` — Update migration head expectations to revision 0006.
20. `tests/unit/application/fakes.py` — Update `FakeUnitOfWork` with fake notification repository.

### Deleted Files
- None.

---

## 3. Database Migrations
- **Revision ID:** `0006` (`0006_notifications.py`)
- **Down Revision:** `0005` (`0005_admin_control_plane.py`)
- **Table Created:** `notifications`
  - Columns: `id` (UUID PK), `tenant_id` (UUID FK NOT NULL), `recipient_id` (UUID NOT NULL), `recipient_phone` (VARCHAR(32) NOT NULL), `patient_id` (UUID FK NULLABLE), `notification_type` (VARCHAR(64) NOT NULL), `channel` (VARCHAR(32) NOT NULL), `template_name` (VARCHAR(128) NOT NULL), `template_params` (JSONB NOT NULL), `status` (VARCHAR(32) NOT NULL DEFAULT 'pending'), `scheduled_at` (TIMESTAMPTZ NULLABLE), `delivered_at` (TIMESTAMPTZ NULLABLE), `failed_at` (TIMESTAMPTZ NULLABLE), `failure_reason` (TEXT NULLABLE), `correlation_id` (VARCHAR(128) NULLABLE), `retry_count` (INTEGER NOT NULL DEFAULT 0), `created_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW()), `updated_at` (TIMESTAMPTZ NOT NULL DEFAULT NOW()).
- **Indexes:**
  - `ix_notifications_tenant_id` on (`tenant_id`)
  - `ix_notifications_patient_id` on (`patient_id`)
  - `ix_notifications_recipient_id` on (`recipient_id`)
  - `ix_notifications_status_scheduled_at` on (`status`, `scheduled_at`)
  - `ix_notifications_correlation_id` on (`correlation_id`)
- **Row Level Security (RLS):**
  - `ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;`
  - `ALTER TABLE notifications FORCE ROW LEVEL SECURITY;`
  - Policy `tenant_isolation_notifications` on `notifications` enforcing `tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid`.
  - Roles granted: `thali_app_role`, `thali_app_test_role`.

---

## 4. Architecture Summary
- **Notification Domain Entity:** Strict lifecycle transitions (`queue`, `mark_delivering`, `mark_delivered`, `mark_failed`, `requeue_for_retry`, `cancel`). Rejects forbidden clinical and analytical fields (`carbs_grams`, `glycemic_index`, `clinical_notes`, `ai_review`, `ai_diagnosis`, `risk_score`).
- **Repository Pattern & Persistence:** `SqlAlchemyNotificationRepository` enforces multi-tenant scoping on every single query using `tenant_id`.
- **Transactional Outbox Boundary:** `NotificationService.send_notification` persists the notification, an audit log entry (`NOTIFICATION_DISPATCHED`), and an outbox event (`channel.message.queued`) atomically in a single UoW transaction.
- **Fail-Safe Channel Delivery:** `WhatsAppChannelSender` checks credentials; if unset or empty, immediately logs and returns `CREDENTIALS_MISSING` failure without throwing unhandled exceptions or falsely claiming success.
- **Deterministic Reminder Scheduler:** `ReminderScheduler` scans due notifications and care tasks deterministically without AI, CDS, or dosage titration.
- **Intake Pipeline Security:** `WhatsAppIntakeHandler` resolves sender phone number against active patients; immediately drops/denies intake for deactivated patients.
- **API & Access Control:** FastAPI router at `/api/v2/notifications` enforces RBAC (`READ_NOTIFICATIONS`, `MANAGE_NOTIFICATIONS`) and caregiver relationship verification (unexpired, verified, non-deactivated patient).
- **Mobile TypeScript Contracts:** Strict Zod validation (`notificationResponseSchema.strict()`) rejecting extra or forbidden fields.

---

## 5. Test Matrix & Verification

### Suite Results
- **Backend (Pytest):** 717 passed, 0 failed, 0 errors.
- **Mobile (Vitest):** 291 passed, 0 failed, 0 errors.
- **Mobile Lint & Typecheck:** 0 errors (`eslint .` clean, `tsc --noEmit` clean).
- **Admin-Web (Vitest):** 41 passed, 0 failed. Untouched from Gate 10K-W.

### Requirement Coverage (A through Z)
- **A — Notification Domain Entity Lifecycle:** Verified in `test_a_notification_lifecycle_state_machine`.
- **B — Notification Model & PostgreSQL Migration:** Verified in `test_b_notifications_alembic_migration_and_schema` & `test_alembic_migrations.py`.
- **C — RLS Policy for Notifications Table:** Verified in `test_c_notifications_rls_live_postgres` & `test_gate_10l_notifications_rls.py`.
- **D — Notification Repository Implementation:** Verified in `test_d_notification_repository_crud_and_querying`.
- **E — Notification Service:** Verified in `test_e_notification_service_send_and_idempotency`.
- **F — Reminder Scheduler:** Verified in `test_f_reminder_scheduler_processes_due_notifications`.
- **G — Care Task Due Reminders:** Verified in `test_g_care_task_due_reminders`.
- **H — Medication Adherence Reminders:** Verified in `test_h_medication_adherence_reminders`.
- **I — Outbox Worker Integration:** Verified in `test_i_outbox_worker_processes_notification_delivery`.
- **J — WhatsApp Sender Fail-Safe:** Verified in `test_j_whatsapp_sender_fails_safe_when_credentials_missing`.
- **K — WhatsApp Sender Transport Outcome Mapping:** Verified in `test_k_whatsapp_sender_transport_outcome_mapping`.
- **L — Webhook Signature Verification:** Verified in `test_l_webhook_raw_body_hmac_sha256_verification`.
- **M — Webhook Replay Deduplication:** Verified in `test_m_webhook_replay_deduplication`.
- **N — WhatsApp Glucose Intake:** Verified in `test_n_whatsapp_glucose_intake_workflow`.
- **O — WhatsApp Meal Log Intake:** Verified in `test_o_whatsapp_meal_log_intake_workflow`.
- **P — WhatsApp Deactivated Patient Rejection:** Verified in `test_p_whatsapp_intake_rejects_deactivated_patient`.
- **Q — Notification Listing Endpoint:** Verified in `test_q_notification_list_endpoint_and_filtering`.
- **R — Single Notification Endpoint:** Verified in `test_r_single_notification_endpoint`.
- **S — Patient Self-Access Notifications:** Verified in `test_s_patient_self_access_notifications`.
- **T — Caregiver Proxy Access Notifications:** Verified in `test_t_caregiver_proxy_access_notifications`.
- **U — Cross-Tenant Notification Access Denied:** Verified in `test_u_cross_tenant_notification_access_denied`.
- **V — Manual Notification Creation:** Verified in `test_v_manual_notification_creation_endpoint`.
- **W — Process Due Trigger Endpoint:** Verified in `test_w_process_due_notifications_endpoint`.
- **X — Notification DTO Asymmetry:** Verified in `test_x_notification_dto_asymmetry_no_forbidden_fields` & `test_dto_asymmetry.py`.
- **Y — Mobile TypeScript Schemas:** Verified in `test_y_mobile_schemas_pass_validation` & `apps/mobile/test/unit/notifications-schemas.test.ts`.
- **Z — End-to-End Notification Workflow:** Verified in `test_z_end_to_end_notification_workflow`.

---

## 6. Static Code Analysis & Security Audit

### 1. Secret & Credential Leak Scan
- Search query: `grep -rnE "(WHATSAPP_TOKEN|META_ACCESS_TOKEN)" backend/ apps/`
- Result: 0 matches. No secrets or tokens hardcoded. Credentials strictly injected through environment settings.

### 2. API Route Hygiene
- Search query: `grep -rn "/api/v1" backend/ apps/mobile/src apps/admin-web/src`
- Result: 0 active routes exposed. Only historical docstring reference in `get_live_inbound.py`. All active routes are `/api/v2/*`.

### 3. Cross-Tenant Isolation
- Verified: `SqlAlchemyNotificationRepository` includes `NotificationModel.tenant_id == self.tenant_id` on every query.
- Verified: PostgreSQL Row-Level Security (`tenant_isolation_notifications`) active and forced on table `notifications`.

### 4. Frontend Security Invariants
- Verified: Mobile notification schemas use `.strict()`; reject forbidden clinical parameters (`carbs_grams`, `glycemic_index`, etc.).
- Verified: Admin web bundle remains untouched and sealed.

### 5. Clinical Safety & Autonomous Agency
- Verified: Zero clinical decision support, zero AI generation, zero autonomous titration.
- All notifications are strictly operational/reminder templates.

---

## 7. Audit Status
**STATUS:** READY FOR INDEPENDENT AUDIT
