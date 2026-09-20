"""Pydantic schemas for the custom auth endpoints."""
from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
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

