"""Pydantic schemas for the custom auth endpoints."""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class ApplicationRole(str, Enum):
    """Exactly the three authorized application roles."""

    PATIENT = "patient"
    CAREGIVER = "caregiver"
    DOCTOR = "doctor"


class LoginRequest(BaseModel):
    email: str
    password: str
    device_id: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_status: str | None = "active"
    role: str | None = None
    name: str | None = None
    email: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: str
    tenant_id: str
    facility_id: str | None = None


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str | None = None
    phone: str | None = None
    role: str = "patient"
    tenant_id: str | None = None
    facility_id: str | None = None
    invite_code: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    status: str = "ok"
    message: str
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    status: str = "ok"
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    status: str = "ok"
    message: str


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyEmailResponse(BaseModel):
    status: str = "ok"
    message: str


class DeleteAccountRequest(BaseModel):
    phone: str


class DeleteAccountResponse(BaseModel):
    status: str = "ok"
    message: str = "Account has been permanently deleted."
