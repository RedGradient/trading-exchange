"""WebSocket endpoint for market data and order commands."""

import asyncio
import time
from contextlib import suppress

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from starlette.websockets import WebSocketState

from app.aws import get_aws_client
from app.config import settings
from app.services import auth_service
from app.schemas.orders import OrderCreate, OrderResponse
from app.schemas.websocket import WsError, WsMessage
from app.services import order_service
from app.services.order_service import OrderService
from app.services.ws_manager import ws_manager
from app.session import get_sessionmaker

logger = logging.getLogger(__name__)

ws_router = APIRouter(tags=["websocket"])

ORDER_PLACE_MESSAGE_TYPE: str = "order.place"
ORDER_PLACED_MESSAGE_TYPE: str = "order.placed"
ERROR_MESSAGE_TYPE: str = "error"


WS_EXCEPTION_MAPPING: dict[type[Exception], tuple[str, Any]] = {
    json.JSONDecodeError: ("invalid_json", lambda exc: str(exc)),
    ValidationError: (
        "validation_error",
        lambda exc: json.dumps(exc.errors(), default=str),
    ),
    order_service.OrderSyncError: ("engine_error", lambda exc: str(exc)),
    IntegrityError: ("constraint_error", lambda exc: "Database constraint violated"),
}


@ws_router.websocket("/ws")
async def market_ws(websocket: WebSocket) -> None:
    """Accept a WebSocket connection and process incoming messages until disconnect."""

    if websocket.headers.get("origin") not in settings.ws_allowed_origins:
        raise WebSocketException(code=1008, reason="Origin is not allowed")
    token = websocket.cookies.get("access_token")
    if not token:
        raise WebSocketException(code=4401, reason="Authentication required")
    try:
        async with get_sessionmaker()() as session:
            user = await auth_service.get_user_from_token(token, session)
        expires_at = float(auth_service.decode_token(token)["exp"])
    except auth_service.InvalidCredentialsError as exc:
        raise WebSocketException(code=4401, reason="Invalid or expired token") from exc
    except auth_service.AuthConfigurationError as exc:
        raise WebSocketException(
            code=1011, reason="Authentication is unavailable"
        ) from exc

    websocket.state.user_id = user.id
    websocket.state.expires_at = expires_at
    await ws_manager.connect(websocket)

    async def close_on_expiry() -> None:
        await asyncio.sleep(max(0, expires_at - time.time()))
        ws_manager.disconnect(websocket)
        await websocket.close(code=4401, reason="Access token expired")

    expiry_task = asyncio.create_task(close_on_expiry())
    try:
        while time.time() < expires_at:
            message_raw = await websocket.receive_text()
            if time.time() >= expires_at:
                await expiry_task
                break
            await handle_message(websocket, message_raw)
        await expiry_task
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)
        expiry_task.cancel()
        with suppress(asyncio.CancelledError):
            await expiry_task


async def handle_message(websocket: WebSocket, message_raw: str) -> None:
    """Parse a raw WebSocket frame and dispatch it to the appropriate handler."""
    request_id: str | None = None

    try:
        message = json.loads(message_raw)
        request = WsMessage.model_validate(message)
        request_id = request.id

        if request.type == ORDER_PLACE_MESSAGE_TYPE:
            await order_place_handler(websocket, request)

    except Exception as exc:
        await send_error(websocket, request_id, exc)


async def send_error(
    websocket: WebSocket,
    request_id: str | None,
    exception: Exception,
) -> None:
    """Map a raised exception to a `WsError` and send it to the client."""
    for exc_type, (exc_code, detail_fn) in WS_EXCEPTION_MAPPING.items():
        if isinstance(exception, exc_type):
            await websocket.send_json(
                WsError(
                    type=ERROR_MESSAGE_TYPE,
                    id=request_id,
                    code=exc_code,
                    detail=detail_fn(exception),
                ).model_dump(mode="json")
            )
            return

    logger.error(
        "Unhandled WebSocket exception (request_id=%s)",
        request_id,
        exc_info=exception,
    )
    await websocket.send_json(
        WsError(
            type=ERROR_MESSAGE_TYPE,
            id=request_id,
            code="internal_error",
            detail="Unexpected server error",
        ).model_dump(mode="json")
    )


async def order_place_handler(websocket: WebSocket, request: WsMessage) -> None:
    """Validate an order payload, place the order, and return `order.placed`."""
    payload = OrderCreate.model_validate(
        {**request.payload, "user_id": websocket.state.user_id}
    )
    service = OrderService(sqs=get_aws_client("sqs"))
    registry = websocket.app.state.registry
    async with get_sessionmaker()() as session:
        order = await service.place_order(payload, session, registry)

    if websocket.application_state != WebSocketState.CONNECTED:
        return
    response_payload = OrderResponse.from_orm(order)
    await websocket.send_json(
        WsMessage(
            type=ORDER_PLACED_MESSAGE_TYPE,
            id=request.id,
            payload=response_payload.model_dump(mode="json"),
        ).model_dump(mode="json")
    )
