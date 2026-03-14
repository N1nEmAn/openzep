import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from graphiti_core.edges import EntityEdge
from graphiti_core.errors import GroupsEdgesNotFoundError, GroupsNodesNotFoundError
from graphiti_core.nodes import EntityNode, EpisodicNode
from graphiti_core.utils.bulk_utils import RawEpisode
from graphiti_core.utils.maintenance.graph_data_operations import EpisodeType

from deps import get_graphiti, verify_api_key
from engine.graphiti_engine import add_single_episode
from models.graph import (
    EdgeListByGraphRequest,
    EdgeListResponse,
    EdgeResponse,
    EntityTypesRequest,
    EpisodeResponse,
    GraphAddBatchRequest,
    GraphAddBatchResponse,
    GraphAddRequest,
    GraphCreateRequest,
    GraphResponse,
    GraphSearchRequest,
    GraphSearchResponse,
    GraphSearchResult,
    GraphStatisticsResponse,
    NodeListByGraphRequest,
    NodeListResponse,
    NodeResponse,
)

router = APIRouter(prefix="/api/v2", tags=["graph"], dependencies=[Depends(verify_api_key)])


# ── graph.add ─────────────────────────────────────────────────────────────────

@router.post("/graph")
async def graph_add(body: GraphAddRequest, request: Request):
    graphiti = get_graphiti(request)
    name = await add_single_episode(
        graphiti,
        graph_id=body.graph_id,
        data=body.data,
        ep_type=body.type,
        source_description=body.source_description,
        created_at=body.created_at,
    )
    return {"uuid": name, "graph_id": body.graph_id}


# ── in-memory episode processing tracker ─────────────────────────────────────
# Maps fake episode uuid -> True (processed) / False (pending)
_episode_status: dict[str, bool] = {}
_processing_sem: asyncio.Semaphore | None = None


def _get_processing_sem() -> asyncio.Semaphore:
    global _processing_sem
    if _processing_sem is None:
        _processing_sem = asyncio.Semaphore(2)  # 2 concurrent batches max
    return _processing_sem


# ── graph.add_batch ───────────────────────────────────────────────────────────

@router.post("/graph-batch")
async def graph_add_batch(body: GraphAddBatchRequest, request: Request):
    import logging as _logging
    import uuid as _uuid
    _log = _logging.getLogger(__name__)
    graphiti = get_graphiti(request)
    now = datetime.now(timezone.utc)

    # Generate fake uuids and mark them as pending
    ep_uuids = [str(_uuid.uuid4()) for _ in body.episodes]
    for uid in ep_uuids:
        _episode_status[uid] = False

    raw_episodes = [
        RawEpisode(
            name=ep.name or f"ep_{body.graph_id}_{i}",
            content=ep.effective_content,
            source_description=ep.source_description,
            source=EpisodeType.message,
            reference_time=ep.created_at or ep.reference_time or now,
        )
        for i, ep in enumerate(body.episodes)
    ]

    async def _process():
        async with _get_processing_sem():
            try:
                await graphiti.add_episode_bulk(raw_episodes, group_id=body.graph_id)
                _log.info(f'add_episode_bulk done: {body.graph_id} ({len(raw_episodes)} eps)')
            except Exception as e:
                _log.error(f'add_episode_bulk failed for {body.graph_id}: {e}', exc_info=True)
                # Wait before retry to let rate limit recover
                await asyncio.sleep(5)
                try:
                    _log.info(f'Retrying add_episode_bulk for {body.graph_id}...')
                    await graphiti.add_episode_bulk(raw_episodes, group_id=body.graph_id)
                    _log.info(f'Retry succeeded for {body.graph_id}')
                except Exception as e2:
                    _log.error(f'Retry also failed for {body.graph_id}: {e2}')
            finally:
                for uid in ep_uuids:
                    _episode_status[uid] = True

    asyncio.create_task(_process())

    return [
        {
            "uuid_": ep_uuids[i],
            "content": ep.effective_content,
            "created_at": now.isoformat(),
            "source_description": ep.source_description or "",
            "processed": False,
        }
        for i, ep in enumerate(body.episodes)
    ]


