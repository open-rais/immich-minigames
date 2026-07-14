"""Pydantic request/response DTOs for the auth endpoints (api/auth_api.py) - separate from
persistence.users.UserModel so the password hash never has a path to the HTTP response."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from persistence.users import UserModel


class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str
    created_at: datetime

    @classmethod
    def from_user(cls, user: UserModel) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            created_at=user.created_at,
        )
