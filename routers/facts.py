from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from deps import get_graphiti, verify_api_key
from engine.graphiti_engine import delete_fact_by_uuid, get_fact_by_uuid

router = APIRouter(prefix="/api/v2/facts", tags=["facts"])


class FactResponse(BaseModel):
    uuid: str
    fact: str
    created_at: str | None = None


@router.get(
    "/{fact_uuid}",
    response_model=FactResponse,
    dependencies=[Depends(verify_api_key)],
)
async def get_fact(fact_uuid: str, request: Request):
    graphiti = get_graphiti(request)
    fact = await get_fact_by_uuid(graphiti, fact_uuid)
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    return FactResponse(**fact)


@router.delete(
    "/{fact_uuid}",
    dependencies=[Depends(verify_api_key)],
)
async def delete_fact(fact_uuid: str, request: Request):
    graphiti = get_graphiti(request)
    deleted = await delete_fact_by_uuid(graphiti, fact_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"message": "Fact deleted"}
