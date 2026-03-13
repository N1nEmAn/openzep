from typing import Any

from pydantic import BaseModel


class GraphSearchRequest(BaseModel):
    query: str
    user_id: str | None = None
    session_id: str | None = None
    limit: int = 10
    min_score: float = 0.0


class GraphSearchResult(BaseModel):
    uuid: str
    fact: str
    score: float | None = None
    metadata: dict[str, Any] = {}


class GraphSearchResponse(BaseModel):
    results: list[GraphSearchResult] = []
