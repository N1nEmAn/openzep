import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from graphiti_core.edges import EntityEdge
from graphiti_core.errors import GroupsEdgesNotFoundError, GroupsNodesNotFoundError
from graphiti_core.llm_client.errors import RateLimitError
from graphiti_core.nodes import EntityNode, EpisodicNode
from graphiti_core.utils.bulk_utils import RawEpisode
import openai

from deps import get_graphiti, verify_api_key
from engine.data_ingestion import normalize_episode_body, normalize_episode_type
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
from ontology_registry import get_ontology, set_ontology as store_ontology

router = APIRouter(prefix="/api/v2", tags=["graph"], dependencies=[Depends(verify_api_key)])
logger = logging.getLogger(__name__)


# ── graph.add ─────────────────────────────────────────────────────────────────

@router.post("/graph")
async def graph_add(body: GraphAddRequest, request: Request):
    graphiti = get_graphiti(request)
    ref_time = body.created_at or datetime.now(timezone.utc)
    ontology = get_ontology(graph_id=body.graph_id, user_id=body.user_id)
    name = await add_single_episode(
        graphiti,
        graph_id=body.graph_id,
        data=body.data,
        ep_type=body.type,
        source_description=body.source_description,
        created_at=ref_time,
        entity_types=ontology.entity_types if ontology else None,
        edge_types=ontology.edge_types if ontology else None,
        edge_type_map=ontology.edge_type_map if ontology else None,
    )
    return {
        "uuid": name,
        "graph_id": body.graph_id,
        "content": body.data,
        "created_at": ref_time.isoformat(),
    }


# ── in-memory episode processing tracker ─────────────────────────────────────
# Maps fake episode uuid -> True (processed) / False (pending)
_episode_status: dict[str, bool] = {}
_processing_sem: asyncio.Semaphore | None = None
_MAX_CONCURRENT_BATCHES = 2
_MAX_BULK_RETRIES = 2
_MAX_SINGLE_RETRIES = 2
_BULK_TIMEOUT_SECONDS = 45
_SINGLE_TIMEOUT_SECONDS = 30


def _get_processing_sem() -> asyncio.Semaphore:
    global _processing_sem
    if _processing_sem is None:
        _processing_sem = asyncio.Semaphore(_MAX_CONCURRENT_BATCHES)
    return _processing_sem


def _build_bulk_kwargs(body: GraphAddBatchRequest, ontology):
    kwargs = {"group_id": body.graph_id}
    if ontology:
        kwargs.update(
            entity_types=ontology.entity_types,
            edge_types=ontology.edge_types,
            edge_type_map=ontology.edge_type_map,
        )
    return kwargs


def _is_retryable_bulk_error(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError | openai.RateLimitError):
        return True
    if isinstance(exc, openai.InternalServerError):
        message = str(exc).lower()
        return "429" in message or "rate limit" in message

    message = str(exc).lower()
    return "rate limit" in message or "429" in message or "too many requests" in message


async def _add_raw_episode(
    graphiti,
    body: GraphAddBatchRequest,
    raw_episode: RawEpisode,
    ontology,
):
    await graphiti.add_episode(
        name=raw_episode.name,
        episode_body=raw_episode.content,
        source_description=raw_episode.source_description or "",
        reference_time=raw_episode.reference_time,
        source=raw_episode.source,
        **_build_bulk_kwargs(body, ontology),
    )


