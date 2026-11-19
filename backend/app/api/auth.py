"""REST authentication routes and FastAPI authentication dependencies."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.users import User
from app.schemas.auth import Credentials, TokenResponse, UserResponse
from app.services import auth_service
from app.session import get_db_session, get_sessionmaker

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise auth_service.InvalidCredentialsError()
    # Authentication uses its own session to preserve OrderService's transaction.
    async with get_sessionmaker()() as session:
        return await auth_service.get_user_from_token(credentials.credentials, session)


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    credentials: Credentials,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    return await auth_service.register_user(credentials, session)


@router.post("/login")
async def login(
    credentials: Credentials,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    key: Annotated[str, Depends(auth_service.get_signing_key)],
) -> TokenResponse:
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.ws_allowed_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed")
    token = await auth_service.login(credentials, session, key)
    user_id = int(auth_service.decode_token(token.access_token)["sub"])
    response.set_cookie(
        "refresh_token",
        auth_service.create_refresh_token(user_id, key),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/api/auth/refresh",
        max_age=settings.jwt_refresh_token_days * 86400,
    )
    set_access_cookie(response, token)
    return token


def set_access_cookie(response: Response, token: TokenResponse) -> None:
    response.set_cookie(
        "access_token",
        token.access_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
        path="/ws",
        max_age=token.expires_in,
    )


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    key: Annotated[str, Depends(auth_service.get_signing_key)],
) -> TokenResponse:
    if request.headers.get("origin") not in settings.ws_allowed_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed")
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise auth_service.InvalidCredentialsError()
    user = await auth_service.get_user_from_token(
        refresh_token, session, token_type="refresh"
    )
    token = auth_service.create_access_token(user.id, key)
    set_access_cookie(response, token)
    return token


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response) -> None:
    if request.headers.get("origin") not in settings.ws_allowed_origins:
        raise HTTPException(status_code=403, detail="Origin is not allowed")
    response.delete_cookie(
        "access_token",
        path="/ws",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    response.delete_cookie(
        "refresh_token",
        path="/api/auth/refresh",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
