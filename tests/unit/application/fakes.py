"""Deterministic in-memory fakes for Gate 04 application tests.

No network, no database, no external providers. Implements the application
ports with in-memory state so use-case orchestration is fully testable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID

from backend.application.ports.ai import ArtifactDraft
from backend.domain.entities import Patient
from backend.domain.exceptions import EntityNotFound

T = TypeVar("T")

FIXED_NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FakeIdGenerator:
    def __init__(self, seed: int = 1000) -> None:
        self._next = seed

    def new_uuid(self) -> UUID:
        value = UUID(int=self._next)
        self._next += 1
        return value


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class ExplodingEventPublisher:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)
        raise RuntimeError("forced publisher failure")


class FakeAIArtifactGenerator:
    def __init__(
        self,
        summary: str = "deterministic AI summary",
        artifact_kind: str = "extracted_observation",
    ) -> None:
        self.summary = summary
        self.artifact_kind = artifact_kind
        self.calls = 0

    def generate(self, context: str, patient_id: UUID) -> ArtifactDraft:
        self.calls += 1
        return ArtifactDraft(artifact_kind=self.artifact_kind, summary=self.summary)


class FailingAIArtifactGenerator(FakeAIArtifactGenerator):
    def generate(self, context: str, patient_id: UUID) -> ArtifactDraft:
        self.calls += 1
        raise RuntimeError("provider failure")


class InMemoryRepository(Generic[T]):
    """Write-through staged repository. ``commit``/``rollback`` are owned by
    the unit of work; ``save``/``add`` stage writes that only appear in the
    committed store after ``commit``."""

    def __init__(self, stage: dict, committed: dict, kind: str) -> None:
        self._stage = stage
        self._committed = committed
        self._kind = kind

    def _key(self, entity_id: object) -> tuple:
        return (self._kind, entity_id)

    def add(self, entity: T) -> None:
        self._stage[self._key(entity.id)] = entity

    def save(self, entity: T) -> None:
        self._stage[self._key(entity.id)] = entity

    def _find(self, entity_id: object) -> T | None:
        return self._stage.get(self._key(entity_id)) or self._committed.get(
            self._key(entity_id)
        )

    def get(self, entity_id: object) -> T:
        entity = self._find(entity_id)
        if entity is None:
            raise EntityNotFound(f"{self._kind} {entity_id} not found")
        return entity

    def list(self) -> list[T]:
        keys = {k for k in self._committed if k[0] == self._kind}
        keys |= {k for k in self._stage if k[0] == self._kind}
        return [self._find(key[1]) for key in sorted(keys) if self._find(key[1]) is not None]

    def list_for_patient(self, patient_id: UUID) -> list[T]:
        return [e for e in self.list() if e.patient_id == patient_id]


class InMemoryCareTeamMemberStore(InMemoryRepository[T]):
    """Looks members up by their authoritative ``user_id``."""

    def get(self, user_id: object) -> T:
        for entity in self.list():
            if entity.user_id == user_id:
                return entity
        raise EntityNotFound(f"care_team_member with user_id {user_id} not found")

    def get_by_id(self, member_id: object) -> T:
        for entity in self.list():
            if entity.id == member_id:
                return entity
        raise EntityNotFound(f"care_team_member with id {member_id} not found")


class InMemoryCaregiverRelationshipStore(InMemoryRepository[T]):
    """In-memory caregiver relationship repository (Gate 08)."""

    def list_for_caregiver(self, caregiver_user_id: UUID) -> list[T]:
        return [e for e in self.list() if e.caregiver_user_id == caregiver_user_id]

    def list_for_patient(self, patient_id: UUID) -> list[T]:
        return [e for e in self.list() if e.patient_id == patient_id]

    def find_by_pair(
        self, caregiver_user_id: UUID, patient_id: UUID
    ) -> T | None:
        for e in self.list():
            if e.caregiver_user_id == caregiver_user_id and e.patient_id == patient_id:
                return e
        return None

    def get_verified_for_patient(
        self, caregiver_user_id: UUID, patient_id: UUID
    ) -> T | None:
        module = __import__(
            "backend.domain.entities", fromlist=["CaregiverRelationshipStatus"]
        )
        verified = module.CaregiverRelationshipStatus.VERIFIED
        for e in self.list():
            if (
                e.caregiver_user_id == caregiver_user_id
                and e.patient_id == patient_id
                and e.status is verified
            ):
                return e
        return None


class InMemoryIdentityMappingStore(InMemoryRepository[T]):
    """In-memory identity-patient mapping repository (Gate 08)."""

    def get_by_user_id(self, user_id: UUID) -> T | None:
        for e in self.list():
            if e.user_id == user_id:
                return e
        return None

    def get_by_patient_id(self, patient_id: UUID) -> T | None:
        for e in self.list():
            if e.patient_id == patient_id:
                return e
        return None


class InMemoryAIReviewArtifactStore(InMemoryRepository[T]):
    """In-memory AI review artifact repository (Gate 10F-B)."""

    def list_by_state(self, state) -> list[T]:
        return [e for e in self.list() if e.state is state]


class InMemoryCareTaskStore(InMemoryRepository[T]):
    """In-memory care task repository (Gate 10J-B)."""

    def __init__(
        self,
        stage: dict,
        committed: dict,
        kind: str,
        patients_repo: InMemoryRepository | None = None,
    ) -> None:
        super().__init__(stage, committed, kind)
        self._patients_repo = patients_repo

    def list_for_patient(self, patient_id: UUID, status=None) -> list[T]:
        items = [e for e in self.list() if e.patient_id == patient_id]
        if status is not None:
            items = [e for e in items if e.status == status]
        return items

    def list_for_assignee(self, assigned_to_user_id: UUID, status=None) -> list[T]:
        items = [e for e in self.list() if e.assigned_to_user_id == assigned_to_user_id]
        if status is not None:
            items = [e for e in items if e.status == status]
        return items

    def list_for_facility(self, facility_id: UUID, status=None) -> list[T]:
        items = []
        for e in self.list():
            if self._patients_repo is not None:
                p = self._patients_repo._find(e.patient_id)
                if p and getattr(p, "facility_id", None) == facility_id:
                    if status is None or e.status == status:
                        items.append(e)
            else:
                if status is None or e.status == status:
                    items.append(e)
        return items


class InMemoryNotificationStore(InMemoryRepository[T]):
    def list_for_recipient(self, recipient_id: UUID, limit: int = 50, offset: int = 0) -> list[T]:
        items = [e for e in self.list() if getattr(e, "recipient_id", None) == recipient_id]
        return items[offset : offset + limit]

    def list_for_patient(self, patient_id: UUID, limit: int = 50, offset: int = 0) -> list[T]:
        items = [e for e in self.list() if getattr(e, "patient_id", None) == patient_id]
        return items[offset : offset + limit]

    def list_due(self, before: datetime, limit: int = 50) -> list[T]:
        items = [
            e for e in self.list()
            if getattr(e, "status", None) == "pending" and getattr(e, "scheduled_at", None) and e.scheduled_at <= before
        ]
        return items[:limit]

    def list_for_tenant(self, status=None, limit: int = 50, offset: int = 0) -> list[T]:
        items = self.list()
        if status:
            status_val = status.value if hasattr(status, "value") else str(status)
            items = [e for e in items if str(getattr(e, "status", "")) == status_val]
        return items[offset : offset + limit]

    def count_for_tenant(self, status=None) -> int:
        return len(self.list_for_tenant(status=status, limit=10000))


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self._stage: dict = {}
        self._committed: dict = {}
        self.commits = 0
        self.rollbacks = 0
        self.patients = InMemoryRepository(self._stage, self._committed, "patients")
        self.facilities = InMemoryRepository(self._stage, self._committed, "facilities")
        self.care_team_members = InMemoryCareTeamMemberStore(self._stage, self._committed, "care_team_members")
        self.caregiver_relationships = InMemoryCaregiverRelationshipStore(self._stage, self._committed, "caregiver_relationships")
        self.identity_mappings = InMemoryIdentityMappingStore(self._stage, self._committed, "identity_patient_mappings")
        self.glucose_observations = InMemoryRepository(self._stage, self._committed, "glucose_observations")
        self.meal_observations = InMemoryRepository(self._stage, self._committed, "meal_observations")
        self.medication_plans = InMemoryRepository(self._stage, self._committed, "medication_plans")
        self.care_tasks = InMemoryCareTaskStore(self._stage, self._committed, "care_tasks", self.patients)
        self.ai_artifacts = InMemoryAIReviewArtifactStore(self._stage, self._committed, "ai_artifacts")
        self.notifications = InMemoryNotificationStore(self._stage, self._committed, "notifications")

    def commit(self) -> None:
        self._committed.update(self._stage)
        self._stage.clear()
        self.commits += 1

    def rollback(self) -> None:
        self._stage.clear()
        self.rollbacks += 1

    def close(self) -> None:
        pass


def seed_patient(uow: InMemoryUnitOfWork, patient_id: UUID, phone=None) -> Patient:
    from backend.domain.value_objects import PhoneNumber, UHID

    patient = Patient(
        id=patient_id,
        uh_id=UHID("D-0001"),
        name="Test Patient",
        phone=phone if phone is not None else PhoneNumber("+919000000001"),
        created_at=FIXED_NOW,
    )
    uow.patients.add(patient)
    return patient


def seed_member(uow: InMemoryUnitOfWork, member_id: UUID, user_id: UUID, role, name: str = "Clinician"):
    from backend.domain.entities import CareTeamMember

    member = CareTeamMember(
        id=member_id,
        user_id=user_id,
        role=role,
        display_name=name,
    )
    uow.care_team_members.add(member)
    return member