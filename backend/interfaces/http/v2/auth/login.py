"""Custom auth endpoints: login, refresh, logout, register, signup, password reset.

Strictly supports exactly THREE human application roles:
1. PATIENT
2. CAREGIVER
3. DOCTOR

Enforces:
- Single-use Refresh Token Rotation with automatic reuse detection and family invalidation.
- Account Lockout after 5 failed login attempts.
- Server-side User Session tracking with device and IP binding.
- Cryptographically secure single-use Password Reset and Email Verification tokens.
- Role Escalation Defense: Clinician/Doctor accounts require verification.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.infrastructure.auth.password_service import hash_password, verify_password
from backend.infrastructure.auth.session_service import (
    AccountLockedError,
    InvalidRefreshTokenError,
    InvalidResetTokenError,
    RefreshTokenReuseError,
    ResetTokenAlreadyUsedError,
    ResetTokenExpiredError,
    SessionService,
)
from backend.infrastructure.auth.token_service import TokenService
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_token_service,
    get_unscoped_session,
)
from backend.interfaces.http.ops.rate_limit import TIERS, apply_rate_limit, get_rate_limiter
from backend.interfaces.http.v2.auth.schemas import (
    ApplicationRole,
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignupRequest,
    VerifyEmailRequest,
    VerifyEmailResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
)
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext
from backend.interfaces.http.v2.security.jwt import TokenVerificationError

auth_custom_router = APIRouter()

CLINICIAN_INVITE_CODES = {"CLINIC-VERIFIED-2026", "PLATE-DOCTOR-INVITE"}


def _get_client_ip(request: Request) -> str:
    """Extract client IP address for security logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@auth_custom_router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> LoginResponse:
    """Authenticate with email + password. Returns RS256 access + refresh tokens."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    email = body.email.lower().strip()
    from backend.infrastructure.persistence.models.user_models import UserModel, UserStatus
    from backend.infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository

    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_email(email)

    # Constant-time mitigation against user enumeration
    if not user:
        verify_password("dummy-password", "$2b$12$e8kU6KqJgX7K6GZlW7k6e.sYtK0a/jE3/3Z6KqJgX7K6GZlW7k6e.")
        SessionService.record_security_event(
            session=session,
            event_type="LOGIN_UNKNOWN_EMAIL",
            ip_address=ip_address,
            details={"email": email},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Account Lockout Check
    try:
        SessionService.check_lockout(user)
    except AccountLockedError as exc:
        session.commit()
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(exc)) from exc

    # Status & Activity Check
    if not user.active or getattr(user, "status", "active") in (UserStatus.DISABLED.value, UserStatus.SUSPENDED.value):
        SessionService.record_security_event(
            session=session,
            event_type="LOGIN_DISABLED_ACCOUNT",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled or suspended. Please contact clinic administration.",
        )

    # Credential Verification
    if not verify_password(body.password, user.hashed_password):
        SessionService.register_failed_attempt(session, user, ip_address=ip_address)
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Credential verification succeeded -> reset failed attempts
    SessionService.reset_failed_attempts(session, user)

    # Establish Server-Side User Session & Refresh Token Family
    user_session, raw_refresh = SessionService.create_user_session(
        session=session,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        device_id=body.device_id,
    )
    session.commit()

    from config.settings import Settings
    settings = Settings()
    expire_seconds = settings.auth.access_token_expire_minutes * 60

    access_token = token_service.issue_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        facility_id=str(user.facility_id) if user.facility_id else None,
        session_id=str(user_session.id),
    )

    user_name: str | None = None
    if user.role in ("doctor", "clinician"):
        from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
        clinician = session.query(CareTeamMemberModel).filter(CareTeamMemberModel.user_id == user.id).first()
        if clinician and clinician.display_name:
            user_name = clinician.display_name
    elif user.role == "patient":
        from backend.infrastructure.persistence.models.identity_models import IdentityPatientMappingModel
        from backend.infrastructure.persistence.models.patient_models import PatientModel
        mapping = session.query(IdentityPatientMappingModel).filter(IdentityPatientMappingModel.user_id == user.id).first()
        if mapping:
            pat = session.query(PatientModel).filter(PatientModel.id == mapping.patient_id).first()
            if pat and pat.name:
                user_name = pat.name

    return LoginResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=expire_seconds,
        user_status=getattr(user, "status", "active"),
        role=user.role,
        name=user_name,
        email=user.email,
    )


@auth_custom_router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    body: RefreshRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> RefreshResponse:
    """Exchange a valid refresh token for a new access token with single-use rotation."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    try:
        user_session, user, new_raw_refresh = SessionService.rotate_refresh_token(
            session=session,
            raw_refresh_token=body.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.commit()
    except RefreshTokenReuseError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except InvalidRefreshTokenError:
        # Fallback check: If presented token was an unpersisted RS256 token (legacy/test harness)
        try:
            claims = token_service.verify_refresh_token(body.refresh_token)
            user_repo = SqlAlchemyUserRepository(session)
            user = user_repo.get_by_id(UUID(claims["sub"]))
            if not user or not user.active:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
            user_session, new_raw_refresh = SessionService.create_user_session(
                session=session,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.commit()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            ) from exc

    from config.settings import Settings
    settings = Settings()
    expire_seconds = settings.auth.access_token_expire_minutes * 60

    access_token = token_service.issue_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        facility_id=str(user.facility_id) if user.facility_id else None,
        session_id=str(user_session.id),
    )

    return RefreshResponse(
        access_token=access_token,
        refresh_token=new_raw_refresh,
        expires_in=expire_seconds,
    )


