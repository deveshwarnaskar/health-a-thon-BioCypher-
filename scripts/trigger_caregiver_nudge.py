"""CLI utility to evaluate and trigger proactive caregiver companion nudges."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import Settings
from backend.application.ops.contracts import OutboundMessage
from backend.application.services.caregiver_companion import (
    CaregiverMilestone,
    evaluate_patient_caregiver_nudge,
)
from backend.infrastructure.channel.whatsapp_sender import WhatsAppChannelSender
from backend.infrastructure.config.database import create_db_engine, create_session_factory
from backend.infrastructure.persistence.models.patient_models import PatientModel
from backend.infrastructure.persistence.uow.sqlalchemy_uow import SqlAlchemyUnitOfWork


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger proactive caregiver companion nudge")
    parser.add_argument("--phone", default="+916291773811", help="Target patient phone number")
    parser.add_argument(
        "--milestone",
        default="auto",
        choices=[
            "auto",
            "morning_fasting",
            "post_breakfast",
            "lunch_check",
            "post_lunch_pp",
            "evening_wellbeing",
            "dinner_check",
            "bedtime_recap",
        ],
        help="Caregiver milestone to trigger ('auto' for current time)",
    )
    args = parser.parse_args()

    settings = Settings()
    engine = create_db_engine(settings.database.url)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        patient_model = (
            session.query(PatientModel)
            .filter(PatientModel.phone == args.phone)
            .first()
        )
        if not patient_model:
            patient_model = (
                session.query(PatientModel)
                .filter(PatientModel.name.ilike("%subham%"))
                .first()
            )

        if not patient_model:
            print(f"Error: Patient with phone {args.phone} not found in database.")
            sys.exit(1)

        tenant_id = patient_model.tenant_id
        patient_id = patient_model.id
        patient_name = patient_model.name

    uow = SqlAlchemyUnitOfWork(session_factory, tenant_id)
    try:
        patient = uow.patients.get(patient_id)
        forced_milestone = None if args.milestone == "auto" else CaregiverMilestone(args.milestone)

        nudge = evaluate_patient_caregiver_nudge(
            patient,
            uow,
            force_milestone=forced_milestone,
        )

        if not nudge:
            print(f"No nudge due for {patient_name} at this time (auto-milestone or quiet hours/suppression active).")
            print("Try specifying a milestone explicitly, e.g. --milestone morning_fasting or --milestone lunch_check")
            sys.exit(0)

        print("=" * 60)
        print(f"CARE COMPANION NUDGE: [{nudge.milestone.value.upper()}]")
        print(f"Target: {patient_name} ({nudge.recipient_phone})")
        print(f"Urgency: {nudge.urgency}")
        print("=" * 60)
        print("\n--- Message Text ---\n")
        print(nudge.message_text)
        print("\n" + "=" * 60)

        sender = WhatsAppChannelSender(
            phone_number_id=settings.whatsapp.phone_number_id,
            access_token=settings.whatsapp.access_token,
            api_version=settings.whatsapp.api_version,
        )

        outbound = OutboundMessage(
            message_id=uuid.uuid4(),
            tenant_id=tenant_id,
            recipient_phone=nudge.recipient_phone,
            channel_type="WHATSAPP",
            template_name="text",
            template_params={"body": nudge.message_text},
        )

        print("\nSending via Meta Cloud API...")
        res = sender.send(outbound)
        if res.success:
            print(f"SUCCESS! Delivered to WhatsApp. Provider Delivery ID: {res.provider_delivery_id}")
        else:
            print(f"FAILED! Error code: {res.error_code}, Retryable: {res.retryable}")

    finally:
        uow.close()


if __name__ == "__main__":
    main()
