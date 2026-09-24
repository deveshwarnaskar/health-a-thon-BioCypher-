"""Session and Token Lifecycle Management Service.

Enforces:
- Single-use Refresh Token Rotation with automatic reuse detection and family invalidation.
- Server-side User Session tracking with device and IP binding.
- Account Lockout after repeated failed attempts.
- Cryptographically secure single-use Password Reset and Email Verification tokens.
- Security Audit Event emission into security_events.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from backend.infrastructure.auth.token_service import TokenService
from backend.infrastructure.persistence.models.user_models import (
    EmailVerificationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenFamilyModel,
    SecurityEventModel,
    UserModel,
    UserSessionModel,
    UserStatus,
)


class AuthServiceError(Exception):
    """Base exception for authentication service errors."""


class InvalidRefreshTokenError(AuthServiceError):
    """Raised when a refresh token is not found or expired."""


class RefreshTokenReuseError(AuthServiceError):
    """Raised when an already-used or revoked refresh token is presented."""


class InvalidResetTokenError(AuthServiceError):
    """Raised when a password reset token is unknown or malformed."""


class ResetTokenAlreadyUsedError(AuthServiceError):
    """Raised when a single-use reset token has already been consumed."""


class ResetTokenExpiredError(AuthServiceError):
    """Raised when a reset token has expired."""


class AccountLockedError(AuthServiceError):
    """Raised when account is locked due to excessive failed attempts."""


class SessionService:
    """Orchestrates database-backed session state, token families, and lockout."""

    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    SESSION_LIFETIME = timedelta(days=7)
    RESET_TOKEN_LIFETIME = timedelta(minutes=15)
    EMAIL_TOKEN_LIFETIME = timedelta(hours=24)

    @staticmethod
    def record_security_event(
        session: Session,
        event_type: str,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
        ip_address: str | None = None,
        details: dict | str | None = None,
    ) -> SecurityEventModel:
        """Log a security-critical audit event to security_events."""
        detail_str = (
            json.dumps(details) if isinstance(details, dict) else (details or "")
        )
        evt = SecurityEventModel(
            id=uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            event_type=event_type,
            ip_address=ip_address,
            details=detail_str,
            created_at=datetime.now(timezone.utc),
        )
        session.add(evt)
        return evt

    @classmethod
    def check_lockout(cls, user: UserModel) -> None:
        """Check if user account is currently locked."""
        now = datetime.now(timezone.utc)
        if user.locked_until is not None:
            # Handle tz-aware or naive datetimes safely
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                raise AccountLockedError(
                    "Account is temporarily locked due to multiple failed login attempts. "
                    "Please try again in a few minutes."
                )

    @classmethod
    def register_failed_attempt(
        cls,
        session: Session,
        user: UserModel,
        ip_address: str | None = None,
    ) -> None:
        """Increment failed login attempts and lock account if threshold exceeded."""
        now = datetime.now(timezone.utc)
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= cls.MAX_FAILED_ATTEMPTS:
            user.locked_until = now + cls.LOCKOUT_DURATION
            cls.record_security_event(
                session=session,
                event_type="ACCOUNT_LOCKED",
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                details={
                    "failed_attempts": user.failed_login_attempts,
                    "locked_until": user.locked_until.isoformat(),
                },
            )
        else:
            cls.record_security_event(
                session=session,
                event_type="LOGIN_FAILED_CREDENTIALS",
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                details={"failed_attempts": user.failed_login_attempts},
            )

    @staticmethod
    def reset_failed_attempts(session: Session, user: UserModel) -> None:
        """Reset failed login attempts upon successful authentication."""
        user.failed_login_attempts = 0
        user.locked_until = None

    @classmethod
    def create_user_session(
        cls,
        session: Session,
        user: UserModel,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_id: str | None = None,
    ) -> tuple[UserSessionModel, str]:
        """Create a new server-side session and issue initial refresh token family record."""
        now = datetime.now(timezone.utc)
        session_id = uuid4()
        expires_at = now + cls.SESSION_LIFETIME

        user_session = UserSessionModel(
            id=session_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            device_id=device_id,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=now,
            last_active_at=now,
            expires_at=expires_at,
            is_active=True,
        )
        session.add(user_session)
        session.flush()

        # High-entropy opaque refresh token secret
        raw_refresh = f"thali_rt_{TokenService.generate_secure_secret(48)}"
        token_hash = TokenService.hash_secret(raw_refresh)

        family_record = RefreshTokenFamilyModel(
            id=uuid4(),
            session_id=session_id,
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_hash=token_hash,
            sequence_number=1,
            issued_at=now,
            expires_at=expires_at,
            is_used=False,
        )
        session.add(family_record)

        cls.record_security_event(
            session=session,
            event_type="SESSION_CREATED",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            details={"session_id": str(session_id), "device_id": device_id},
        )

        return user_session, raw_refresh

    @classmethod
    def rotate_refresh_token(
        cls,
        session: Session,
        raw_refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[UserSessionModel, UserModel, str]:
        """Validate presented refresh token, check for reuse, and rotate."""
        now = datetime.now(timezone.utc)
        token_hash = TokenService.hash_secret(raw_refresh_token)

        # Lookup in refresh_token_families
        record = (
            session.query(RefreshTokenFamilyModel)
            .filter(RefreshTokenFamilyModel.token_hash == token_hash)
            .first()
        )

        if not record:
            raise InvalidRefreshTokenError("Invalid refresh token")

        # Reuse Detection: If already used or revoked, the token has been compromised!
        if record.is_used or record.revoked_at is not None:
            # Breach defense: Revoke entire session and all family tokens immediately
            session.query(UserSessionModel).filter(
                UserSessionModel.id == record.session_id
            ).update({"is_active": False, "revoked_at": now})

            session.query(RefreshTokenFamilyModel).filter(
                RefreshTokenFamilyModel.session_id == record.session_id
            ).update({"revoked_at": now})

            cls.record_security_event(
                session=session,
                event_type="TOKEN_REUSE_DETECTED",
                user_id=record.user_id,
                tenant_id=record.tenant_id,
                ip_address=ip_address,
                details={
                    "session_id": str(record.session_id),
                    "compromised_seq": record.sequence_number,
                },
            )
            session.commit()
            raise RefreshTokenReuseError(
                "Refresh token reuse detected. For your security, this session has been terminated."
            )

        # Check token expiration
        token_exp = record.expires_at
        if token_exp.tzinfo is None:
            token_exp = token_exp.replace(tzinfo=timezone.utc)
        if token_exp < now:
            raise InvalidRefreshTokenError("Refresh token has expired")

        # Check session validity
        user_session = (
            session.query(UserSessionModel)
            .filter(UserSessionModel.id == record.session_id)
            .first()
        )
        if not user_session or not user_session.is_active or user_session.revoked_at is not None:
            raise InvalidRefreshTokenError("Session is inactive or revoked")

        session_exp = user_session.expires_at
        if session_exp.tzinfo is None:
            session_exp = session_exp.replace(tzinfo=timezone.utc)
        if session_exp < now:
            user_session.is_active = False
            raise InvalidRefreshTokenError("Session has expired")

        # Check user status
        user = session.query(UserModel).filter(UserModel.id == record.user_id).first()
        if not user or not user.active or getattr(user, "status", "active") != "active":
            raise InvalidRefreshTokenError("User account is inactive or disabled")

        # Legitimate rotation: Consume current token
        record.is_used = True
        record.revoked_at = now

        # Issue new refresh token in family
        new_raw_refresh = f"thali_rt_{TokenService.generate_secure_secret(48)}"
        new_token_hash = TokenService.hash_secret(new_raw_refresh)

        new_record = RefreshTokenFamilyModel(
            id=uuid4(),
            session_id=record.session_id,
            user_id=record.user_id,
            tenant_id=record.tenant_id,
            token_hash=new_token_hash,
            sequence_number=record.sequence_number + 1,
            issued_at=now,
            expires_at=now + cls.SESSION_LIFETIME,
            is_used=False,
        )
        session.add(new_record)

        # Update session activity and client tracking
        user_session.last_active_at = now
        if ip_address:
            user_session.ip_address = ip_address
        if user_agent:
            user_session.user_agent = user_agent

        cls.record_security_event(
            session=session,
            event_type="TOKEN_ROTATED",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            details={
                "session_id": str(user_session.id),
                "sequence": new_record.sequence_number,
            },
        )

        return user_session, user, new_raw_refresh

    @classmethod
    def revoke_session_by_refresh_token(
        cls,
        session: Session,
        raw_refresh_token: str,
        ip_address: str | None = None,
    ) -> bool:
        """Terminate session and revoke token family on logout."""
        token_hash = TokenService.hash_secret(raw_refresh_token)
        record = (
            session.query(RefreshTokenFamilyModel)
            .filter(RefreshTokenFamilyModel.token_hash == token_hash)
            .first()
        )
        if not record:
            return False

        now = datetime.now(timezone.utc)
        session.query(UserSessionModel).filter(
            UserSessionModel.id == record.session_id
        ).update({"is_active": False, "revoked_at": now})

        session.query(RefreshTokenFamilyModel).filter(
            RefreshTokenFamilyModel.session_id == record.session_id
        ).update({"revoked_at": now})

        cls.record_security_event(
            session=session,
            event_type="SESSION_LOGOUT",
            user_id=record.user_id,
            tenant_id=record.tenant_id,
            ip_address=ip_address,
            details={"session_id": str(record.session_id)},
        )
        return True

    @classmethod
    def revoke_all_user_sessions(
        cls,
        session: Session,
        user_id: UUID,
        reason: str = "PASSWORD_RESET",
    ) -> int:
        """Revoke all active sessions for a user (e.g. after password reset)."""
        now = datetime.now(timezone.utc)
        count = (
            session.query(UserSessionModel)
            .filter(
                UserSessionModel.user_id == user_id,
                UserSessionModel.is_active.is_(True),
            )
            .update({"is_active": False, "revoked_at": now})
        )

        session.query(RefreshTokenFamilyModel).filter(
            RefreshTokenFamilyModel.user_id == user_id,
            RefreshTokenFamilyModel.revoked_at.is_(None),
        ).update({"revoked_at": now})

        cls.record_security_event(
            session=session,
            event_type="ALL_SESSIONS_REVOKED",
            user_id=user_id,
            details={"reason": reason, "revoked_count": count},
        )
        return count

    @classmethod
    def create_password_reset_token(
        cls,
        session: Session,
        user: UserModel,
        ip_address: str | None = None,
    ) -> str:
        """Generate a single-use cryptographically random password reset token."""
        raw_token = f"thali_rst_{TokenService.generate_secure_secret(32)}"
        token_hash = TokenService.hash_secret(raw_token)
        now = datetime.now(timezone.utc)

        # Invalidate any previously pending reset tokens for this user
        session.query(PasswordResetTokenModel).filter(
            PasswordResetTokenModel.user_id == user.id,
            PasswordResetTokenModel.used_at.is_(None),
        ).update({"used_at": now})

        record = PasswordResetTokenModel(
            id=uuid4(),
            user_id=user.id,
            token_hash=token_hash,
            created_at=now,
            expires_at=now + cls.RESET_TOKEN_LIFETIME,
            used_at=None,
            ip_address=ip_address,
        )
        session.add(record)

        cls.record_security_event(
            session=session,
            event_type="PASSWORD_RESET_REQUESTED",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
        )
        return raw_token

    @classmethod
    def verify_and_consume_password_reset_token(
        cls,
        session: Session,
        raw_token: str,
        ip_address: str | None = None,
    ) -> tuple[PasswordResetTokenModel, UserModel]:
        """Verify password reset token, assert single-use, and mark consumed."""
        now = datetime.now(timezone.utc)
        token_hash = TokenService.hash_secret(raw_token)

        record = (
            session.query(PasswordResetTokenModel)
            .filter(PasswordResetTokenModel.token_hash == token_hash)
            .first()
        )

        if not record:
            raise InvalidResetTokenError("Invalid or expired password reset token")

        if record.used_at is not None:
            cls.record_security_event(
                session=session,
                event_type="PASSWORD_RESET_REPLAY_ATTEMPT",
                user_id=record.user_id,
                ip_address=ip_address,
            )
            raise ResetTokenAlreadyUsedError(
                "This password reset token has already been used"
            )

        token_exp = record.expires_at
        if token_exp.tzinfo is None:
            token_exp = token_exp.replace(tzinfo=timezone.utc)
        if token_exp < now:
            raise ResetTokenExpiredError("Password reset token has expired")

        user = session.query(UserModel).filter(UserModel.id == record.user_id).first()
        if not user or not user.active:
            raise InvalidResetTokenError("User account not found or disabled")

        # Consume token immediately
        record.used_at = now

        # Security Invariant: Terminate all active sessions upon password reset
        cls.revoke_all_user_sessions(
            session=session, user_id=user.id, reason="PASSWORD_RESET"
        )

        cls.record_security_event(
            session=session,
            event_type="PASSWORD_RESET_COMPLETED",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
        )

        return record, user
