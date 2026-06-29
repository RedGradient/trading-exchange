from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine
from collections.abc import AsyncGenerator
from app.config import settings


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _get_db_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True)
    return _engine

async def _dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def _get_sessionmaker():
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=_get_db_engine(), expire_on_commit=False
        )
    return _sessionmaker

def _dispose_sessionmaker() -> None:
    global _sessionmaker
    _sessionmaker = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    sessionmaker = _get_sessionmaker()
    async with sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

async def close_db() -> None:
    await _dispose_engine()
    _dispose_sessionmaker()
