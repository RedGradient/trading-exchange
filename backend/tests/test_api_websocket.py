import asyncio
import json
from collections.abc import Generator
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from app.api.websocket import (
    ERROR_MESSAGE_TYPE,
    ORDER_PLACE_MESSAGE_TYPE,
    ORDER_PLACED_MESSAGE_TYPE,
)
from app.engine.models import OrderStatus, Side
from app.engine.registry import EngineRegistry
from app.main import app
from app.models.users import User
from app.schemas.orders import OrderCreate, OrderResponse
from app.schemas.websocket import WsError, WsMessage
from app.services.order_service import OrderService, OrderSyncError
from tests.test_api_orders import _limit_order_payload


@pytest.fixture
def ws_client(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient]:
    async def seed_user() -> None:
        async with db_sessionmaker() as session:
            session.add(User())
            await session.commit()

    asyncio.run(seed_user())

    monkeypatch.setattr("app.api.websocket.get_sessionmaker", lambda: db_sessionmaker)
    monkeypatch.setattr("app.api.websocket.get_aws_client", lambda _service: MagicMock())

    async def noop_fanout() -> None:
        return

    monkeypatch.setattr("app.main.ws_fanout_loop", noop_fanout)
    app.state.registry = EngineRegistry()

    with TestClient(app) as client:
        yield client


def _order_place_message(*, request_id: str = "req-1", payload: dict | None = None) -> str:
    if payload is None:
        payload = OrderCreate.model_validate(_limit_order_payload()).model_dump(mode="json")
    message = WsMessage(
        type=ORDER_PLACE_MESSAGE_TYPE,
        id=request_id,
        payload=payload,
    )
    return json.dumps(message.model_dump(mode="json"))


def _receive_ws_error(ws_client: TestClient, message: str) -> WsError:
    with ws_client.websocket_connect("/ws") as ws:
        ws.send_text(message)
        raw = ws.receive_text()
    return WsError.model_validate_json(raw)


def test_order_create_returns_created_order(ws_client: TestClient) -> None:
    payload = OrderCreate.model_validate(
        _limit_order_payload(side="SELL", price="101.00", quantity="3")
    )
    message = WsMessage(
        type=ORDER_PLACE_MESSAGE_TYPE,
        id="req-1",
        payload=payload.model_dump(mode="json"),
    )

    with ws_client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(message.model_dump(mode="json")))
        raw = ws.receive_text()

    response = WsMessage.model_validate_json(raw)
    assert response.type == ORDER_PLACED_MESSAGE_TYPE
    assert response.id == "req-1"

    order = OrderResponse.model_validate(response.payload)
    assert order.id == 1
    assert order.symbol == payload.symbol


@pytest.mark.parametrize(
    ("side", "price", "best_order_attr"),
    [
        (Side.SELL, "101.00", "peek_best_ask"),
        (Side.BUY, "99.00", "peek_best_bid"),
    ],
)
def test_order_create_updates_order_book(
    ws_client: TestClient,
    side: Side,
    price: str,
    best_order_attr: str,
) -> None:
    payload = OrderCreate.model_validate(
        _limit_order_payload(side=side.value, price=price, quantity="3")
    )
    message = WsMessage(
        type=ORDER_PLACE_MESSAGE_TYPE,
        id="req-1",
        payload=payload.model_dump(mode="json"),
    )

    with ws_client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps(message.model_dump(mode="json")))
        # Wait for order.placed so place_order finishes before we inspect the book.
        ws.receive_text()

    registry: EngineRegistry = app.state.registry
    engine = registry.get_engine("BTC-USD")

    # Select the best ask or bid in the book
    order = getattr(engine._order_book, best_order_attr)()
    assert order is not None
    assert order.symbol == payload.symbol
    assert order.side == side
    assert order.price == Decimal(price)
    assert order.quantity == Decimal("3")
    assert order.remaining == Decimal("3")
    assert order.status == OrderStatus.OPEN


def test_order_create_bad_request_json(ws_client: TestClient) -> None:
    response = _receive_ws_error(ws_client, '{ "a": 1 ')
    assert response.type == ERROR_MESSAGE_TYPE
    assert response.id is None
    assert response.code == "invalid_json"
    assert response.detail


def test_order_create_validation_error(ws_client: TestClient) -> None:
    payload = {
        "user_id": 1,
        "symbol": "BTC-USD",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": "5",
    }
    response = _receive_ws_error(
        ws_client,
        _order_place_message(request_id="req-val", payload=payload),
    )
    assert response.type == ERROR_MESSAGE_TYPE
    assert response.id == "req-val"
    assert response.code == "validation_error"
    errors = json.loads(response.detail)
    assert isinstance(errors, list)
    assert errors


def test_order_create_engine_error(ws_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def raise_engine_error(*_args: object, **_kwargs: object) -> None:
        raise OrderSyncError("maker order missing in database")

    monkeypatch.setattr(OrderService, "place_order", raise_engine_error)

    response = _receive_ws_error(ws_client, _order_place_message(request_id="req-engine"))
    assert response.type == ERROR_MESSAGE_TYPE
    assert response.id == "req-engine"
    assert response.code == "engine_error"
    assert "maker order missing" in response.detail


def test_order_create_constraint_error(
    ws_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def raise_integrity_error(*_args: object, **_kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("fk violation"))

    monkeypatch.setattr(OrderService, "place_order", raise_integrity_error)

    response = _receive_ws_error(ws_client, _order_place_message(request_id="req-db"))
    assert response.type == ERROR_MESSAGE_TYPE
    assert response.id == "req-db"
    assert response.code == "constraint_error"
    assert response.detail == "Database constraint violated"


def test_order_create_internal_error(ws_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def raise_unhandled(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(OrderService, "place_order", raise_unhandled)

    response = _receive_ws_error(ws_client, _order_place_message(request_id="req-internal"))
    assert response.type == ERROR_MESSAGE_TYPE
    assert response.id == "req-internal"
    assert response.code == "internal_error"
    assert response.detail == "Unexpected server error"
