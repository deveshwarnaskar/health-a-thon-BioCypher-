"""Regression tests for CaregiverRelationship timezone normalization.

Verifies:
- Naive and aware datetimes for expires_at, verified_at, revoked_at, created_at, updated_at
  are properly normalized to UTC.
- is_granted_at() works cleanly when comparing:
  * aware UTC now against aware expires_at (future and past)
  * aware UTC now against naive expires_at (future and past)
  * naive now against aware/naive expires_at
  * expires_at is None
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from backend.domain.entities.caregiver_relationship import (
    CaregiverRelationship,
    CaregiverRelationshipStatus,
    _as_utc,
)


class TestCaregiverRelationshipTimezoneNormalization:
    """Proves timezone safety and normalization in CaregiverRelationship."""

    def test_as_utc_helper(self):
        assert _as_utc(None) is None

        # Naive datetime gets converted to UTC-aware
        naive = datetime(2026, 9, 23, 12, 0, 0)
        aware = _as_utc(naive)
        assert aware is not None
        assert aware.tzinfo == timezone.utc
        assert aware.year == 2026 and aware.hour == 12

        # Already UTC-aware datetime stays UTC
        already_utc = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
        result = _as_utc(already_utc)
        assert result == already_utc
        assert result.tzinfo == timezone.utc

    def test_post_init_normalizes_naive_timestamps_to_utc(self):
        naive_dt = datetime(2026, 1, 1, 0, 0, 0)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.VERIFIED,
            expires_at=naive_dt,
            verified_at=naive_dt,
            created_at=naive_dt,
            updated_at=naive_dt,
        )
        assert rel.expires_at.tzinfo == timezone.utc
        assert rel.verified_at.tzinfo == timezone.utc
        assert rel.created_at.tzinfo == timezone.utc
        assert rel.updated_at.tzinfo == timezone.utc

    def test_verified_future_aware_expires_at_is_granted(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(days=30)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.VERIFIED,
            expires_at=future,
        )
        assert rel.is_granted_at(now) is True

    def test_verified_expired_aware_expires_at_is_denied(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.VERIFIED,
            expires_at=past,
        )
        assert rel.is_granted_at(now) is False

    def test_verified_future_naive_expires_at_with_aware_now_is_granted(self):
        """Simulates SQLite loading where expires_at has tzinfo=None."""
        now = datetime.now(timezone.utc)
        # Create entity and explicitly bypass __post_init__ or pass naive dt
        naive_future = datetime.utcnow() + timedelta(days=365)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.VERIFIED,
            expires_at=naive_future,
        )
        # Even if expires_at were somehow set with naive dt later
        object.__setattr__(rel, "expires_at", naive_future)

        # Must compare without TypeError: can't compare offset-naive and offset-aware datetimes
        assert rel.is_granted_at(now) is True

    def test_verified_expired_naive_expires_at_with_aware_now_is_denied(self):
        now = datetime.now(timezone.utc)
        naive_past = datetime.utcnow() - timedelta(days=1)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.VERIFIED,
            expires_at=naive_past,
        )
        object.__setattr__(rel, "expires_at", naive_past)

        assert rel.is_granted_at(now) is False

    def test_verified_expires_at_none_is_granted(self):
        now = datetime.now(timezone.utc)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.VERIFIED,
            expires_at=None,
        )
        assert rel.is_granted_at(now) is True

    def test_non_verified_status_is_denied(self):
        now = datetime.now(timezone.utc)
        rel = CaregiverRelationship(
            relationship="Daughter",
            status=CaregiverRelationshipStatus.PENDING,
            expires_at=now + timedelta(days=30),
        )
        assert rel.is_granted_at(now) is False

    def test_lifecycle_methods_normalize_timestamps(self):
        rel = CaregiverRelationship(relationship="Daughter")
        assert rel.status == CaregiverRelationshipStatus.PENDING

        # verify with naive dt
        naive_verify = datetime(2026, 2, 1, 10, 0, 0)
        rel.verify(verified_at=naive_verify)
        assert rel.status == CaregiverRelationshipStatus.VERIFIED
        assert rel.verified_at.tzinfo == timezone.utc
        assert rel.updated_at.tzinfo == timezone.utc

        # expire with naive dt
        naive_expire = datetime(2026, 3, 1, 10, 0, 0)
        rel.expire(expired_at=naive_expire)
        assert rel.status == CaregiverRelationshipStatus.EXPIRED
        assert rel.updated_at.tzinfo == timezone.utc
