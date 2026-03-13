import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, status

from database import get_db
from deps import get_graphiti, verify_api_key
from models.session import SessionCreateRequest, SessionListResponse, SessionResponse

router = APIRouter(prefix="/api/v2/sessions", tags=["sessions"])


def _row_to_session(row: aiosqlite.Row) -> SessionResponse:
    return SessionResponse(
        uuid=row["session_id"],
        session_id=row["session_id"],
        user_id=row["user_id"],
        metadata=json.loads(row["metadata"] or "{}"),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


@router.post(
    "/search",
    dependencies=[Depends(verify_api_key)],
)
async def search_sessions(
    body: dict[str, Any],
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Search sessions by text query across the knowledge graph."""
    text = body.get("text", "")
    user_id = body.get("user_id")
    session_ids_filter = body.get("session_ids")
    limit = body.get("limit", 10)

    if session_ids_filter:
        placeholders = ",".join("?" * len(session_ids_filter))
        rows = await (await db.execute(
            f"SELECT session_id FROM sessions WHERE session_id IN ({placeholders})",
            session_ids_filter,
        )).fetchall()
    elif user_id:
        rows = await (await db.execute(
            "SELECT session_id FROM sessions WHERE user_id = ?", (user_id,)
        )).fetchall()
    else:
        rows = await (await db.execute("SELECT session_id FROM sessions")).fetchall()

    if not rows or not text:
        return {"results": []}

    graphiti = get_graphiti(request)
    group_ids = [r["session_id"] for r in rows]
    edges = await graphiti.search(query=text, group_ids=group_ids, num_results=limit)

    results = [
        {
            "session_id": e.group_id if hasattr(e, "group_id") else None,
            "fact_uuid": e.uuid,
            "fact": e.fact,
        }
        for e in edges
    ]
    return {"results": results}


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def create_session(
    body: SessionCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    session_id = body.session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(
            "INSERT INTO sessions (session_id, user_id, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, body.user_id, json.dumps(body.metadata), now, now),
        )
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Session '{session_id}' already exists")
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    return _row_to_session(row)


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_session(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return _row_to_session(row)


@router.get(
    "",
    response_model=SessionListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_sessions(
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: aiosqlite.Connection = Depends(get_db),
):
    if user_id:
        rows = await (await db.execute(
            "SELECT * FROM sessions WHERE user_id = ? LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )).fetchall()
        count_row = await (await db.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
        )).fetchone()
    else:
        rows = await (await db.execute(
            "SELECT * FROM sessions LIMIT ? OFFSET ?", (limit, offset)
        )).fetchall()
        count_row = await (await db.execute("SELECT COUNT(*) FROM sessions")).fetchone()
    total = count_row[0] if count_row else 0
    sessions = [_row_to_session(r) for r in rows]
    return SessionListResponse(sessions=sessions, total_count=total, row_count=len(sessions))


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    dependencies=[Depends(verify_api_key)],
)
async def update_session(
    session_id: str,
    body: dict,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    now = datetime.now(timezone.utc).isoformat()
    new_metadata = json.dumps(body.get("metadata", json.loads(row["metadata"] or "{}")))
    await db.execute(
        "UPDATE sessions SET metadata = ?, updated_at = ? WHERE session_id = ?",
        (new_metadata, now, session_id),
    )
    await db.commit()
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    return _row_to_session(row)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def delete_session(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    await db.commit()
    return {"message": "Session deleted"}
