from datetime import datetime
from typing import Any

from pydantic import BaseModel


class GraphAddRequest(BaseModel):
    data: str
    type: str = "text"
    graph_id: str
    source_description: str = "user"
    created_at: datetime | None = None
    user_id: str | None = None


class GraphCreateRequest(BaseModel):
    name: str | None = None
    graph_id: str | None = None


class GraphResponse(BaseModel):
    graph_id: str
    name: str
    created_at: datetime | None = None


class NodeListByGraphRequest(BaseModel):
    limit: int = 100
    uuid_cursor: str | None = None


class EdgeListByGraphRequest(BaseModel):
    limit: int = 100
    uuid_cursor: str | None = None


class EpisodeResponse(BaseModel):
    uuid: str
    name: str
    content: str
    source_description: str = ""
    source: str = "message"
    created_at: datetime | None = None
    group_id: str = ""
    processed: bool = True


class EntityTypesRequest(BaseModel):
    entity_types: list[Any] | None = None
    edge_types: list[Any] | None = None
    graph_ids: list[str] | None = None
    user_ids: list[str] | None = None


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


# ── Node models ───────────────────────────────────────────────────────────────

class NodeResponse(BaseModel):
    uuid: str
    name: str
    group_id: str
    summary: str = ""
    labels: list[str] = []
    attributes: dict[str, Any] = {}
    created_at: datetime | None = None


class NodeListResponse(BaseModel):
    nodes: list[NodeResponse] = []
    total_count: int = 0


# ── Edge models ───────────────────────────────────────────────────────────────

class EdgeResponse(BaseModel):
    uuid: str
    name: str
    group_id: str
    fact: str = ""
    source_node_uuid: str
    target_node_uuid: str
    created_at: datetime | None = None
    expired_at: datetime | None = None
    valid_at: datetime | None = None
    invalid_at: datetime | None = None
    episodes: list[str] = []
    attributes: dict[str, Any] = {}


class EdgeListResponse(BaseModel):
    edges: list[EdgeResponse] = []
    total_count: int = 0


# ── Batch episode add ─────────────────────────────────────────────────────────

class EpisodeBatchItem(BaseModel):
    data: str | None = None
    type: str = "text"
    source_description: str = "batch"
    created_at: datetime | None = None
    # legacy fields kept for backward compat
    name: str | None = None
    content: str | None = None
    source: str = "message"
    reference_time: datetime | None = None
    uuid: str | None = None

    @property
    def effective_content(self) -> str:
        return self.data or self.content or ""


class GraphAddBatchRequest(BaseModel):
    graph_id: str
    user_id: str | None = None
    episodes: list[EpisodeBatchItem]


class GraphAddBatchResponse(BaseModel):
    added: int
    graph_id: str


# ── Graph statistics ──────────────────────────────────────────────────────────

class GraphStatisticsResponse(BaseModel):
    graph_id: str
    node_count: int
    edge_count: int
    episode_count: int
