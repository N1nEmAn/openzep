from datetime import datetime
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
    name: str
    content: str
    source_description: str = "batch"
    source: str = "message"
    reference_time: datetime | None = None
    uuid: str | None = None


class GraphAddBatchRequest(BaseModel):
    graph_id: str
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
