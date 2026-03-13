from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from graphiti_core import Graphiti

bearerScheme = HTTPBearer(auto_error=False)


def get_graphiti(request: Request) -> Graphiti:
    return request.app.state.graphiti


def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(bearerScheme),
):
    if settings.api_key is None:
        return
    if credentials is None or credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
