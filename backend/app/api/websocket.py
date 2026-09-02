"""WebSocket endpoint for market data and order commands."""

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.aws import get_aws_client
from app.schemas.orders import OrderCreate, OrderResponse
from app.schemas.websocket import WsError, WsMessage
from app.services import order_service
from app.services.order_service import OrderService
from app.services.ws_manager import ws_manager
from app.session import get_sessionmaker

ws_router = APIRouter(tags=["websocket"])

ORDER_PLACE_MESSAGE_TYPE: str = "order.place"
ORDER_PLACED_MESSAGE_TYPE: str = "order.placed"
ERROR_MESSAGE_TYPE: str = "error"


WS_EXCEPTION_MAPPING: dict[type[Exception], tuple[str, Any]] = {
    ValidationError: ("validation_error", lambda exc: exc.errors()),
    order_service.OrderSyncError: ("engine_error", lambda exc: str(exc)),
    IntegrityError: ("constraint_error", lambda exc: "Database constraint violated"),
}


@ws_router.websocket("/ws")
async def market_ws(websocket: WebSocket) -> None:
    """Accept a WebSocket connection and process incoming messages until disconnect."""
    await ws_manager.connect(websocket)
    try:
        while True:
            message_raw = await websocket.receive_text()
            await handle_message(websocket, message_raw)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


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


async def order_place_handler(websocket: WebSocket, request: WsMessage) -> None:
    """Validate an order payload, place the order, and return `order.placed`."""
    payload = OrderCreate.model_validate(request.payload)
    service = OrderService(sqs=get_aws_client("sqs"))
    registry = websocket.app.state.registry
    async with get_sessionmaker()() as session:
        order = await service.place_order(payload, session, registry)

    response = OrderResponse.from_orm(order)
    await websocket.send_json(
        WsMessage(
            type=ORDER_PLACED_MESSAGE_TYPE,
            id=request.id,
            payload=response.model_dump(mode="json"),
        ).model_dump(mode="json")
    )
