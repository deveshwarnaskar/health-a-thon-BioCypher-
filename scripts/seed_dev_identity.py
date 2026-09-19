"""Seed development identity fixtures matching config/keycloak-local-realm.json.

Populates PostgreSQL with tenant 11111111-1111-1111-1111-111111111111,
facility 22222222-2222-2222-2222-222222222222, patient identity mappings,
caregiver relationships, and care team members.

Idempotent: Safe to re-run multiple times.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.infrastructure.persistence.models.base import Base
from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
from backend.infrastructure.persistence.models.identity_models import (
    CaregiverRelationshipModel,
    IdentityPatientMappingModel,
)
from backend.infrastructure.persistence.models.patient_models import PatientModel
from backend.infrastructure.persistence.models.tenant_models import (
    FacilityModel,
    OrganizationModel,
)

# ─── Realm UUIDs matching config/keycloak-local-realm.json ────────────────────
DEV_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEV_FACILITY_ID = UUID("22222222-2222-2222-2222-222222222222")

# Keycloak Users
KEYCLOAK_PATIENT_USER_ID = UUID("10000000-0000-0000-0000-000000000001")
KEYCLOAK_CAREGIVER_USER_ID = UUID("10000000-0000-0000-0000-000000000002")
KEYCLOAK_DOCTOR_USER_ID = UUID("10000000-0000-0000-0000-000000000003")
KEYCLOAK_NURSE_USER_ID = UUID("10000000-0000-0000-0000-000000000004")
KEYCLOAK_COORDINATOR_USER_ID = UUID("10000000-0000-0000-0000-000000000005")
KEYCLOAK_DIETITIAN_USER_ID = UUID("10000000-0000-0000-0000-000000000006")
KEYCLOAK_FHW_USER_ID = UUID("10000000-0000-0000-0000-000000000007")

# Domain Patients
PATIENT_SITA_ID = UUID("33333333-3333-3333-3333-333333333331")
PATIENT_RAJESH_ID = UUID("33333333-3333-3333-3333-333333333332")

# Identity mapping & relationship IDs
MAPPING_SITA_ID = UUID("44444444-4444-4444-4444-444444444441")
RELATIONSHIP_RAJESH_ID = UUID("44444444-4444-4444-4444-444444444442")


def seed_dev_identities(session: Session) -> dict[str, int]:
    """Idempotently seed development identities."""
    now = datetime.now(timezone.utc)

    # 1. Organization
    org = session.query(OrganizationModel).filter_by(id=DEV_TENANT_ID).first()
    if not org:
        org = OrganizationModel(
            id=DEV_TENANT_ID,
            name="THALI Metro Health System",
            slug="thali-metro",
        )
        session.add(org)
        session.flush()

    # 2. Facility
    fac = session.query(FacilityModel).filter_by(id=DEV_FACILITY_ID).first()
    if not fac:
        fac = FacilityModel(
            id=DEV_FACILITY_ID,
            tenant_id=DEV_TENANT_ID,
            name="THALI Metro Primary Health Clinic",
        )
        session.add(fac)
        session.flush()

    # 3. Workforce Members
    workforce_specs = [
        (KEYCLOAK_DOCTOR_USER_ID, "doctor", "Dr. Arvind Sharma"),
        (KEYCLOAK_NURSE_USER_ID, "nurse", "Nurse Priya Patel"),
        (KEYCLOAK_COORDINATOR_USER_ID, "care_coordinator", "Coordinator Rahul Verma"),
        (KEYCLOAK_DIETITIAN_USER_ID, "dietitian", "Dietitian Sunita Rao"),
        (KEYCLOAK_FHW_USER_ID, "field_health_worker", "FHW Meena Devi"),
    ]
    seeded_workforce = 0
    for user_id, role, name in workforce_specs:
        member = (
            session.query(CareTeamMemberModel)
            .filter_by(tenant_id=DEV_TENANT_ID, user_id=user_id)
            .first()
        )
        if not member:
            member = CareTeamMemberModel(
                tenant_id=DEV_TENANT_ID,
                user_id=user_id,
                facility_id=DEV_FACILITY_ID,
                role=role,
                display_name=name,
                active=True,
            )
            session.add(member)
            seeded_workforce += 1

    # 4. Patients
    patient_specs = [
        (PATIENT_SITA_ID, "UHID-DEL-001", "Sita Sharma", "+919800000001"),
        (PATIENT_RAJESH_ID, "UHID-DEL-002", "Rajesh Sharma", "+919800000002"),
    ]
    seeded_patients = 0
    for p_id, p_uhid, p_name, p_phone in patient_specs:
        pat = session.query(PatientModel).filter_by(id=p_id).first()
        if not pat:
            pat = PatientModel(
                id=p_id,
                tenant_id=DEV_TENANT_ID,
                facility_id=DEV_FACILITY_ID,
                uh_id=p_uhid,
                name=p_name,
                phone=p_phone,
                active=True,
            )
            session.add(pat)
            seeded_patients += 1

    session.flush()

    # 5. Identity Patient Mapping for patient.test
    mapping = session.query(IdentityPatientMappingModel).filter_by(id=MAPPING_SITA_ID).first()
    if not mapping:
        mapping = IdentityPatientMappingModel(
            id=MAPPING_SITA_ID,
            tenant_id=DEV_TENANT_ID,
            user_id=KEYCLOAK_PATIENT_USER_ID,
            patient_id=PATIENT_SITA_ID,
            active=True,
        )
        session.add(mapping)

    # 6. Caregiver Relationship for caregiver.test -> Rajesh Sharma
    rel = session.query(CaregiverRelationshipModel).filter_by(id=RELATIONSHIP_RAJESH_ID).first()
    if not rel:
        rel = CaregiverRelationshipModel(
            id=RELATIONSHIP_RAJESH_ID,
            tenant_id=DEV_TENANT_ID,
            caregiver_user_id=KEYCLOAK_CAREGIVER_USER_ID,
            patient_id=PATIENT_RAJESH_ID,
            relationship_label="Daughter / Family Caregiver",
            status="verified",
            capabilities=["VIEW_OBSERVATIONS", "RECORD_OBSERVATIONS", "VIEW_CARE_PLANS"],
            verified_at=now,
        )
        session.add(rel)

    session.commit()
    return {
        "workforce": seeded_workforce,
        "patients": seeded_patients,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Keycloak local realm development identities.")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "postgresql://thali_app:thali_local_pass@localhost:5432/thali_dev"),
        help="Database URL (default: $DATABASE_URL or postgresql://thali_app:thali_local_pass@localhost:5432/thali_dev)",
    )
    args = parser.parse_args()

    engine = create_engine(args.db_url)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        stats = seed_dev_identities(session)
        print(f"Successfully seeded development identities for tenant {DEV_TENANT_ID}:")
        print(f"  Facility: {DEV_FACILITY_ID}")
        print(f"  Workforce: {stats['workforce']} members")
        print(f"  Patients: {stats['patients']} patients")
        print("Ready for authentication testing with Keycloak users!")


if __name__ == "__main__":
    main()
