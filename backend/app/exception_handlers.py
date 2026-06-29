import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.engine.matching_engine import SymbolMismatchError
from app.services.order_service import (
    OrderNotCancellableException,
    OrderNotFoundException,
    OrderSyncError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(OrderNotFoundException)
    async def order_not_found_handler(
        _request: Request,
        _exc: OrderNotFoundException,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Order not found"})

    @app.exception_handler(OrderNotCancellableException)
    async def order_not_cancellable_handler(
        _request: Request,
        _exc: OrderNotCancellableException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": "Order cannot be cancelled"},
        )

    @app.exception_handler(SymbolMismatchError)
    async def symbol_mismatch_handler(
        _request: Request,
        _exc: SymbolMismatchError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": "Order symbol does not match engine symbol"},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        _request: Request,
        exc: IntegrityError,
    ) -> JSONResponse:
        logger.exception("Database integrity error", exc_info=exc)
        return JSONResponse(
            status_code=400,
            content={"detail": "Request violates database constraints"},
        )

    @app.exception_handler(OrderSyncError)
    async def order_sync_error_handler(
        _request: Request,
        _exc: OrderSyncError,
    ) -> JSONResponse:
        logger.exception("Order sync error")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal order processing error"},
        )
