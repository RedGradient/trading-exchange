import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.orders import router
from app.api.websocket import ws_router
from app.engine.registry import EngineRegistry
from app.exception_handlers import register_exception_handlers
from app.services.ws_manager import ws_fanout_loop
from app.session import close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.registry = EngineRegistry()
    task = asyncio.create_task(ws_fanout_loop())
    yield
    task.cancel()
    await close_db()


app = FastAPI(
    title="Trading Exchange API",
    description="REST API for placing orders, reading order state, and viewing the order book.",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
