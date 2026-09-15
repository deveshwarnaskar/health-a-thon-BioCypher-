"""Gate 08 application-layer tests (in-memory).

Proves use-case orchestration for caregiver relationships and identity
mappings, including duplicate rejection, lifecycle state machines, canonical
event publication, and identity→patient resolution semantics. No network, no
database.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.application.commands import (
    CreateIdentityMapping,
    DeactivateIdentityMapping,
    RegisterCaregiverRelationship,
    RevokeCaregiverRelationship,
    VerifyCaregiverRelationship,
)
from backend.application.exceptions import (
    DuplicateCaregiverRelationship,
    DuplicateIdentityMapping,
)
from backend.domain.entities import CaregiverRelationshipStatus
from backend.domain.events import (
    CaregiverRelationshipCreated,
    CaregiverRelationshipRevoked,
    CaregiverRelationshipVerified,
    IdentityMappingCreated,
    IdentityMappingDeactivated,
)
from backend.domain.exceptions import (
    EntityNotFound,
    InvalidRelationship,
    InvalidStateTransition,
)

from conftest import PATIENT_ID

PATIENT_ID_2 = uuid4()


class TestCaregiverRelationshipLifecycle:
    def test_register_creates_pending(self, world):
        cg = uuid4()
        result = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID,
                caregiver_user_id=cg,
                relationship_label="spouse",
                capabilities=frozenset({"read_glucose", "read_meal"}),
            )
        )
        assert result.status == "pending"
        rel = world["uow"].caregiver_relationships.get(result.relationship_id)
        assert rel.status is CaregiverRelationshipStatus.PENDING
        assert rel.capabilities == frozenset({"read_glucose", "read_meal"})
        assert not rel.active

        published = [e for e in world["events"].published if isinstance(e, CaregiverRelationshipCreated)]
        assert len(published) == 1
        assert published[0].relationship_id == result.relationship_id

    def test_verify_grants_active(self, world):
        cg = uuid4()
        reg = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID,
                caregiver_user_id=cg,
                relationship_label="parent",
            )
        )
        result = world["app"].verify_caregiver.handle(
            VerifyCaregiverRelationship(relationship_id=reg.relationship_id)
        )
        assert result.status == "verified"
        rel = world["uow"].caregiver_relationships.get(reg.relationship_id)
        assert rel.active
        assert rel.verified_at is not None
        published = [e for e in world["events"].published if isinstance(e, CaregiverRelationshipVerified)]
        assert len(published) == 1

    def test_verify_rejects_non_pending(self, world):
        cg = uuid4()
        reg = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="x"
            )
        )
        world["app"].verify_caregiver.handle(VerifyCaregiverRelationship(relationship_id=reg.relationship_id))
        with pytest.raises(InvalidStateTransition):
            world["app"].verify_caregiver.handle(VerifyCaregiverRelationship(relationship_id=reg.relationship_id))

    def test_revoke_denies_access_lifecycle(self, world):
        cg = uuid4()
        reg = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="x"
            )
        )
        result = world["app"].revoke_caregiver.handle(
            RevokeCaregiverRelationship(relationship_id=reg.relationship_id)
        )
        assert result.status == "revoked"
        rel = world["uow"].caregiver_relationships.get(reg.relationship_id)
        assert not rel.active
        assert rel.revoked_at is not None
        published = [e for e in world["events"].published if isinstance(e, CaregiverRelationshipRevoked)]
        assert len(published) == 1

    def test_revoke_already_revoked_raises(self, world):
        cg = uuid4()
        reg = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="x"
            )
        )
        world["app"].revoke_caregiver.handle(RevokeCaregiverRelationship(relationship_id=reg.relationship_id))
        with pytest.raises(InvalidRelationship):
            world["app"].revoke_caregiver.handle(RevokeCaregiverRelationship(relationship_id=reg.relationship_id))

    def test_duplicate_active_relationship_rejected(self, world):
        cg = uuid4()
        world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="x"
            )
        )
        with pytest.raises(DuplicateCaregiverRelationship):
            world["app"].register_caregiver.handle(
                RegisterCaregiverRelationship(
                    patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="y"
                )
            )

    def test_revoked_relationship_does_not_block_new_registration(self, world):
        cg = uuid4()
        reg = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="x"
            )
        )
        world["app"].revoke_caregiver.handle(RevokeCaregiverRelationship(relationship_id=reg.relationship_id))
        reg2 = world["app"].register_caregiver.handle(
            RegisterCaregiverRelationship(
                patient_id=PATIENT_ID, caregiver_user_id=cg, relationship_label="y"
            )
        )
        assert reg2.relationship_id != reg.relationship_id


class TestIdentityMappingLifecycle:
    def _seed_second_patient(self, world):
        from tests.unit.application.fakes import seed_patient

        seed_patient(world["uow"], PATIENT_ID_2)
        world["uow"].commit()

    def test_create_mapping_publishes_event(self, world):
        user_id = uuid4()
        result = world["app"].create_identity_mapping.handle(
            CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID)
        )
        assert result.active is True
        published = [e for e in world["events"].published if isinstance(e, IdentityMappingCreated)]
        assert len(published) == 1
        assert published[0].user_id == user_id
        assert published[0].patient_id == PATIENT_ID

    def test_duplicate_mapping_for_user_rejected(self, world):
        user_id = uuid4()
        self._seed_second_patient(world)
        world["app"].create_identity_mapping.handle(CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID))
        with pytest.raises(DuplicateIdentityMapping):
            world["app"].create_identity_mapping.handle(CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID_2))

    def test_duplicate_mapping_for_patient_rejected(self, world):
        user_id = uuid4()
        world["app"].create_identity_mapping.handle(CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID))
        with pytest.raises(DuplicateIdentityMapping):
            world["app"].create_identity_mapping.handle(CreateIdentityMapping(user_id=uuid4(), patient_id=PATIENT_ID))

    def test_deactivate_mapping_yields_inactive(self, world):
        user_id = uuid4()
        created = world["app"].create_identity_mapping.handle(
            CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID)
        )
        result = world["app"].deactivate_identity_mapping.handle(
            DeactivateIdentityMapping(mapping_id=created.mapping_id)
        )
        assert result.active is False
        published = [e for e in world["events"].published if isinstance(e, IdentityMappingDeactivated)]
        assert len(published) == 1
        assert published[0].mapping_id == created.mapping_id

    def test_mapping_to_missing_patient_rejected(self, world):
        with pytest.raises(EntityNotFound):
            world["app"].create_identity_mapping.handle(
                CreateIdentityMapping(user_id=uuid4(), patient_id=uuid4())
            )


class TestIdentityResolver:
    def test_no_mapping_is_inactive(self, world):
        resolved = world["app"].identity_resolver.resolve(uuid4())
        assert resolved.active is False
        assert resolved.patient_id is None

    def test_active_mapping_resolves_to_patient(self, world):
        user_id = uuid4()
        world["app"].create_identity_mapping.handle(CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID))
        resolved = world["app"].identity_resolver.resolve(user_id)
        assert resolved.active is True
        assert resolved.patient_id == PATIENT_ID

    def test_deactivated_mapping_is_inactive(self, world):
        user_id = uuid4()
        created = world["app"].create_identity_mapping.handle(
            CreateIdentityMapping(user_id=user_id, patient_id=PATIENT_ID)
        )
        world["app"].deactivate_identity_mapping.handle(DeactivateIdentityMapping(mapping_id=created.mapping_id))
        resolved = world["app"].identity_resolver.resolve(user_id)
        assert resolved.active is False
        assert resolved.patient_id == PATIENT_ID

    def test_mapping_to_stale_patient_resolves_inactive(self, world):
        user_id = uuid4()
        stale_patient_id = uuid4()
        from backend.domain.entities import IdentityPatientMapping

        world["uow"].identity_mappings.add(
            IdentityPatientMapping(
                user_id=user_id,
                patient_id=stale_patient_id,
                active=True,
            )
        )
        resolved = world["app"].identity_resolver.resolve(user_id)
        assert resolved.active is False
        assert resolved.patient_id == stale_patient_id