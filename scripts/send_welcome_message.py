"""Utility script to dispatch the personalized welcome message to a patient."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from config.settings import Settings
from backend.domain.value_objects import PhoneNumber
from backend.application.ops.contracts import OutboundMessage
from backend.infrastructure.channel.whatsapp_sender import WhatsAppChannelSender
from backend.application.services.welcome_template import build_welcome_message
from backend.infrastructure.config.database import create_db_engine, create_session_factory
from backend.infrastructure.persistence.models.patient_models import PatientModel


def main():
    settings = Settings()
    engine = create_db_engine(settings.database.url)
    session_factory = create_session_factory(engine)

    phone_target = sys.argv[1] if len(sys.argv) > 1 else "+916291773811"

    with session_factory() as session:
        patient = (
            session.query(PatientModel)
            .filter(PatientModel.phone == phone_target)
            .first()
        )
        if patient is None:
            # Fallback query by any active patient
            patient = session.query(PatientModel).filter(PatientModel.name.ilike("%subham%")).first()

        patient_name = patient.name if patient else "SUBHAM DAS"
        tenant_id = patient.tenant_id if patient else uuid.uuid4()

    print(f"Target phone: {phone_target}")
    print(f"Patient name resolved from DB: '{patient_name}'")

    welcome_text = build_welcome_message(patient_name)
    print("\n--- Free-form Message Preview ---\n")
    print(welcome_text)
    print("\n-----------------------\n")

    from backend.infrastructure.channel.template_registry import WhatsAppTemplateRegistry

    template_name = WhatsAppTemplateRegistry(settings=settings).resolve_welcome_template()
    print(f"Resolved welcome template: {template_name}")
    if template_name == "text":
        template_params = {"body": welcome_text}
    elif template_name in ("thali_welcome", "thali_welcome_greeting"):
        template_params = {"1": patient_name, "_language": "en"}
    else:
        template_params = {"_language": "en"}

    sender = WhatsAppChannelSender(
        phone_number_id=settings.whatsapp.phone_number_id,
        access_token=settings.whatsapp.access_token,
        api_version=settings.whatsapp.api_version,
    )

    msg = OutboundMessage(
        message_id=uuid.uuid4(),
        tenant_id=tenant_id,
        recipient_phone=phone_target,
        channel_type="WHATSAPP",
        template_name=template_name,
        template_params=template_params,
    )

    print("Sending message via Meta Cloud API...")
    res = sender.send(msg)

    if res.success:
        print(f"SUCCESS! Message delivered. Delivery ID: {res.provider_delivery_id}")
    else:
        print(f"FAILED! Error code: {res.error_code}")
        print(f"Retryable: {res.retryable}")


if __name__ == "__main__":
    main()
