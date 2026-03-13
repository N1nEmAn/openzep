from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from database import get_db
from deps import get_graphiti, verify_api_key
from engine.graphiti_engine import add_messages_to_graph, clear_session_graph, search_graph
from models.memory import AddMemoryRequest, AddMemoryResponse, Fact, MemoryResponse

router = APIRouter(prefix="/api/v2/sessions", tags=["memory"])


@router.post(
    "/{session_id}/memory",
    response_model=AddMemoryResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def add_memory(
    session_id: str,
    body: AddMemoryRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db=Depends(get_db),
):
    # Verify session exists
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    graphiti = get_graphiti(request)
    messages = [m.model_dump() for m in body.messages]
    background_tasks.add_task(add_messages_to_graph, graphiti, session_id, messages)
    return AddMemoryResponse(ok=True)


@router.get(
    "/{session_id}/memory",
    response_model=MemoryResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_memory(
    session_id: str,
    request: Request,
    lastn: int = 10,
    min_rating: float = 0.0,
    db=Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    graphiti = get_graphiti(request)
    edge_dicts = await search_graph(graphiti, session_id, query="", num_results=lastn)

    facts = [
        Fact(
            uuid=e["uuid"],
            fact=e["fact"],
            created_at=e.get("created_at"),
        )
        for e in edge_dicts
    ]
    # Format context as a numbered fact list for LLM consumption
    context = "\n".join(f"{i+1}. {f.fact}" for i, f in enumerate(facts))
    return MemoryResponse(context=context, facts=facts, messages=[])


@router.delete(
    "/{session_id}/memory",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def delete_memory(
    session_id: str,
    request: Request,
    db=Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    graphiti = get_graphiti(request)
    await clear_session_graph(graphiti, session_id)
    return {"message": "Memory deleted"}
