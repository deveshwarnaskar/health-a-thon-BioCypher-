"""Target-stack synthetic demo seed script (Gate 10J-B).

Populates the v2 target PostgreSQL / relational schema with a realistic, multi-facility
demo deployment for testing and demonstration:

1. Organization:
   - demo-health (tenant)
2. Facilities:
   - Facility A: Demo General Hospital (Urban Primary Facility)
   - Facility B: Demo Rural Clinic (Secondary / Peripheral Facility)
3. 5 Workforce Roles:
   - Doctor (Facility A)
   - Nurse (Facility A)
   - Care Coordinator (Facility A)
   - Dietitian (Facility A)
   - Field Health Worker / FHW (Facility A)
   - Doctor B (Facility B, for cross-facility isolation testing)
4. Patients:
   - Active patient in Facility A
   - Active patient in Facility A with verified caregiver
   - Deactivated patient in Facility A
   - Active patient in Facility B (for cross-facility boundary testing)
5. Care Tasks:
   - Tasks across lifecycle states (OPEN, IN_PROGRESS, COMPLETED) with due_at
   - Tasks assigned to FHW, Nurse, Coordinator, Doctor
6. Observations:
   - Glucose observations (fasting, postprandial)
   - Meal observations with calibrated portions and computed carbs/GI

Idempotent: Safe to run multiple times against the target database.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.domain.services.carbohydrate_calculator import CarbohydrateCalculator
from backend.infrastructure.persistence.models.base import Base
from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
from backend.infrastructure.persistence.models.identity_models import (
    CaregiverRelationshipModel,
    IdentityPatientMappingModel,
)
from backend.infrastructure.persistence.models.observation_models import (
    GlucoseObservationModel,
    MealObservationModel,
)
from backend.infrastructure.persistence.models.patient_models import PatientModel
from backend.infrastructure.persistence.models.plan_models import (
    CareTaskModel,
    MedicationPlanModel,
)
from backend.infrastructure.persistence.models.tenant_models import (
    FacilityModel,
    OrganizationModel,
)

# ─── Deterministic Demo UUIDs ────────────────────────────────────────────────
DEMO_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
FACILITY_A_ID = UUID("00000000-0000-0000-0000-000000000010")
FACILITY_B_ID = UUID("00000000-0000-0000-0000-000000000020")

# Workforce users (Keycloak/JWT actor IDs)
DOCTOR_ID = UUID("00000000-0000-0000-0000-000000000101")
NURSE_ID = UUID("00000000-0000-0000-0000-000000000102")
COORDINATOR_ID = UUID("00000000-0000-0000-0000-000000000103")
DIETITIAN_ID = UUID("00000000-0000-0000-0000-000000000104")
FHW_ID = UUID("00000000-0000-0000-0000-000000000105")
DOCTOR_B_ID = UUID("00000000-0000-0000-0000-000000000106")

# Patients
PATIENT_1_ID = UUID("00000000-0000-0000-0000-000000000201")  # Active, Facility A
PATIENT_2_ID = UUID("00000000-0000-0000-0000-000000000202")  # Active with caregiver, Facility A
PATIENT_3_ID = UUID("00000000-0000-0000-0000-000000000203")  # Deactivated, Facility A
PATIENT_4_ID = UUID("00000000-0000-0000-0000-000000000204")  # Active, Facility B (cross-facility)

# Proxy users
CAREGIVER_USER_ID = UUID("00000000-0000-0000-0000-000000000301")
PATIENT_1_USER_ID = UUID("00000000-0000-0000-0000-000000000302")

# Care tasks
TASK_1_ID = UUID("00000000-0000-0000-0000-000000000401")
TASK_2_ID = UUID("00000000-0000-0000-0000-000000000402")
TASK_3_ID = UUID("00000000-0000-0000-0000-000000000403")
TASK_4_ID = UUID("00000000-0000-0000-0000-000000000404")

# Observations
GLUCOSE_1_ID = UUID("00000000-0000-0000-0000-000000000501")
GLUCOSE_2_ID = UUID("00000000-0000-0000-0000-000000000502")
MEAL_1_ID = UUID("00000000-0000-0000-0000-000000000601")
MEAL_2_ID = UUID("00000000-0000-0000-0000-000000000602")


def clean_existing_demo_fixtures(session: Session) -> None:
    """Safely clear previous demo data for idempotent re-runs."""
    # Delete observations
    session.query(GlucoseObservationModel).filter(
        GlucoseObservationModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)
    session.query(MealObservationModel).filter(
        MealObservationModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)
    session.query(MedicationPlanModel).filter(
        MedicationPlanModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    # Delete care tasks
    session.query(CareTaskModel).filter(
        CareTaskModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    # Delete caregiver relationships and identity mappings
    session.query(CaregiverRelationshipModel).filter(
        CaregiverRelationshipModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)
    session.query(IdentityPatientMappingModel).filter(
        IdentityPatientMappingModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    # Delete patients
    session.query(PatientModel).filter(
        PatientModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    # Delete workforce members
    session.query(CareTeamMemberModel).filter(
        CareTeamMemberModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    # Delete facilities
    session.query(FacilityModel).filter(
        FacilityModel.tenant_id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    # Delete organization
    session.query(OrganizationModel).filter(
        OrganizationModel.id == DEMO_TENANT_ID
    ).delete(synchronize_session=False)

    session.flush()


def seed_target_stack(session: Session) -> dict[str, Any]:
    """Populate the synthetic target-stack demo data."""
    clean_existing_demo_fixtures(session)

    now = datetime.now(timezone.utc)
    calc = CarbohydrateCalculator()

    # 1. Organization
    org = OrganizationModel(
        id=DEMO_TENANT_ID,
        name="Demo Health System",
        slug="demo-health",
    )
    session.add(org)

    # 2. Facilities
    fac_a = FacilityModel(
        id=FACILITY_A_ID,
        tenant_id=DEMO_TENANT_ID,
        name="Demo General Hospital (Facility A)",
    )
    fac_b = FacilityModel(
        id=FACILITY_B_ID,
        tenant_id=DEMO_TENANT_ID,
        name="Demo Rural Clinic (Facility B)",
    )
    session.add_all([fac_a, fac_b])

    # 3. Workforce (5 roles in Facility A + 1 in Facility B)
    workforce = [
        CareTeamMemberModel(
            tenant_id=DEMO_TENANT_ID,
            user_id=DOCTOR_ID,
            facility_id=FACILITY_A_ID,
            role="doctor",
            display_name="Dr. Arvind Sharma",
            active=True,
        ),
        CareTeamMemberModel(
            tenant_id=DEMO_TENANT_ID,
            user_id=NURSE_ID,
            facility_id=FACILITY_A_ID,
            role="nurse",
            display_name="Nurse Priya Patel",
            active=True,
        ),
        CareTeamMemberModel(
            tenant_id=DEMO_TENANT_ID,
            user_id=COORDINATOR_ID,
            facility_id=FACILITY_A_ID,
            role="care_coordinator",
            display_name="Coordinator Rahul Verma",
            active=True,
        ),
        CareTeamMemberModel(
            tenant_id=DEMO_TENANT_ID,
            user_id=DIETITIAN_ID,
            facility_id=FACILITY_A_ID,
            role="dietitian",
            display_name="Dietitian Sunita Rao",
            active=True,
        ),
        CareTeamMemberModel(
            tenant_id=DEMO_TENANT_ID,
            user_id=FHW_ID,
            facility_id=FACILITY_A_ID,
            role="field_health_worker",
            display_name="FHW Meena Devi",
            active=True,
        ),
        CareTeamMemberModel(
            tenant_id=DEMO_TENANT_ID,
            user_id=DOCTOR_B_ID,
            facility_id=FACILITY_B_ID,
            role="doctor",
            display_name="Dr. Vikram Singh",
            active=True,
        ),
    ]
    session.add_all(workforce)

    # 4. Patients
    patients = [
        PatientModel(
            id=PATIENT_1_ID,
            tenant_id=DEMO_TENANT_ID,
            facility_id=FACILITY_A_ID,
            uh_id="DEMO-P-001",
            name="Ramesh Kumar",
            phone="+919800000001",
            active=True,
        ),
        PatientModel(
            id=PATIENT_2_ID,
            tenant_id=DEMO_TENANT_ID,
            facility_id=FACILITY_A_ID,
            uh_id="DEMO-P-002",
            name="Sita Devi",
            phone="+919800000002",
            active=True,
        ),
        PatientModel(
            id=PATIENT_3_ID,
            tenant_id=DEMO_TENANT_ID,
            facility_id=FACILITY_A_ID,
            uh_id="DEMO-P-003",
            name="Anil Verma",
            phone="+919800000003",
            active=False,  # Deactivated
        ),
        PatientModel(
            id=PATIENT_4_ID,
            tenant_id=DEMO_TENANT_ID,
            facility_id=FACILITY_B_ID,
            uh_id="DEMO-P-004",
            name="Sunita Sharma",
            phone="+919800000004",
            active=True,  # Facility B
        ),
    ]
    session.add_all(patients)

    # 5. Identity mappings & Caregiver relationships
    identity_mapping = IdentityPatientMappingModel(
        tenant_id=DEMO_TENANT_ID,
        user_id=PATIENT_1_USER_ID,
        patient_id=PATIENT_1_ID,
        active=True,
    )
    caregiver_rel = CaregiverRelationshipModel(
        tenant_id=DEMO_TENANT_ID,
        caregiver_user_id=CAREGIVER_USER_ID,
        patient_id=PATIENT_2_ID,
        relationship_label="daughter",
        status="verified",
        capabilities=["read_observations", "read_medication_plans", "read_care_tasks", "complete_care_tasks"],
        verified_at=now - timedelta(days=5),
        expires_at=now + timedelta(days=90),
    )
    session.add_all([identity_mapping, caregiver_rel])

    # 6. Care Tasks (with due_at and status progression)
    tasks = [
        CareTaskModel(
            id=TASK_1_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_1_ID,
            assigned_to_user_id=FHW_ID,
            description="Perform home fasting glucose check",
            status="open",
            due_at=now + timedelta(days=2),
            created_at=now - timedelta(days=1),
        ),
        CareTaskModel(
            id=TASK_2_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_2_ID,
            assigned_to_user_id=FHW_ID,
            description="Follow-up on postprandial dietary adherence",
            status="in_progress",
            due_at=now + timedelta(days=1),
            created_at=now - timedelta(days=2),
        ),
        CareTaskModel(
            id=TASK_3_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_1_ID,
            assigned_to_user_id=NURSE_ID,
            description="Weekly clinical review of vitals",
            status="completed",
            due_at=now - timedelta(days=1),
            created_at=now - timedelta(days=3),
            completed_at=now - timedelta(days=1),
        ),
        CareTaskModel(
            id=TASK_4_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_4_ID,
            assigned_to_user_id=DOCTOR_B_ID,
            description="Facility B initial intake assessment",
            status="open",
            due_at=now + timedelta(days=3),
            created_at=now - timedelta(hours=6),
        ),
    ]
    session.add_all(tasks)

    # 7. Glucose Observations
    glucose_obs = [
        GlucoseObservationModel(
            id=GLUCOSE_1_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_1_ID,
            taken_at=now - timedelta(hours=8),
            value_mg_dl=115,
            tag="fasting",
            confirmation="confirmed",
            confirmed_by="+919800000001",
        ),
        GlucoseObservationModel(
            id=GLUCOSE_2_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_2_ID,
            taken_at=now - timedelta(hours=2),
            value_mg_dl=148,
            tag="postprandial",
            confirmation="confirmed",
            confirmed_by="+919800000002",
        ),
    ]
    session.add_all(glucose_obs)

    # 8. Meal Observations with deterministic carbs & GI
    meal_1_calc = calc.calculate("roti", volume_ml=220, quantity=2.0)
    meal_2_calc = calc.calculate("white rice", volume_ml=220, quantity=1.0)

    meals = [
        MealObservationModel(
            id=MEAL_1_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_1_ID,
            recorded_at=now - timedelta(hours=4),
            description="2 rotis and 1 bowl dal",
            portion_food_key="roti",
            portion_volume_ml=220,
            portion_quantity=2.0,
            carbs_grams=meal_1_calc.carbs_grams,
            glycemic_index=meal_1_calc.glycemic_index,
            confirmation="confirmed",
            confirmed_by="+919800000001",
        ),
        MealObservationModel(
            id=MEAL_2_ID,
            tenant_id=DEMO_TENANT_ID,
            patient_id=PATIENT_2_ID,
            recorded_at=now - timedelta(hours=3),
            description="1 bowl white rice with mixed sabzi",
            portion_food_key="white rice",
            portion_volume_ml=220,
            portion_quantity=1.0,
            carbs_grams=meal_2_calc.carbs_grams,
            glycemic_index=meal_2_calc.glycemic_index,
            confirmation="confirmed",
            confirmed_by="+919800000002",
        ),
    ]
    session.add_all(meals)

    session.commit()

    return {
        "tenant_id": DEMO_TENANT_ID,
        "facility_a_id": FACILITY_A_ID,
        "facility_b_id": FACILITY_B_ID,
        "workforce": {
            "doctor": DOCTOR_ID,
            "nurse": NURSE_ID,
            "coordinator": COORDINATOR_ID,
            "dietitian": DIETITIAN_ID,
            "fhw": FHW_ID,
            "doctor_b": DOCTOR_B_ID,
        },
        "patients": {
            "active_p1": PATIENT_1_ID,
            "caregiver_p2": PATIENT_2_ID,
            "deactivated_p3": PATIENT_3_ID,
            "facility_b_p4": PATIENT_4_ID,
        },
        "tasks": [TASK_1_ID, TASK_2_ID, TASK_3_ID, TASK_4_ID],
        "glucose": [GLUCOSE_1_ID, GLUCOSE_2_ID],
        "meals": [MEAL_1_ID, MEAL_2_ID],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed GLYCOCARE target-stack demo database.")
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL", "sqlite:///target_stack_demo.db"),
        help="Database URL to connect to (defaults to $DATABASE_URL or sqlite:///target_stack_demo.db)",
    )
    args = parser.parse_args()

    print(f"Connecting to {args.db_url}...")
    engine = create_engine(args.db_url)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        result = seed_target_stack(session)
        print(f"Successfully seeded target-stack demo fixtures for tenant: {result['tenant_id']}")
        print(f"  Facilities: 2 (Facility A: {result['facility_a_id']}, Facility B: {result['facility_b_id']})")
        print(f"  Workforce roles: {len(result['workforce'])} members seeded")
        print(f"  Patients: {len(result['patients'])} patients seeded")
        print(f"  Care tasks: {len(result['tasks'])} tasks seeded")
        print(f"  Observations: {len(result['glucose'])} glucose, {len(result['meals'])} meals seeded")


if __name__ == "__main__":
    main()
