#!/usr/bin/env python3
"""Seed development database with default tenant, facility, users, and patient.

Idempotent: Safe to re-run multiple times without errors or duplicates.
Replaces scripts/seed_dev_identity.py and scripts/seed_target_stack.py.

Usage:
    python -m scripts.seed_dev_stack
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.environ.get("THALI_DATABASE__URL", "")
ADMIN_PASSWORD = os.environ.get("THALI_SEED_ADMIN_PASSWORD", "admin-change-me-2026")
SEED_ENABLED = os.environ.get("THALI_SEED_ENABLED", "true").lower() in ("true", "1", "yes")

# Deterministic IDs for reproducible local development
DEV_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
DEV_FACILITY_ID = UUID("22222222-2222-2222-2222-222222222222")
DEV_PATIENT_ID = UUID("33333333-3333-3333-3333-333333333331")
DEV_ADMIN_ID = UUID("10000000-0000-0000-0000-000000000001")
DEV_DOCTOR_ID = UUID("10000000-0000-0000-0000-000000000002")
DEV_NURSE_ID = UUID("10000000-0000-0000-0000-000000000003")
DEV_PATIENT_USER_ID = UUID("10000000-0000-0000-0000-000000000004")
DEV_CAREGIVER_USER_ID = UUID("10000000-0000-0000-0000-000000000005")


def seed() -> None:
    if not SEED_ENABLED:
        print("Seeding disabled (THALI_SEED_ENABLED=false)")
        return

    if not DATABASE_URL:
        print("ERROR: THALI_DATABASE__URL not set", file=sys.stderr)
        sys.exit(1)

    from backend.infrastructure.auth.password_service import hash_password
    from backend.infrastructure.persistence.models import (
        Base,
        CaregiverRelationshipModel,
        CareTeamMemberModel,
        FacilityModel,
        IdentityPatientMappingModel,
        OrganizationModel,
        PatientModel,
        UserModel,
    )

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        # Disable RLS check if in postgres superuser / admin connection
        if engine.dialect.name == "postgresql":
            session.execute(
                text("SELECT set_config('app.current_tenant_id', :tid, true)"),
                {"tid": str(DEV_TENANT_ID)},
            )

        # ------------------------------------------------------------------
        # 1. Tenant (organizations table)
        # ------------------------------------------------------------------
        org = session.query(OrganizationModel).filter_by(slug="thali-dev").first()
        if not org:
            org = session.query(OrganizationModel).filter_by(id=DEV_TENANT_ID).first()
        if not org:
            org = OrganizationModel(
                id=DEV_TENANT_ID,
                name="THALI Development",
                slug="thali-dev",
                active=True,
                created_at=now,
            )
            session.add(org)
            session.flush()
            print(f"  Created tenant: {org.id} ({org.slug})")
        else:
            print(f"  Tenant already exists: {org.id} ({org.slug})")

        tenant_id = org.id

        # ------------------------------------------------------------------
        # 2. Facility
        # ------------------------------------------------------------------
        facility = session.query(FacilityModel).filter_by(tenant_id=tenant_id, name="Dev Hospital").first()
        if not facility:
            facility = session.query(FacilityModel).filter_by(id=DEV_FACILITY_ID).first()
        if not facility:
            facility = FacilityModel(
                id=DEV_FACILITY_ID,
                tenant_id=tenant_id,
                name="Dev Hospital",
                active=True,
                created_at=now,
            )
            session.add(facility)
            session.flush()
            print(f"  Created facility: {facility.id} ({facility.name})")
        else:
            print(f"  Facility already exists: {facility.id} ({facility.name})")

        facility_id = facility.id

        # ------------------------------------------------------------------
        # 3. Users (users table for custom auth)
        # ------------------------------------------------------------------
        users_to_seed = [
            {
                "id": DEV_ADMIN_ID,
                "email": "admin@thali.local",
                "password": ADMIN_PASSWORD,
                "role": "admin",
                "facility_id": None,
            },
            {
                "id": DEV_DOCTOR_ID,
                "email": "doctor@thali.local",
                "password": "doctor-change-me-2026",
                "role": "doctor",
                "facility_id": facility_id,
            },
            {
                "id": DEV_NURSE_ID,
                "email": "nurse@thali.local",
                "password": "nurse-change-me-2026",
                "role": "nurse",
                "facility_id": facility_id,
            },
            {
                "id": DEV_PATIENT_USER_ID,
                "email": "patient@thali.local",
                "password": "patient-change-me-2026",
                "role": "patient",
                "facility_id": facility_id,
            },
            {
                "id": DEV_CAREGIVER_USER_ID,
                "email": "caregiver@thali.local",
                "password": "caregiver-change-me-2026",
                "role": "caregiver",
                "facility_id": facility_id,
            },
        ]

        seeded_user_map: dict[str, UserModel] = {}
        for u in users_to_seed:
            existing_user = session.query(UserModel).filter_by(email=u["email"]).first()
            if existing_user:
                seeded_user_map[u["email"]] = existing_user
                print(f"  User already exists: {u['email']}")
            else:
                new_user = UserModel(
                    id=u["id"],
                    email=u["email"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                    tenant_id=tenant_id,
                    facility_id=u["facility_id"],
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(new_user)
                session.flush()
                seeded_user_map[u["email"]] = new_user
                print(f"  Created user: {u['email']} ({u['role']})")

        # ------------------------------------------------------------------
        # 4. Patient (patients table)
        # ------------------------------------------------------------------
        pat = session.query(PatientModel).filter_by(tenant_id=tenant_id, uh_id="UHID-DEV-0001").first()
        if not pat:
            pat = session.query(PatientModel).filter_by(id=DEV_PATIENT_ID).first()
        if not pat:
            pat = PatientModel(
                id=DEV_PATIENT_ID,
                tenant_id=tenant_id,
                facility_id=facility_id,
                uh_id="UHID-DEV-0001",
                name="Sita Sharma",
                phone="+919876543210",
                active=True,
                created_at=now,
            )
            session.add(pat)
            session.flush()
            print(f"  Created patient: {pat.id} ({pat.name}, {pat.uh_id})")
        else:
            print(f"  Patient already exists: {pat.id} ({pat.name})")

        # ------------------------------------------------------------------
        # 5. Identity Patient Mapping (links user patient@thali.local to Sita)
        # ------------------------------------------------------------------
        patient_user = seeded_user_map.get("patient@thali.local")
        if patient_user:
            mapping = session.query(IdentityPatientMappingModel).filter_by(
                tenant_id=tenant_id,
                user_id=patient_user.id,
            ).first()
            if not mapping:
                mapping = IdentityPatientMappingModel(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    user_id=patient_user.id,
                    patient_id=pat.id,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(mapping)
                print(f"  Linked user {patient_user.email} to patient {pat.name}")

        # ------------------------------------------------------------------
        # 5b. Caregiver Relationship (links user caregiver@thali.local to Sita)
        # ------------------------------------------------------------------
        caregiver_user = seeded_user_map.get("caregiver@thali.local")
        if caregiver_user:
            rel = session.query(CaregiverRelationshipModel).filter_by(
                tenant_id=tenant_id,
                caregiver_user_id=caregiver_user.id,
                patient_id=pat.id,
            ).first()
            if not rel:
                from datetime import timedelta
                rel = CaregiverRelationshipModel(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    caregiver_user_id=caregiver_user.id,
                    patient_id=pat.id,
                    relationship_label="Daughter",
                    status="verified",
                    capabilities=["read_glucose", "create_glucose", "read_meal", "create_meal"],
                    verified_at=now,
                    expires_at=now + timedelta(days=365),
                    created_at=now,
                    updated_at=now,
                )
                session.add(rel)
                print(f"  Linked caregiver {caregiver_user.email} to patient {pat.name}")
            else:
                print(f"  Caregiver relationship already exists for {pat.name}")

        # ------------------------------------------------------------------
        # 6. Care Team Member (Doctor)
        # ------------------------------------------------------------------
        doctor_user = seeded_user_map.get("doctor@thali.local")
        if doctor_user:
            ctm = session.query(CareTeamMemberModel).filter_by(
                tenant_id=tenant_id,
                user_id=doctor_user.id,
            ).first()
            if not ctm:
                ctm = CareTeamMemberModel(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    facility_id=facility_id,
                    user_id=doctor_user.id,
                    role="doctor",
                    display_name="Dr. Dev",
                    active=True,
                    created_at=now,
                )
                session.add(ctm)
                print(f"  Enrolled care team member: Dr. Dev ({doctor_user.email})")

        session.commit()

    print("Seed complete.")
    print()
    print("Default credentials:")
    print(f"  admin@thali.local     /  {ADMIN_PASSWORD}")
    print("  doctor@thali.local    /  doctor-change-me-2026")
    print("  nurse@thali.local     /  nurse-change-me-2026")
    print("  patient@thali.local   /  patient-change-me-2026")
    print("  caregiver@thali.local /  caregiver-change-me-2026")


if __name__ == "__main__":
    seed()
