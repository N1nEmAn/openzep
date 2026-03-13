from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    user_id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    metadata: dict[str, Any] = {}


class UserUpdateRequest(BaseModel):
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    metadata: dict[str, Any] | None = None


class UserResponse(BaseModel):
    uuid: str
    user_id: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total_count: int
    row_count: int
