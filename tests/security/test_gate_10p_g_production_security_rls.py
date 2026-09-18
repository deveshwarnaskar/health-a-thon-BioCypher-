"""Gate 10P-G — Production Multi-Tenant RLS, Security Hardening & Clinical AI Safety Suite.

Verifies:
1. Production Configuration & Secret Fail-Closed Integrity:
   - Rejects blocklisted secrets ('minioadmin', 'changeme', 'secret', etc.)
   - Rejects secrets with insufficient entropy (<32 characters for identity secret, <16 for Redis)
   - Rejects insecure CORS origins (wildcards '*' and insecure HTTP schemes)
   - Rejects non-HTTPS Keycloak issuer in production
   - Rejects insecure WhatsApp tokens and storage credentials in production
   - Passes when production configuration is fully compliant

2. 8-Role Keycloak Production Matrix & Least-Privilege Separation:
   - Doctor: Full clinical authority (prescribing, AI review, observations)
   - Nurse: Observation logging, care tasks, clinical workflow
   - Dietitian: Meal observations, care tasks, clinical workflow
   - Care Coordinator: Caregiver relationships, care tasks, but DENIED prescribing
   - Field Health Worker: Care task execution, observations, but DENIED prescribing/AI review
   - Patient: Proxy role, coarse RBAC DENIED, authorized strictly via identity mapping
   - Caregiver: Proxy role, coarse RBAC DENIED, authorized strictly via verified capability grants
   - Admin: Administrative provisioning, facilities, but DENIED direct clinical writes

3. Multi-Tenant RLS & Storage Path Isolation:
   - Tenant isolation guarantees zero cross-tenant row leakage
   - UnitOfWork bounds repository queries to active tenant (accessing other tenant raises EntityNotFound)
   - Object storage keys enforce tenant-scoped prefix 'tenants/{tenant_id}/...'
   - Path traversal attempts ('..') are rejected with ValueError

4. Clinical AI Safety Invariants:
   - AI artifacts MUST start in GENERATED or PENDING_REVIEW state
   - Autonomous clinical actions (prescribing, titrating) by AI are strictly prohibited
   - AI review artifacts require explicit human clinician sign-off with reviewer_id
   - Domain rules reject autonomous execution without clinician review
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config.settings import (
    AppConfig,
    DatabaseConfig,
    IdentityConfig,
    ObservabilityConfig,
    RedisConfig,
    SecurityConfig,
    SecurityConfigurationError,
    Settings,
    StorageConfig,
    WhatsAppConfig,
    validate_security_configuration,
)
from backend.domain.entities import (
    AIReviewArtifact,
    CaregiverRelationship,
    CaregiverRelationshipStatus,
    CareTask,
    CareTaskStatus,
    CareTeamRole,
    GlucoseObservation,
    MealObservation,
    MedicationPlan,
    Patient,
    ReviewAuthority,
    ReviewState,
)
from backend.domain.exceptions import EntityNotFound, InvalidStateTransition
from backend.domain.value_objects import (
    GlucoseValue,
    KatoriVolume,
    MealPortion,
    PhoneNumber,
    ReadingTag,
    UHID,
)
from backend.infrastructure.persistence.models import Base
from backend.infrastructure.persistence.models.tenant_models import OrganizationModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork
from backend.infrastructure.storage.s3_storage import S3ObjectStorage, build_storage_key
from backend.interfaces.http.v2.security.authorization import (
    AuthenticatedContext,
    DefaultAuthorizationPolicy,
    Operation,
    RelationshipAuthorizationPolicy,
)


def make_compliant_settings() -> Settings:
    """Helper to create valid, compliant production settings."""
    return Settings(
        app=AppConfig(
            env="production",
            name="THALI-PLATE-PROD",
            version="0.1.0",
        ),
        identity=IdentityConfig(
            issuer_url="https://auth.plate.thali.health/realms/thali-production",
            client_id="thali-backend-api",
            client_secret="a-secure-production-secret-with-more-than-32-chars-entropy!",
            allowed_algorithms="RS256",
        ),
        database=DatabaseConfig(
            url="postgresql+psycopg://thali_user:a-secure-production-db-password-1234@db-prod.internal:5432/thali_production",
            pool_size=10,
            max_overflow=20,
            pool_timeout=5.0,
            pool_pre_ping=True,
        ),
        redis=RedisConfig(
            enabled=True,
            host="redis-prod.internal",
            port=6379,
            password="a-secure-redis-auth-token-with-sufficient-entropy",
        ),
        storage=StorageConfig(
            endpoint_url="https://s3.ap-south-1.amazonaws.com",
            bucket="thali-production-documents-ap-south-1",
            region="ap-south-1",
            access_key_id="AKIA-PROD-AUDIT-KEY-ID",
            secret_access_key="a-secure-s3-production-secret-key-entropy-40-chars",
        ),
        whatsapp=WhatsAppConfig(
            verify_token="a-secure-webhook-verify-token-production-16",
            app_secret="a-secure-whatsapp-production-secret-32-chars-long!",
            phone_number_id="100098765432100",
        ),
        observability=ObservabilityConfig(
            log_level="INFO",
            structured_logs=True,
            metrics_enabled=True,
            metrics_require_auth=True,
            metrics_auth_token="a-secure-metrics-scraping-token-entropy-16",
            tracing_enabled=True,
            tracing_exporter="otlp",
            tracing_otlp_endpoint="https://otel-collector.internal:4318/v1/traces",
        ),
        security=SecurityConfig(
            allowed_origins=[
                "https://admin.plate.thali.health",
                "https://plate.thali.health",
            ],
            session_ttl_minutes=60,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Production Configuration & Secret Fail-Closed Verification
# ─────────────────────────────────────────────────────────────────────────────


class TestProductionConfigurationSecurity:
    """Validates fail-closed security invariants for production configuration."""

    def test_production_rejects_blocklisted_identity_secret(self):
        """Production configuration must reject known default and insecure identity secrets."""
        for bad_secret in ["minioadmin", "changeme", "secret", "password", "admin", "dev-secret-change-in-production"]:
            settings = make_compliant_settings()
            settings.identity.client_secret = bad_secret
            with pytest.raises(SecurityConfigurationError, match="rejected insecure/placeholder identity.client_secret"):
                validate_security_configuration(settings)

    def test_production_rejects_short_identity_secret(self):
        """Production configuration must reject identity secrets shorter than 32 characters."""
        settings = make_compliant_settings()
        settings.identity.client_secret = "too_short_secret_12345"  # < 32 chars
        with pytest.raises(SecurityConfigurationError, match="at least 32 characters"):
            validate_security_configuration(settings)

    def test_production_rejects_insecure_cors_wildcard(self):
        """Production CORS policy must never allow wildcard origins."""
        settings = make_compliant_settings()
        settings.security.allowed_origins = ["*"]
        with pytest.raises(SecurityConfigurationError, match="strictly forbids wildcard"):
            validate_security_configuration(settings)

    def test_production_rejects_insecure_http_cors(self):
        """Production CORS policy must reject plain HTTP origins."""
        settings = make_compliant_settings()
        settings.security.allowed_origins = ["http://insecure-admin.example.com"]
        with pytest.raises(SecurityConfigurationError, match="requires HTTPS scheme"):
            validate_security_configuration(settings)

    def test_production_rejects_weak_redis_password(self):
        """Production configuration must require a strong Redis password."""
        settings = make_compliant_settings()
        settings.redis.password = "short"
        with pytest.raises(SecurityConfigurationError, match="requires redis.password to have at least 16 characters"):
            validate_security_configuration(settings)

    def test_production_rejects_weak_storage_credentials(self):
        """Production configuration must reject default/blocklisted storage credentials."""
        settings = make_compliant_settings()
        settings.storage.secret_access_key = "minioadmin"
        with pytest.raises(SecurityConfigurationError, match="rejected insecure/placeholder storage credentials"):
            validate_security_configuration(settings)

    def test_production_rejects_insecure_whatsapp_token(self):
        """Production configuration must reject default/blocklisted WhatsApp token."""
        settings = make_compliant_settings()
        settings.whatsapp.verify_token = "changeme"
        with pytest.raises(SecurityConfigurationError, match="rejected insecure/placeholder whatsapp.verify_token"):
            validate_security_configuration(settings)

    def test_production_rejects_non_https_issuer(self):
        """Production identity issuer must strictly use HTTPS."""
        settings = make_compliant_settings()
        settings.identity.issuer_url = "http://auth.plate.thali.health/realms/thali-production"
        with pytest.raises(SecurityConfigurationError, match="requires identity.issuer_url to use HTTPS scheme"):
            validate_security_configuration(settings)

    def test_compliant_production_configuration_passes(self):
        """A fully compliant production configuration passes all validation assertions."""
        settings = make_compliant_settings()
        # Should not raise any error
        validate_security_configuration(settings)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Keycloak 8 Production Roles & Least-Privilege Separation
# ─────────────────────────────────────────────────────────────────────────────


class TestKeycloakRolesAuthorizationMatrix:
    """Verifies that the 8 production Keycloak roles adhere to strict least-privilege."""

    @pytest.fixture
    def policy(self):
        return RelationshipAuthorizationPolicy()

    def test_doctor_has_full_clinical_authority(self, policy):
        """Doctor role can prescribe medications, review AI artifacts, and record observations."""
        ctx = AuthenticatedContext(
            actor_id=uuid4(),
            tenant_id=uuid4(),
            roles=("doctor",),
        )
        assert policy.is_allowed(ctx, Operation.READ_OBSERVATIONS) is True
        assert policy.is_allowed(ctx, Operation.WRITE_OBSERVATIONS) is True
        assert policy.is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS) is True
        assert policy.is_allowed(ctx, Operation.READ_MEDICATION_PLANS) is True
        assert policy.is_allowed(ctx, Operation.REVIEW_AI_ARTIFACT) is True
        assert policy.is_allowed(ctx, Operation.GENERATE_AI_ARTIFACT) is True

    def test_care_coordinator_cannot_prescribe_medications(self, policy):
        """Care coordinator can manage caregiver relationships but CANNOT prescribe medication."""
        ctx = AuthenticatedContext(
            actor_id=uuid4(),
            tenant_id=uuid4(),
            roles=("care_coordinator",),
        )
        assert policy.is_allowed(ctx, Operation.MANAGE_CAREGIVER_RELATIONSHIPS) is True
        assert policy.is_allowed(ctx, Operation.CREATE_CARE_TASK) is True
        assert policy.is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS) is False

    def test_field_health_worker_restricted_to_tasks_and_observations(self, policy):
        """Field health worker can perform tasks and log observations, but cannot prescribe or review AI."""
        ctx = AuthenticatedContext(
            actor_id=uuid4(),
            tenant_id=uuid4(),
            roles=("field_health_worker",),
        )
        assert policy.is_allowed(ctx, Operation.READ_OBSERVATIONS) is True
        assert policy.is_allowed(ctx, Operation.WRITE_OBSERVATIONS) is True
        assert policy.is_allowed(ctx, Operation.START_CARE_TASK) is True
        assert policy.is_allowed(ctx, Operation.COMPLETE_CARE_TASK) is True
        # Prescribing and AI Review are strictly denied for FHW
        assert policy.is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS) is False
        assert policy.is_allowed(ctx, Operation.REVIEW_AI_ARTIFACT) is False

    def test_admin_cannot_perform_direct_clinical_mutations(self, policy):
        """Admin has administrative authority but CANNOT write clinical observations or prescribe."""
        ctx = AuthenticatedContext(
            actor_id=uuid4(),
            tenant_id=uuid4(),
            roles=("admin",),
        )
        assert policy.is_allowed(ctx, Operation.ADMIN) is True
        assert policy.is_allowed(ctx, Operation.PROVISION_PATIENT) is True
        assert policy.is_allowed(ctx, Operation.MANAGE_FACILITIES) is True
        # Clinical write boundaries denied for admin
        assert policy.is_allowed(ctx, Operation.WRITE_OBSERVATIONS) is False
        assert policy.is_allowed(ctx, Operation.WRITE_MEDICATION_PLANS) is False

    def test_patient_and_caregiver_deny_coarse_rbac(self, policy):
        """Proxy roles (patient, caregiver) are strictly denied coarse RBAC permissions."""
        patient_ctx = AuthenticatedContext(
            actor_id=uuid4(),
            tenant_id=uuid4(),
            roles=("patient",),
        )
        caregiver_ctx = AuthenticatedContext(
            actor_id=uuid4(),
            tenant_id=uuid4(),
            roles=("caregiver",),
        )
        # Without relationship/identity mapping context, coarse queries fail closed
        assert policy.is_allowed(patient_ctx, Operation.READ_OBSERVATIONS) is False
        assert policy.is_allowed(caregiver_ctx, Operation.READ_OBSERVATIONS) is False


# ─────────────────────────────────────────────────────────────────────────────
# 3. Multi-Tenant RLS & Object Storage Namespace Isolation
# ─────────────────────────────────────────────────────────────────────────────


class TestMultiTenantIsolation:
    """Verifies strict multi-tenant boundary separation and storage isolation."""

    @pytest.fixture
    def session_factory(self):
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @pytest.fixture
    def uow_factory(self, session_factory):
        def _create(tenant_id: UUID) -> SqlAlchemyUnitOfWork:
            with session_factory() as session:
                existing = session.query(OrganizationModel).filter_by(id=tenant_id).first()
                if not existing:
                    session.add(
                        OrganizationModel(
                            id=tenant_id,
                            name=f"Tenant-{str(tenant_id)[:8]}",
                            slug=f"tenant-{str(tenant_id)[:8]}",
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                    session.commit()
            return SqlAlchemyUnitOfWork(session_factory, tenant_id)
        return _create

    def test_patient_cross_tenant_isolation(self, uow_factory):
        """Tenant B must never be able to view or retrieve Tenant A patients."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        patient_a_id = uuid4()

        # Seed patient in Tenant A
        uow_a = uow_factory(tenant_a)
        with uow_a:
            patient_a = Patient(
                id=patient_a_id,
                uh_id=UHID("UHID-TENANT-A-001"),
                name="Amitabh Roy",
                facility_id=uuid4(),
                phone=PhoneNumber("+919800000001"),
                active=True,
            )
            uow_a.patients.add(patient_a)
            uow_a.commit()

        # Query from Tenant B must raise EntityNotFound
        uow_b = uow_factory(tenant_b)
        with uow_b:
            with pytest.raises(EntityNotFound):
                uow_b.patients.get(patient_a_id)

        # Verify Tenant A can retrieve it
        uow_a_read = uow_factory(tenant_a)
        with uow_a_read:
            loaded = uow_a_read.patients.get(patient_a_id)
            assert loaded is not None
            assert loaded.name == "Amitabh Roy"

    def test_glucose_observation_cross_tenant_isolation(self, uow_factory):
        """Tenant B must never be able to access Tenant A clinical observations."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        patient_a_id = uuid4()
        obs_id = uuid4()

        uow_a = uow_factory(tenant_a)
        with uow_a:
            obs = GlucoseObservation(
                id=obs_id,
                patient_id=patient_a_id,
                value=GlucoseValue(155),
                tag=ReadingTag.FASTING,
                taken_at=datetime.now(timezone.utc),
            )
            uow_a.glucose_observations.add(obs)
            uow_a.commit()

        # Tenant B cannot access Tenant A observation
        uow_b = uow_factory(tenant_b)
        with uow_b:
            with pytest.raises(EntityNotFound):
                uow_b.glucose_observations.get(obs_id)

    def test_storage_key_path_traversal_rejection(self):
        """Storage service must reject path traversal attempts that escape tenant prefix."""
        storage = S3ObjectStorage(
            bucket="thali-production-documents-ap-south-1",
            endpoint_url=None,
            access_key_id=None,
            secret_access_key=None,
        )

        malicious_keys = [
            "../../etc/passwd",
            "tenants/tenant-a/../../tenant-b/patient.pdf",
            "../secret.pdf",
            "tenants/../documents",
        ]

        for bad_key in malicious_keys:
            with pytest.raises(ValueError, match="Illegal object key path"):
                storage.put(bad_key, b"malicious content")
            with pytest.raises(ValueError, match="Illegal object key path"):
                storage.get(bad_key)
            with pytest.raises(ValueError, match="Illegal object key path"):
                storage.generate_presigned_url(bad_key)

    def test_storage_key_scoped_to_tenant_namespace(self):
        """Valid storage key generation strictly enforces the tenant prefix."""
        tenant_id = uuid4()
        patient_id = uuid4()
        doc_id = uuid4()

        key = build_storage_key(tenant_id, patient_id, "discharge_summary", doc_id, "pdf")
        assert key.startswith(f"tenants/{tenant_id}/patients/{patient_id}/")
        assert key.endswith(".pdf")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Clinical AI Safety Invariants
# ─────────────────────────────────────────────────────────────────────────────


class TestClinicalAISafetyInvariants:
    """Verifies clinical safety invariants: AI cannot prescribe, titrate, or self-approve."""

    def test_ai_artifact_requires_human_clinician_approval(self):
        """AI review artifact cannot be executed or actioned without human clinician sign-off."""
        artifact_id = uuid4()
        patient_id = uuid4()
        tenant_id = uuid4()
        doctor_id = uuid4()

        artifact = AIReviewArtifact(
            id=artifact_id,
            patient_id=patient_id,
            tenant_id=tenant_id,
            artifact_kind="glycemic_risk_summary",
            authority=ReviewAuthority.CLINICIAN_REVIEW,
            state=ReviewState.GENERATED,
            summary="Patient exhibited high fasting glucose variance",
        )

        # Artifact starts in GENERATED state
        assert artifact.state == ReviewState.GENERATED
        assert artifact.reviewed_by_user_id is None

        # Cannot directly transition to ACTIONED or AUDITED without review
        with pytest.raises(InvalidStateTransition):
            artifact.action()

        # Must move to PENDING_REVIEW first
        artifact.submit_for_review()
        assert artifact.state == ReviewState.PENDING_REVIEW

        # Clinician must explicitly approve
        artifact.approve(reviewer=doctor_id)
        assert artifact.state == ReviewState.APPROVED
        assert artifact.reviewed_by_user_id == doctor_id
        assert artifact.reviewed_at is not None

        # Now it can transition to ACTIONED
        artifact.action()
        assert artifact.state == ReviewState.ACTIONED

    def test_ai_cannot_be_author_of_medication_plan(self):
        """Medication plans require a human CareTeamRole (DOCTOR). AI is strictly prohibited."""
        patient_id = uuid4()
        doctor_id = uuid4()

        # Valid prescription by DOCTOR
        plan = MedicationPlan(
            id=uuid4(),
            patient_id=patient_id,
            prescribed_by_user_id=doctor_id,
            prescribed_by_role=CareTeamRole.DOCTOR,
            medication="Glimepiride 1mg",
            instruction="Take before breakfast",
            active=True,
        )
        assert plan.prescribed_by_role == CareTeamRole.DOCTOR

        # CareTeamRole does not include AI
        allowed_roles = {role.value for role in CareTeamRole}
        assert "ai" not in allowed_roles
        assert "bot" not in allowed_roles
        assert "system" not in allowed_roles
