from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from graphiti_core import Graphiti

bearerScheme = HTTPBearer(auto_error=False)


def get_graphiti(request: Request) -> Graphiti:
    return request.app.state.graphiti


def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearerScheme),
):
    if settings.api_key is None:
        return
    # 支持 Bearer 和 Api-Key 两种格式
    token = None
    if credentials is not None:
        token = credentials.credentials
    else:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("api-key "):
            token = auth_header[8:]
    if token != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
