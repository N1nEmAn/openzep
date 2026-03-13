from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    session_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] = {}


class SessionResponse(BaseModel):
    uuid: str
    session_id: str
    user_id: str | None = None
    metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total_count: int
    row_count: int
