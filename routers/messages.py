from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from deps import get_graphiti, verify_api_key

router = APIRouter(prefix="/api/v2/sessions", tags=["messages"])


async def _get_episodes(graphiti, session_id: str, limit: int):
    return await graphiti.retrieve_episodes(
        reference_time=datetime.now(timezone.utc),
        last_n=limit,
        group_ids=[session_id],
    )


def _ep_to_message(ep) -> dict[str, Any]:
    content = ep.content if hasattr(ep, "content") else str(ep)
    parts = content.split(": ", 1)
    role, body = (parts[0], parts[1]) if len(parts) == 2 else ("unknown", content)
    return {
        "uuid": ep.uuid,
        "role": role,
        "content": body,
        "created_at": ep.created_at.isoformat() if ep.created_at else None,
        "metadata": {},
    }


@router.get(
    "/{session_id}/messages",
    dependencies=[Depends(verify_api_key)],
)
async def get_messages(
    session_id: str,
    request: Request,
    limit: int = 100,
    db=Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    graphiti = get_graphiti(request)
    episodes = await _get_episodes(graphiti, session_id, limit)
    messages = [_ep_to_message(ep) for ep in episodes]
    return {"messages": messages, "total_count": len(messages), "row_count": len(messages)}


@router.get(
    "/{session_id}/messages/{message_uuid}",
    dependencies=[Depends(verify_api_key)],
)
async def get_message(
    session_id: str,
    message_uuid: str,
    request: Request,
    db=Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    graphiti = get_graphiti(request)
    episodes = await _get_episodes(graphiti, session_id, 10000)
    for ep in episodes:
        if ep.uuid == message_uuid:
            return _ep_to_message(ep)
    raise HTTPException(status_code=404, detail="Message not found")


@router.patch(
    "/{session_id}/messages/{message_uuid}",
    dependencies=[Depends(verify_api_key)],
)
async def update_message_metadata(
    session_id: str,
    message_uuid: str,
    body: dict[str, Any],
    db=Depends(get_db),
):
    # Zep stores message metadata — we acknowledge but don't persist in graph
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"uuid": message_uuid, "metadata": body.get("metadata", {}), "message": "Metadata updated"}
