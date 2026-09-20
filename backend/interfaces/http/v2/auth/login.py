"""Custom auth endpoints: login, refresh, logout, register (Task 2).

Endpoints:
- POST /api/v2/auth/login   — {email, password} → bcrypt verify → issue access + refresh tokens
- POST /api/v2/auth/refresh — {refresh_token} → verify refresh JWT → issue new access token
- POST /api/v2/auth/logout  — stateless / revoke refresh token
- POST /api/v2/auth/register — creates new user (admin-only)
"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.infrastructure.auth.password_service import hash_password, verify_password
from backend.infrastructure.auth.token_service import TokenService
from backend.interfaces.http.dependencies import (
    get_authenticated_context,
    get_token_service,
    get_unscoped_session,
)
from backend.interfaces.http.v2.auth.schemas import (
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
)
from backend.interfaces.http.v2.security.authorization import AuthenticatedContext
from backend.interfaces.http.v2.security.jwt import TokenVerificationError

auth_custom_router = APIRouter()


@auth_custom_router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> LoginResponse:
    """Authenticate with email + password. Returns RS256 access + refresh tokens."""
    from backend.infrastructure.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )

    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_email(body.email)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    from config.settings import Settings
    settings = Settings()
    expire_seconds = settings.auth.access_token_expire_minutes * 60

    access_token = token_service.issue_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        facility_id=str(user.facility_id) if user.facility_id else None,
    )
    refresh_token = token_service.issue_refresh_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expire_seconds,
    )


@auth_custom_router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    body: RefreshRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> RefreshResponse:
    """Exchange a valid refresh token for a new access token."""
    from backend.infrastructure.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )

    try:
        claims = token_service.verify_refresh_token(body.refresh_token)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_id(UUID(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    from config.settings import Settings
    settings = Settings()
    expire_seconds = settings.auth.access_token_expire_minutes * 60

    access_token = token_service.issue_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
        facility_id=str(user.facility_id) if user.facility_id else None,
    )
    return RefreshResponse(access_token=access_token, expires_in=expire_seconds)


@auth_custom_router.post("/logout", status_code=204)
async def logout(body: RefreshRequest) -> None:
    """Stateless logout — client discards tokens."""
    return None


@auth_custom_router.post("/register", status_code=201)
async def register(
    body: RegisterRequest,
    ctx: Annotated[AuthenticatedContext, Depends(get_authenticated_context)],
    session: Annotated[Any, Depends(get_unscoped_session)],
) -> dict:
    """Register a new user. Requires admin role."""
    from backend.infrastructure.persistence.models.user_models import UserModel
    from backend.infrastructure.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )

    if "admin" not in ctx.roles:
        raise HTTPException(status_code=403, detail="Admin role required to register users")

    user_repo = SqlAlchemyUserRepository(session)
    existing = user_repo.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = UserModel(
        email=body.email.lower().strip(),
        hashed_password=hash_password(body.password),
        role=body.role,
        tenant_id=UUID(body.tenant_id),
        facility_id=UUID(body.facility_id) if body.facility_id else None,
    )
    user_repo.add(new_user)
    session.commit()

    return {
        "user_id": str(new_user.id),
        "email": new_user.email,
        "role": new_user.role,
        "tenant_id": str(new_user.tenant_id),
    }


@auth_custom_router.post("/signup", response_model=LoginResponse, status_code=201)
async def signup(
    body: SignupRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> LoginResponse:
    """Self-service registration for patients / users. Issues JWT access + refresh tokens."""
    import uuid
    from backend.infrastructure.persistence.models.identity_models import IdentityPatientMappingModel
    from backend.infrastructure.persistence.models.patient_models import PatientModel
    from backend.infrastructure.persistence.models.tenant_models import FacilityModel, OrganizationModel
    from backend.infrastructure.persistence.models.user_models import UserModel
    from backend.infrastructure.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )

    email = body.email.lower().strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_repo = SqlAlchemyUserRepository(session)
    existing = user_repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Resolve tenant
    tenant_id: UUID | None = None
    if body.tenant_id:
        try:
            tenant_id = UUID(body.tenant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant_id format")
    else:
        org = session.query(OrganizationModel).filter(OrganizationModel.active.is_(True)).first()
        if org:
            tenant_id = org.id
        else:
            tenant_id = uuid.uuid4()
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
            .filter(
                FacilityModel.tenant_id == tenant_id,
                FacilityModel.active.is_(True),
            )
            .first()
        )
        if fac:
            facility_id = fac.id

    role = body.role.lower().strip() if body.role else "patient"
    if role not in ("patient", "caregiver", "doctor", "nurse", "coordinator", "dietitian"):
        role = "patient"

    user_id = uuid.uuid4()
    new_user = UserModel(
        id=user_id,
        email=email,
        hashed_password=hash_password(body.password),
        role=role,
        tenant_id=tenant_id,
        facility_id=facility_id,
        active=True,
    )
    user_repo.add(new_user)
    session.flush()

    # If registering a patient, also provision patient profile and identity mapping
    if role == "patient":
        patient_id = uuid.uuid4()
        uh_id = f"UHID-{uuid.uuid4().hex[:8].upper()}"
        display_name = (body.name or email.split("@")[0].replace(".", " ").title()).strip()
        patient_record = PatientModel(
            id=patient_id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            uh_id=uh_id,
            name=display_name,
            phone=body.phone.strip() if body.phone else None,
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

    session.commit()

    from config.settings import Settings
    settings = Settings()
    expire_seconds = settings.auth.access_token_expire_minutes * 60

    access_token = token_service.issue_access_token(
        user_id=str(new_user.id),
        tenant_id=str(new_user.tenant_id),
        role=new_user.role,
        facility_id=str(new_user.facility_id) if new_user.facility_id else None,
    )
    refresh_token = token_service.issue_refresh_token(
        user_id=str(new_user.id),
        tenant_id=str(new_user.tenant_id),
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expire_seconds,
    )


@auth_custom_router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> ForgotPasswordResponse:
    """Generate a password reset token for account recovery."""
    from datetime import datetime, timedelta, timezone
    import uuid
    import jwt as pyjwt
    from backend.infrastructure.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )

    email = body.email.lower().strip()
    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_email(email)

    if not user or not user.active:
        return ForgotPasswordResponse(
            status="ok",
            message="If your email is registered with THALI, you will receive password recovery instructions.",
            reset_token=None,
        )

    # Issue a signed reset token (15-minute validity)
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "typ": "password_reset",
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": str(uuid.uuid4()),
    }
    reset_token = pyjwt.encode(payload, token_service._private_key, algorithm="RS256")

    return ForgotPasswordResponse(
        status="ok",
        message="If your email is registered with THALI, you will receive password recovery instructions.",
        reset_token=reset_token,
    )


@auth_custom_router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    body: ResetPasswordRequest,
    session: Annotated[Any, Depends(get_unscoped_session)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> ResetPasswordResponse:
    """Reset account password using a valid password reset token."""
    from backend.infrastructure.persistence.repositories.user_repository import (
        SqlAlchemyUserRepository,
    )

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    try:
        claims = token_service.verify_token(body.token)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token") from exc

    if claims.get("typ") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid token type for password reset")

    user_repo = SqlAlchemyUserRepository(session)
    user = user_repo.get_by_id(UUID(claims["sub"]))
    if not user or not user.active:
        raise HTTPException(status_code=404, detail="User account not found or deactivated")

    user.hashed_password = hash_password(body.new_password)
    session.commit()

    return ResetPasswordResponse(
        status="ok",
        message="Password has been successfully updated. You can now sign in with your new password.",
    )

