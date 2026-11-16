"""REST authentication routes and FastAPI authentication dependencies."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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
    session: Annotated[AsyncSession, Depends(get_db_session)],
    key: Annotated[str, Depends(auth_service.get_signing_key)],
) -> TokenResponse:
    return await auth_service.login(credentials, session, key)
