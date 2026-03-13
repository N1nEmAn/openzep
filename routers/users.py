import json
import uuid
from datetime import datetime, timezone

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from deps import verify_api_key
from models.user import UserCreateRequest, UserListResponse, UserResponse, UserUpdateRequest

router = APIRouter(prefix="/api/v2/users", tags=["users"])


def _row_to_user(row: aiosqlite.Row) -> UserResponse:
    return UserResponse(
        uuid=row["user_id"],
        user_id=row["user_id"],
        email=row["email"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        metadata=json.loads(row["metadata"] or "{}"),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def create_user(
    body: UserCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(
            "INSERT INTO users (user_id, email, first_name, last_name, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (body.user_id, body.email, body.first_name, body.last_name, json.dumps(body.metadata), now, now),
        )
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=409, detail=f"User '{body.user_id}' already exists")
    row = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (body.user_id,))).fetchone()
    return _row_to_user(row)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_user(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_user(row)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(verify_api_key)],
)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    current = _row_to_user(row)
    new_email = body.email if body.email is not None else current.email
    new_first = body.first_name if body.first_name is not None else current.first_name
    new_last = body.last_name if body.last_name is not None else current.last_name
    new_meta = body.metadata if body.metadata is not None else current.metadata
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(
        "UPDATE users SET email=?, first_name=?, last_name=?, metadata=?, updated_at=? WHERE user_id=?",
        (new_email, new_first, new_last, json.dumps(new_meta), now, user_id),
    )
    await db.commit()
    row = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))).fetchone()
    return _row_to_user(row)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def delete_user(
    user_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    await db.commit()
    return {"message": "User deleted"}


@router.get(
    "/{user_id}/sessions",
    dependencies=[Depends(verify_api_key)],
)
async def get_user_sessions(
    user_id: str,
    limit: int = 100,
    offset: int = 0,
    db: aiosqlite.Connection = Depends(get_db),
):
    row = await (await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    rows = await (await db.execute(
        "SELECT * FROM sessions WHERE user_id = ? LIMIT ? OFFSET ?", (user_id, limit, offset)
    )).fetchall()
    import json
    from datetime import datetime
    sessions = []
    for r in rows:
        sessions.append({
            "uuid": r["session_id"],
            "session_id": r["session_id"],
            "user_id": r["user_id"],
            "metadata": json.loads(r["metadata"] or "{}"),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return {"sessions": sessions, "total_count": len(sessions), "row_count": len(sessions)}


@router.get(
    "",
    response_model=UserListResponse,
    dependencies=[Depends(verify_api_key)],
)
async def list_users(
    limit: int = 100,
    offset: int = 0,
    db: aiosqlite.Connection = Depends(get_db),
):
    rows = await (await db.execute(
        "SELECT * FROM users LIMIT ? OFFSET ?", (limit, offset)
    )).fetchall()
    count_row = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
    total = count_row[0] if count_row else 0
    users = [_row_to_user(r) for r in rows]
    return UserListResponse(users=users, total_count=total, row_count=len(users))
