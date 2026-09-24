"""Tests for SqlAlchemyConversationSessionStore (Gate 11, spec §5).

Verifies:
1. get() returns a fresh IDLE session when no row exists.
2. save() persists the session pointer (state/draft/fingerprint/context).
3. A new store instance recovers the persisted draft after "restart".
4. Multiple tenants row-separated; patient-bound keying is tenant-scoped.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.application.ops.conversation.state import (
    ConversationState,
    ConversationSession,
    DraftKind,
    fingerprint_medication,
)
from backend.infrastructure.persistence.models import Base, OrganizationModel
from backend.infrastructure.persistence.ops.conversation_session_store import (
    SqlAlchemyConversationSessionStore,
)


@pytest.fixture
def tenant_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def make_tenant():
        tenant_id = uuid4()
        with session_factory() as session:
            session.add(
                OrganizationModel(
                    id=tenant_id,
                    name="Test Hospital",
                    slug=f"test-hospital-{tenant_id.hex[:8]}",
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        return tenant_id

    return make_tenant, session_factory


def test_get_returns_fresh_idle_session(tenant_factory):
    make_tenant, session_factory = tenant_factory
    tenant_id = make_tenant()
    store = SqlAlchemyConversationSessionStore(session_factory)

    session = store.get(tenant_id, uuid4())

    assert session.state == ConversationState.IDLE
    assert session.draft_kind == DraftKind.NONE
    assert session.draft_fingerprint == ""


def test_save_then_recover_draft_across_restart(tenant_factory):
    make_tenant, session_factory = tenant_factory
    tenant_id = make_tenant()
    patient_id = uuid4()
    store = SqlAlchemyConversationSessionStore(session_factory)

    draft = ConversationSession(tenant_id=tenant_id, patient_id=patient_id)
    draft.mark_draft(
        DraftKind.MEDICATION,
        fingerprint_medication(medication="metformin", when="morning"),
        {"display": "metformin subah"},
    )
    store.save(draft)

    recovered = SqlAlchemyConversationSessionStore(session_factory).get(tenant_id, patient_id)
    assert recovered.state == ConversationState.AWAITING_MEDICATION_CONFIRM
    assert recovered.draft_kind == DraftKind.MEDICATION
    assert recovered.draft_fingerprint == "med:metformin:morning"
    assert recovered.context == {"display": "metformin subah"}


def test_tenants_are_row_separated(tenant_factory):
    make_tenant, session_factory = tenant_factory
    tenant_a = make_tenant()
    tenant_b = make_tenant()
    shared_patient = uuid4()
    store = SqlAlchemyConversationSessionStore(session_factory)

    draft_a = ConversationSession(tenant_id=tenant_a, patient_id=shared_patient)
    draft_a.mark_draft(DraftKind.GLUCOSE, "g:140:fasting", {})
    store.save(draft_a)

    b_session = SqlAlchemyConversationSessionStore(session_factory).get(tenant_b, shared_patient)
    assert b_session.state == ConversationState.IDLE

    a_session = SqlAlchemyConversationSessionStore(session_factory).get(tenant_a, shared_patient)
    assert a_session.state == ConversationState.AWAITING_GLUCOSE_CONFIRM


def test_reset_persists_clear(tenant_factory):
    make_tenant, session_factory = tenant_factory
    tenant_id = make_tenant()
    patient_id = uuid4()
    store = SqlAlchemyConversationSessionStore(session_factory)

    draft = ConversationSession(tenant_id=tenant_id, patient_id=patient_id)
    draft.mark_draft(DraftKind.CARE_TASK, "t:walk", {"when": "kal 8 baje"})
    store.save(draft)

    draft.reset(datetime.now(timezone.utc))
    store.save(draft)

    recovered = SqlAlchemyConversationSessionStore(session_factory).get(tenant_id, patient_id)
    assert recovered.is_awaiting(DraftKind.CARE_TASK) is False
    assert recovered.state == ConversationState.IDLE