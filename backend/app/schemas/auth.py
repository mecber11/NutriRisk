"""Authentication, user and RBAC schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import ORMModel


class RoleOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None = None


class UserOut(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: RoleOut
    is_active: bool
    organization: str | None = None
    position: str | None = None
    phone: str | None = None
    last_login_at: datetime | None = None
    must_change_password: bool = False
    created_at: datetime | None = None


class UserWithPermissions(UserOut):
    permissions: dict[str, list[str]] = Field(default_factory=dict)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserWithPermissions


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    reset_token: str | None = None
    expires_in_minutes: int | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=160)
    organization: str | None = Field(default=None, max_length=160)
    position: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, max_length=40)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=8, max_length=128)
    role_code: str
    organization: str | None = None
    position: str | None = None
    phone: str | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=160)
    role_code: str | None = None
    is_active: bool | None = None
    organization: str | None = None
    position: str | None = None
    phone: str | None = None


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True


class PermissionMatrix(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    roles: list[RoleOut]
    modules: list[str]
    actions: list[str]
    matrix: dict[str, dict[str, list[str]]]
