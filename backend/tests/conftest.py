from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import httpx
import pytest
import pytest_asyncio
from app.api.orders import get_order_service
from app.config import settings
from app.engine.registry import EngineRegistry
from app.main import app
from app.models.base import Base
from app.services.order_service import OrderService
from app.session import get_db_session
from helpers import empty_engine
from helpers import filled_engine as build_filled_engine
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
def engine():
    return empty_engine()


@pytest.fixture
def filled_engine():
    return build_filled_engine(
        asks=[
            ("101", "5"),
            ("102", "8"),
            ("103", "12"),
            ("104", "6"),
            ("105", "15"),
        ],
        bids=[
            ("99", "4"),
            ("98", "10"),
            ("97", "7"),
            ("96", "20"),
            ("95", "3"),
        ],
    )


@pytest_asyncio.fixture
async def db_sessionmaker() -> AsyncGenerator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    yield sessionmaker
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession]:
    async with db_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def rest_client(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "jwt_secret_key", SecretStr("test-signing-key-" * 4))
    monkeypatch.setattr(settings, "jwt_access_token_minutes", 15)
    monkeypatch.setattr(settings, "ws_allowed_origins", ["http://localhost:8000"])
    monkeypatch.setattr("app.api.auth.get_sessionmaker", lambda: db_sessionmaker)

    async def override_session() -> AsyncGenerator[AsyncSession]:
        async with db_sessionmaker() as session:
            yield session

    def override_order_service() -> OrderService:
        return OrderService(sqs=MagicMock(), sns=MagicMock())

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_order_service] = override_order_service
    app.state.registry = EngineRegistry()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