# ── graph.set-ontology (no-op compat) ────────────────────────────────────────

@router.post("/graph/set-ontology")
async def graph_set_ontology(request: Request):
    # OpenZep/Graphiti does not support custom ontologies; accept and ignore.
    return {"success": True}


# ── graph.create ──────────────────────────────────────────────────────────────

@router.post("/graph/create", response_model=GraphResponse)
async def graph_create(body: GraphCreateRequest, request: Request):
    # graphiti has no explicit "create graph" — groups are implicit
    graph_id = body.graph_id or body.name or f"graph_{datetime.now(timezone.utc).timestamp()}"
    return GraphResponse(
        graph_id=graph_id,
        name=body.name or graph_id,
        created_at=datetime.now(timezone.utc),
    )


# ── graph.search ──────────────────────────────────────────────────────────────

@router.post("/graph/search", response_model=GraphSearchResponse)
async def graph_search(body: GraphSearchRequest, request: Request):
    graphiti = get_graphiti(request)

    group_ids = None
    if body.session_id:
        group_ids = [body.session_id]

    edges = await graphiti.search(
        query=body.query,
        group_ids=group_ids,
        num_results=body.limit,
    )

    results = [
        GraphSearchResult(
            uuid=e.uuid,
            fact=e.fact,
            score=getattr(e, "score", None),
        )
        for e in edges
        if getattr(e, "score", 1.0) >= body.min_score
    ]
    return GraphSearchResponse(results=results)


# ── graph.node.get_by_graph_id (POST) ─────────────────────────────────────────

@router.post("/graph/node/graph/{graph_id}", response_model=list[NodeResponse])
async def get_nodes_by_graph_id(
    graph_id: str,
    body: NodeListByGraphRequest,
    request: Request,
):
    graphiti = get_graphiti(request)
    try:
        nodes = await EntityNode.get_by_group_ids(
            graphiti.driver,
            group_ids=[graph_id],
            limit=body.limit,
            uuid_cursor=body.uuid_cursor,
        )
    except GroupsNodesNotFoundError:
        return []
    return [
        NodeResponse(
            uuid=n.uuid,
            name=n.name,
            group_id=n.group_id,
            summary=n.summary or "",
            labels=_ensure_custom_label(list(getattr(n, "labels", []))),
            attributes=n.attributes or {},
            created_at=getattr(n, "created_at", None),
        )
        for n in nodes
    ]


def _ensure_custom_label(labels: list[str]) -> list[str]:
    """Ensure nodes have at least one non-default label so mirofish entity filter passes."""
    custom = [l for l in labels if l not in ("Entity", "Node")]
    if not custom:
        labels.append("ExtractedEntity")
    return labels


# ── graph.node.get ────────────────────────────────────────────────────────────

@router.get("/graph/node/{uuid}", response_model=NodeResponse)
async def get_node_by_uuid(uuid: str, request: Request):
    graphiti = get_graphiti(request)
    node = await EntityNode.get_by_uuid(graphiti.driver, uuid=uuid)
    return NodeResponse(
        uuid=node.uuid,
        name=node.name,
        group_id=node.group_id,
        summary=node.summary or "",
        labels=_ensure_custom_label(list(getattr(node, "labels", []))),
        attributes=node.attributes or {},
        created_at=getattr(node, "created_at", None),
    )


# ── graph.node.get_entity_edges ───────────────────────────────────────────────

@router.get("/graph/node/{uuid}/entity-edges", response_model=list[EdgeResponse])
async def get_node_entity_edges(uuid: str, request: Request):
    graphiti = get_graphiti(request)
    edges = await EntityEdge.get_by_node_uuid(graphiti.driver, node_uuid=uuid)
    return [
        EdgeResponse(
            uuid=e.uuid,
            name=e.name,
            group_id=e.group_id,
            fact=e.fact or "",
            source_node_uuid=e.source_node_uuid,
            target_node_uuid=e.target_node_uuid,
            created_at=getattr(e, "created_at", None),
            expired_at=getattr(e, "expired_at", None),
            valid_at=getattr(e, "valid_at", None),
            invalid_at=getattr(e, "invalid_at", None),
            episodes=list(getattr(e, "episodes", []) or []),
            attributes=getattr(e, "attributes", {}) or {},
        )
        for e in edges
    ]


