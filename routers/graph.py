from fastapi import APIRouter, Depends, Request

from deps import get_graphiti, verify_api_key
from models.graph import GraphSearchRequest, GraphSearchResponse, GraphSearchResult

router = APIRouter(prefix="/api/v2/graph", tags=["graph"])


@router.post(
    "/search",
    response_model=GraphSearchResponse,
    dependencies=[Depends(verify_api_key)],
)
async def graph_search(
    body: GraphSearchRequest,
    request: Request,
):
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
