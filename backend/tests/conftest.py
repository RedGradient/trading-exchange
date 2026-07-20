from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.base import Base


from helpers import empty_engine, filled_engine as build_filled_engine


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