@auth_custom_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    body: RefreshRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
) -> None:
    """Stateful logout — invalidates server-side session and revokes refresh token family."""
    ip_address = _get_client_ip(request)
    SessionService.revoke_session_by_refresh_token(
        session=session,
        raw_refresh_token=body.refresh_token,
        ip_address=ip_address,
    )
    session.commit()
    return None


@auth_custom_router.post("/signup", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: Request,
    response: Response,
    body: SignupRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> LoginResponse:
    """Self-service registration for mobile users (PATIENT, CAREGIVER, DOCTOR).

    Security Invariants:
    - PATIENT: Auto-provisions patient profile and active 1:1 identity mapping.
    - CAREGIVER: Account provisioned, but has NO patient data access until relationship authorized.
    - DOCTOR: Cannot self-elect into active clinical privileges. Requires valid clinic invite code
      or is placed in PENDING_VERIFICATION state.
    """
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)
    user_agent = request.headers.get("user-agent")

    email = body.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid email is required")
    if len(body.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
    from backend.infrastructure.persistence.models.identity_models import IdentityPatientMappingModel
    from backend.infrastructure.persistence.models.patient_models import PatientModel
    from backend.infrastructure.persistence.models.tenant_models import FacilityModel, OrganizationModel
    from backend.infrastructure.persistence.models.user_models import UserModel, UserStatus
    from backend.infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository

    user_repo = SqlAlchemyUserRepository(session)
    existing = user_repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Resolve tenant
    tenant_id: UUID | None = None
    if body.tenant_id:
        try:
            tenant_id = UUID(body.tenant_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid tenant_id format")
    else:
        org = session.query(OrganizationModel).filter(OrganizationModel.active.is_(True)).first()
        if org:
            tenant_id = org.id
        else:
            tenant_id = uuid4()
            org = OrganizationModel(id=tenant_id, name="Default Health System", slug="default-org", active=True)
            session.add(org)
            session.flush()

    # Resolve facility
    facility_id: UUID | None = None
    if body.facility_id:
        try:
            facility_id = UUID(body.facility_id)
        except ValueError:
            pass
    else:
        fac = (
            session.query(FacilityModel)
            .filter(FacilityModel.tenant_id == tenant_id, FacilityModel.active.is_(True))
            .first()
        )
        if fac:
            facility_id = fac.id

    # Canonicalize Role — strictly exactly three roles
    requested_role = body.role.lower().strip() if body.role else "patient"
    if requested_role not in ("patient", "caregiver", "doctor"):
        requested_role = "patient"

    # Role Escalation Defense: Doctor verification flow
    user_status = UserStatus.ACTIVE.value
    if requested_role == "doctor":
        if body.invite_code and body.invite_code.strip() in CLINICIAN_INVITE_CODES:
            user_status = UserStatus.ACTIVE.value
        else:
            # Mark doctor as pending verification — cannot execute unverified clinical operations
            user_status = UserStatus.PENDING_VERIFICATION.value

    user_id = uuid4()
    new_user = UserModel(
        id=user_id,
        email=email,
        hashed_password=hash_password(body.password),
        role=requested_role,
        tenant_id=tenant_id,
        facility_id=facility_id,
        phone=body.phone.strip() if body.phone else None,
        active=True,
        status=user_status,
        failed_login_attempts=0,
    )
    user_repo.add(new_user)
    session.flush()

    # Role-Specific Provisioning
    if requested_role == "patient":
        patient_id = uuid4()
        uh_id = f"UHID-{uuid4().hex[:8].upper()}"
        display_name = (body.name or email.split("@")[0].replace(".", " ").title()).strip()
        patient_record = PatientModel(
            id=patient_id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            uh_id=uh_id,
            name=display_name,
            # WhatsApp number is intentionally NOT stored or connected at
            # signup. A patient must explicitly complete the OTP verification
            # flow (POST /whatsapp/identity/request-verification + verify-code,
            # driven by the in-app connect popup) before their number is linked
            # to the patient record and routed to WhatsApp. Persisting it here
            # would silently connect the number and suppress that popup.
            phone=None,
            active=True,
        )
        session.add(patient_record)
        session.flush()

        mapping = IdentityPatientMappingModel(
            tenant_id=tenant_id,
            user_id=user_id,
            patient_id=patient_id,
            active=True,
        )
        session.add(mapping)

    elif requested_role == "doctor":
        # Register clinician record in facility
        display_name = (body.name or f"Dr. {email.split('@')[0].title()}").strip()
        clinician = CareTeamMemberModel(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            facility_id=facility_id,
            role="doctor",
            display_name=display_name,
            active=(user_status == UserStatus.ACTIVE.value),
        )
        session.add(clinician)

    # Establish Server-Side User Session & Refresh Token Family
    user_session, raw_refresh = SessionService.create_user_session(
        session=session,
        user=new_user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    session.commit()

    from config.settings import Settings
    settings = Settings()
    expire_seconds = settings.auth.access_token_expire_minutes * 60

    access_token = token_service.issue_access_token(
        user_id=str(new_user.id),
        tenant_id=str(new_user.tenant_id),
        role=new_user.role,
        facility_id=str(new_user.facility_id) if new_user.facility_id else None,
        session_id=str(user_session.id),
    )

    signup_name = display_name if "display_name" in locals() else (body.name or None)
    return LoginResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=expire_seconds,
        user_status=user_status,
        role=new_user.role,
        name=signup_name,
        email=new_user.email,
    )


@auth_custom_router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    request: Request,
    response: Response,
    body: ForgotPasswordRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ForgotPasswordResponse:
    """Generate a single-use password reset token for account recovery."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)

    email = body.email.lower().strip()
    from backend.infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository
    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_email(email)

    if not user or not user.active:
        return ForgotPasswordResponse(
            status="ok",
            message="If your email is registered with THALI, you will receive password recovery instructions.",
            reset_token=None,
        )

    raw_token = SessionService.create_password_reset_token(
        session=session,
        user=user,
        ip_address=ip_address,
    )
    session.commit()

    return ForgotPasswordResponse(
        status="ok",
        message="If your email is registered with THALI, you will receive password recovery instructions.",
        reset_token=raw_token,
    )


@auth_custom_router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: Request,
    response: Response,
    body: ResetPasswordRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ResetPasswordResponse:
    """Reset account password using a valid, single-use password reset token."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    try:
        record, user = SessionService.verify_and_consume_password_reset_token(
            session=session,
            raw_token=body.token,
            ip_address=ip_address,
        )
    except ResetTokenAlreadyUsedError as exc:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset token has already been used",
        ) from exc
    except (InvalidResetTokenError, ResetTokenExpiredError) as exc:
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from exc

    user.hashed_password = hash_password(body.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    session.commit()

    return ResetPasswordResponse(
        status="ok",
        message="Password has been successfully updated. You can now sign in with your new password.",
    )


@auth_custom_router.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordRequest,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    session: Annotated[Any, Depends(get_unscoped_session)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> ChangePasswordResponse:
    """Change account password for authenticated caller and revoke other sessions."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters",
        )

    from backend.infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository
    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_id(ctx.actor_id)
    if not user or not user.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(body.current_password, user.hashed_password):
        SessionService.record_security_event(
            session=session,
            event_type="PASSWORD_CHANGE_INVALID_CURRENT",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    user.hashed_password = hash_password(body.new_password)
    SessionService.revoke_all_user_sessions(session, user.id, reason="PASSWORD_CHANGE")
    session.commit()

    return ChangePasswordResponse(
        status="ok",
        message="Password has been successfully changed.",
    )


@auth_custom_router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    request: Request,
    body: VerifyEmailRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
) -> VerifyEmailResponse:
    """Verify email ownership using a single-use token."""
    ip_address = _get_client_ip(request)
    now = datetime.now(timezone.utc)
    token_hash = TokenService.hash_secret(body.token)

    from backend.infrastructure.persistence.models.user_models import (
        EmailVerificationTokenModel,
        UserModel,
        UserStatus,
    )
    record = session.query(EmailVerificationTokenModel).filter(
        EmailVerificationTokenModel.token_hash == token_hash
    ).first()

    if not record or record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")

    token_exp = record.expires_at
    if token_exp.tzinfo is None:
        token_exp = token_exp.replace(tzinfo=timezone.utc)
    if token_exp < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token has expired")

    user = session.query(UserModel).filter(UserModel.id == record.user_id).first()
    if user:
        user.status = UserStatus.ACTIVE.value
        record.used_at = now
        SessionService.record_security_event(
            session=session,
            event_type="EMAIL_VERIFIED",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
        )
        session.commit()

    return VerifyEmailResponse(status="ok", message="Email successfully verified.")


@auth_custom_router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    session: Annotated[Any, Depends(get_unscoped_session)],
) -> dict:
    """Register a new user account (Restricted administrative provisioning)."""
    if "admin" not in ctx.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required to register users")

    role = body.role.lower().strip()
    if role not in ("patient", "caregiver", "doctor", "admin"):
        role = "patient"

    from backend.infrastructure.persistence.models.user_models import UserModel, UserStatus
    from backend.infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository

    user_repo = SqlAlchemyUserRepository(session)
    existing = user_repo.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    new_user = UserModel(
        email=body.email.lower().strip(),
        hashed_password=hash_password(body.password),
        role=role,
        tenant_id=UUID(body.tenant_id),
        facility_id=UUID(body.facility_id) if body.facility_id else None,
        status=UserStatus.ACTIVE.value,
        active=True,
    )
    user_repo.add(new_user)
    session.commit()

    return {
        "user_id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role,
        "tenant_id": str(new_user.tenant_id),
    }


def _normalize_phone(p: str | None) -> str:
    if not p:
        return ""
    import re
    return re.sub(r"\D", "", p)


def _phones_match(p1: str | None, p2: str | None) -> bool:
    n1 = _normalize_phone(p1)
    n2 = _normalize_phone(p2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    if len(n1) >= 10 and len(n2) >= 10:
        return n1[-10:] == n2[-10:]
    return False


@auth_custom_router.delete("/account", response_model=DeleteAccountResponse)
@auth_custom_router.post("/delete-account", response_model=DeleteAccountResponse)
async def delete_account(
    request: Request,
    response: Response,
    body: DeleteAccountRequest,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    session: Annotated[Any, Depends(get_unscoped_session)],
    limiter: Annotated[object, Depends(get_rate_limiter)] = None,
) -> DeleteAccountResponse:
    """Permanently delete user account, associated patient observations/plans, and revoke all sessions."""
    apply_rate_limit(request=request, response=response, tier=TIERS["auth"], limiter=limiter)
    ip_address = _get_client_ip(request)

    from backend.infrastructure.persistence.models.clinician_models import CareTeamMemberModel
    from backend.infrastructure.persistence.models.identity_models import (
        CaregiverRelationshipModel,
        IdentityPatientMappingModel,
    )
    from backend.infrastructure.persistence.models.patient_models import PatientModel
    from backend.infrastructure.persistence.models.user_models import (
        EmailVerificationTokenModel,
        PasswordResetTokenModel,
        RefreshTokenFamilyModel,
        SecurityEventModel,
        UserModel,
        UserSessionModel,
    )
    from backend.infrastructure.persistence.repositories.user_repository import SqlAlchemyUserRepository

    user_repo = SqlAlchemyUserRepository(session)
    actor_uuid = UUID(str(ctx.actor_id)) if not isinstance(ctx.actor_id, UUID) else ctx.actor_id
    user = user_repo.get_by_id(actor_uuid)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")

    # Resolve registered phone
    registered_phone = user.phone
    patient_mappings = (
        session.query(IdentityPatientMappingModel)
        .filter(IdentityPatientMappingModel.user_id == user.id)
        .all()
    )
    patient_ids = [m.patient_id for m in patient_mappings]
    patient_records = (
        session.query(PatientModel).filter(PatientModel.id.in_(patient_ids)).all()
        if patient_ids
        else []
    )

    if not registered_phone and patient_records:
        for p in patient_records:
            if p.phone:
                registered_phone = p.phone
                break

    # If there is a registered phone on record, enforce exact verification
    if registered_phone:
        if not _phones_match(body.phone, registered_phone):
            SessionService.record_security_event(
                session=session,
                event_type="ACCOUNT_DELETION_PHONE_MISMATCH",
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                details={"entered_phone": body.phone},
            )
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The phone number entered does not match your registered phone number.",
            )
    else:
        # If no phone was stored in backend DB, require a plausible non-empty phone string
        if not body.phone or len(_normalize_phone(body.phone)) < 7:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A valid phone number is required to confirm account deletion.",
            )

    # 1. Cascade delete Patient records (cascades observations, care plans, meals, tasks, docs, whatsapp conversation)
    for p in patient_records:
        session.delete(p)

    # 2. Delete identity mappings
    session.query(IdentityPatientMappingModel).filter(
        IdentityPatientMappingModel.user_id == user.id
    ).delete(synchronize_session=False)

    # 3. Clean up caregiver relationships
    session.query(CaregiverRelationshipModel).filter(
        CaregiverRelationshipModel.caregiver_user_id == user.id
    ).delete(synchronize_session=False)

    # 4. Clean up clinician membership
    session.query(CareTeamMemberModel).filter(
        CareTeamMemberModel.user_id == user.id
    ).delete(synchronize_session=False)

    # 5. Revoke and purge all user sessions & security tokens
    session.query(RefreshTokenFamilyModel).filter(
        RefreshTokenFamilyModel.user_id == user.id
    ).delete(synchronize_session=False)
    session.query(UserSessionModel).filter(
        UserSessionModel.user_id == user.id
    ).delete(synchronize_session=False)
    session.query(PasswordResetTokenModel).filter(
        PasswordResetTokenModel.user_id == user.id
    ).delete(synchronize_session=False)
    session.query(EmailVerificationTokenModel).filter(
        EmailVerificationTokenModel.user_id == user.id
    ).delete(synchronize_session=False)

    # 6. Audit security event
    SessionService.record_security_event(
        session=session,
        event_type="ACCOUNT_DELETED",
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip_address=ip_address,
        details={"email": user.email, "role": user.role},
    )

    # 7. Delete user record
    session.delete(user)
    session.commit()

    return DeleteAccountResponse(
        status="ok",
        message="Account and all associated health records have been permanently deleted.",
    )