async def _add_episode_bulk_resilient(
    graphiti,
    body: GraphAddBatchRequest,
    raw_episodes: list[RawEpisode],
    ontology,
    *,
    attempt: int = 1,
) -> None:
    try:
        await asyncio.wait_for(
            graphiti.add_episode_bulk(raw_episodes, **_build_bulk_kwargs(body, ontology)),
            timeout=_BULK_TIMEOUT_SECONDS,
        )
        logger.info("add_episode_bulk done: %s (%s eps)", body.graph_id, len(raw_episodes))
        return
    except Exception as exc:
        retryable = _is_retryable_bulk_error(exc)
        timed_out = isinstance(exc, TimeoutError)
        if retryable and attempt < _MAX_BULK_RETRIES:
            delay = attempt * 2
            logger.warning(
                "add_episode_bulk retrying for %s (%s eps, attempt %s/%s) after %ss: %s",
                body.graph_id,
                len(raw_episodes),
                attempt + 1,
                _MAX_BULK_RETRIES,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
            await _add_episode_bulk_resilient(
                graphiti,
                body,
                raw_episodes,
                ontology,
                attempt=attempt + 1,
            )
            return

        if len(raw_episodes) > 1:
            midpoint = len(raw_episodes) // 2
            logger.warning(
                "add_episode_bulk splitting batch for %s after %s (%s eps -> %s + %s): %s",
                body.graph_id,
                "timeout" if timed_out else "failure",
                len(raw_episodes),
                midpoint,
                len(raw_episodes) - midpoint,
                exc,
            )
            await _add_episode_bulk_resilient(
                graphiti,
                body,
                raw_episodes[:midpoint],
                ontology,
            )
            await _add_episode_bulk_resilient(
                graphiti,
                body,
                raw_episodes[midpoint:],
                ontology,
            )
            return

        raw_episode = raw_episodes[0]
        for single_attempt in range(1, _MAX_SINGLE_RETRIES + 1):
            try:
                await asyncio.wait_for(
                    _add_raw_episode(graphiti, body, raw_episode, ontology),
                    timeout=_SINGLE_TIMEOUT_SECONDS,
                )
                logger.info("add_episode single fallback done: %s (%s)", body.graph_id, raw_episode.name)
                return
            except Exception as single_exc:
                if _is_retryable_bulk_error(single_exc) and single_attempt < _MAX_SINGLE_RETRIES:
                    delay = single_attempt * 2
                    logger.warning(
                        "single episode retrying for %s (%s, attempt %s/%s) after %ss: %s",
                        body.graph_id,
                        raw_episode.name,
                        single_attempt + 1,
                        _MAX_SINGLE_RETRIES,
                        delay,
                        single_exc,
                    )
                    await asyncio.sleep(delay)
                    continue

                logger.error(
                    "single episode fallback failed for %s (%s): %s",
                    body.graph_id,
                    raw_episode.name,
                    single_exc,
                    exc_info=True,
                )
                return


# ── graph.add_batch ───────────────────────────────────────────────────────────

@router.post("/graph-batch")
async def graph_add_batch(body: GraphAddBatchRequest, request: Request):
    import uuid as _uuid
    graphiti = get_graphiti(request)
    ontology = get_ontology(graph_id=body.graph_id, user_id=body.user_id)
    now = datetime.now(timezone.utc)

    # Generate fake uuids and mark them as pending
    ep_uuids = [str(_uuid.uuid4()) for _ in body.episodes]
    for uid in ep_uuids:
        _episode_status[uid] = False

    raw_episodes = [
        RawEpisode(
            name=ep.name or f"ep_{body.graph_id}_{i}",
            content=normalize_episode_body(ep.effective_content, ep.type),
            source_description=ep.source_description,
            source=normalize_episode_type(ep.type),
            reference_time=ep.created_at or ep.reference_time or now,
        )
        for i, ep in enumerate(body.episodes)
    ]

    async def _process():
        async with _get_processing_sem():
            try:
                await _add_episode_bulk_resilient(graphiti, body, raw_episodes, ontology)
            except Exception as exc:
                logger.error("add_episode_bulk failed for %s: %s", body.graph_id, exc, exc_info=True)
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


# ── graph.set-ontology compat ────────────────────────────────────────────────

@router.post("/graph/set-ontology")
async def graph_set_ontology(body: EntityTypesRequest | None = None):
    if body is not None:
        store_ontology(
            graph_ids=body.graph_ids,
            user_ids=body.user_ids,
            entity_types=body.entity_types,
            edge_types=body.edge_types,
        )
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
    compiled = store_ontology(
        graph_ids=body.graph_ids,
        user_ids=body.user_ids,
        entity_types=body.entity_types,
        edge_types=body.edge_types,
    )
    return {
        "message": "ok",
        "graph_ids": body.graph_ids,
        "user_ids": body.user_ids,
        "entity_type_count": len(compiled.entity_types),
        "edge_type_count": len(compiled.edge_types),
    }
