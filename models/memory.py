from typing import Any

from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str
    role_type: str | None = None
    metadata: dict[str, Any] = {}


class AddMemoryRequest(BaseModel):
    messages: list[Message]
    return_context: bool = False


class Fact(BaseModel):
    uuid: str
    fact: str
    created_at: str | None = None


class MemoryContext(BaseModel):
    facts: list[Fact] = []


class MemoryResponse(BaseModel):
    context: str = ""
    facts: list[Fact] = []
    messages: list[Message] = []


class AddMemoryResponse(BaseModel):
    ok: bool = True
