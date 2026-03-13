from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EntityNode, EpisodicNode
from graphiti_core.utils.bulk_utils import RawEpisode
from graphiti_core.utils.maintenance.graph_data_operations import EpisodeType

from deps import get_graphiti, verify_api_key
from models.graph import (
    EdgeListResponse,
    EdgeResponse,
    GraphAddBatchRequest,
    GraphAddBatchResponse,
    GraphSearchRequest,
    GraphSearchResponse,
    GraphSearchResult,
    GraphStatisticsResponse,
    NodeListResponse,
    NodeResponse,
)

router = APIRouter(prefix="/api/v2/graph", tags=["graph"], dependencies=[Depends(verify_api_key)])


@router.post("/search", response_model=GraphSearchResponse)
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


@router.get("/node", response_model=NodeListResponse)
async def get_nodes_by_graph_id(
    request: Request,
    graph_id: str = Query(...),
    limit: int = Query(100),
    uuid_cursor: str | None = Query(None),
):
    graphiti = get_graphiti(request)
    nodes = await EntityNode.get_by_group_ids(
        graphiti.driver,
        group_ids=[graph_id],
        limit=limit,
        uuid_cursor=uuid_cursor,
    )
    return NodeListResponse(
        nodes=[
            NodeResponse(
                uuid=n.uuid,
                name=n.name,
                group_id=n.group_id,
                summary=n.summary or "",
                labels=list(getattr(n, "labels", [])),
                attributes=n.attributes or {},
                created_at=getattr(n, "created_at", None),
            )
            for n in nodes
        ],
        total_count=len(nodes),
    )


@router.get("/node/{uuid}", response_model=NodeResponse)
async def get_node_by_uuid(uuid: str, request: Request):
    graphiti = get_graphiti(request)
    node = await EntityNode.get_by_uuid(graphiti.driver, uuid=uuid)
    return NodeResponse(
        uuid=node.uuid,
        name=node.name,
        group_id=node.group_id,
        summary=node.summary or "",
        labels=list(getattr(node, "labels", [])),
        attributes=node.attributes or {},
        created_at=getattr(node, "created_at", None),
    )


@router.get("/edge", response_model=EdgeListResponse)
async def get_edges_by_graph_id(
    request: Request,
    graph_id: str = Query(...),
    limit: int = Query(100),
    uuid_cursor: str | None = Query(None),
):
    graphiti = get_graphiti(request)
    edges = await EntityEdge.get_by_group_ids(
        graphiti.driver,
        group_ids=[graph_id],
        limit=limit,
        uuid_cursor=uuid_cursor,
    )
    return EdgeListResponse(
        edges=[
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
        ],
        total_count=len(edges),
    )


@router.post("/episodes/batch", response_model=GraphAddBatchResponse)
async def add_episode_batch(body: GraphAddBatchRequest, request: Request):
    graphiti = get_graphiti(request)

    raw_episodes = [
        RawEpisode(
            name=ep.name,
            uuid=ep.uuid,
            content=ep.content,
            source_description=ep.source_description,
            source=EpisodeType(ep.source),
            reference_time=ep.reference_time or datetime.now(timezone.utc),
        )
        for ep in body.episodes
    ]

    await graphiti.add_episode_bulk(raw_episodes, group_id=body.graph_id)

    return GraphAddBatchResponse(added=len(raw_episodes), graph_id=body.graph_id)


@router.get("/{graph_id}/statistics", response_model=GraphStatisticsResponse)
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


@router.delete("/{graph_id}")
async def delete_graph(graph_id: str, request: Request):
    graphiti = get_graphiti(request)
    driver = graphiti.driver

    episodes = await EpisodicNode.get_by_group_ids(driver, group_ids=[graph_id])
    for ep in episodes:
        await graphiti.remove_episode(ep.uuid)

    return {"deleted": True, "graph_id": graph_id, "episodes_removed": len(episodes)}