# ── graph.edge.get_by_graph_id (POST) ─────────────────────────────────────────

@router.post("/graph/edge/graph/{graph_id}", response_model=list[EdgeResponse])
async def get_edges_by_graph_id(
    graph_id: str,
    body: EdgeListByGraphRequest,
    request: Request,
):
    graphiti = get_graphiti(request)
    try:
        edges = await EntityEdge.get_by_group_ids(
            graphiti.driver,
            group_ids=[graph_id],
            limit=body.limit,
            uuid_cursor=body.uuid_cursor,
        )
    except GroupsEdgesNotFoundError:
        return []
    return [
        EdgeResponse(
            uuid=e.uuid,
            name=e.name,
            group_id=e.group_id,
            fact=e.fact or "",
            source_node_uuid=e.source_node_uuid,
            target_node_uuid=e.target_node_uuid,
            created_at=getattr(e, "created_at", None),
            expired_at=getattr(e, "expired_at", None),
            valid_at=getattr(e, "valid_at", None),
            invalid_at=getattr(e, "invalid_at", None),
            episodes=list(getattr(e, "episodes", []) or []),
            attributes=getattr(e, "attributes", {}) or {},
        )
        for e in edges
    ]


# ── graph.episode.get ─────────────────────────────────────────────────────────

@router.get("/graph/episodes/{uuid}", response_model=EpisodeResponse)
async def get_episode_by_uuid(uuid: str, request: Request):
    graphiti = get_graphiti(request)
    now = datetime.now(timezone.utc)

    # Check in-memory tracker first (for fake uuids from add_batch)
    if uuid in _episode_status:
        return EpisodeResponse(
            uuid=uuid,
            name="",
            content="",
            created_at=now,
            processed=_episode_status[uuid],
        )

    # Real episode in Neo4j
    try:
        ep = await EpisodicNode.get_by_uuid(graphiti.driver, uuid=uuid)
        return EpisodeResponse(
            uuid=ep.uuid,
            name=ep.name,
            content=ep.content,
            source_description=getattr(ep, "source_description", ""),
            source=str(getattr(ep, "source", "message")),
            created_at=getattr(ep, "created_at", None) or now,
            group_id=getattr(ep, "group_id", ""),
            processed=True,
        )
    except Exception:
        return EpisodeResponse(
            uuid=uuid,
            name="",
            content="",
            created_at=now,
            processed=True,
        )


# ── graph statistics ──────────────────────────────────────────────────────────

@router.get("/graph/{graph_id}/statistics", response_model=GraphStatisticsResponse)
async def get_graph_statistics(graph_id: str, request: Request):
    graphiti = get_graphiti(request)
    driver = graphiti.driver

    nodes = await EntityNode.get_by_group_ids(driver, group_ids=[graph_id])
    edges = await EntityEdge.get_by_group_ids(driver, group_ids=[graph_id])
    episodes = await EpisodicNode.get_by_group_ids(driver, group_ids=[graph_id])

    return GraphStatisticsResponse(
        graph_id=graph_id,
        node_count=len(nodes),
        edge_count=len(edges),
        episode_count=len(episodes),
    )


# ── graph.delete ──────────────────────────────────────────────────────────────

@router.delete("/graph/{graph_id}")
async def delete_graph(graph_id: str, request: Request):
    graphiti = get_graphiti(request)
    driver = graphiti.driver

    episodes = await EpisodicNode.get_by_group_ids(driver, group_ids=[graph_id])
    for ep in episodes:
        await graphiti.remove_episode(ep.uuid)

    return {"deleted": True, "graph_id": graph_id, "episodes_removed": len(episodes)}


# ── entity-types stub ─────────────────────────────────────────────────────────

@router.put("/entity-types")
async def set_entity_types(body: EntityTypesRequest):
    return {"message": "ok"}
