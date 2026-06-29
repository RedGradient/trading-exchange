from collections.abc import AsyncGenerator
from decimal import Decimal

import httpx
import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.registry import EngineRegistry
from app.main import app
from app.models.users import User
from app.session import get_db_session


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient]:
    db_session.add(User())
    await db_session.commit()

    async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.state.registry = EngineRegistry()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


def _limit_order_payload(
    *,
    side: str = "BUY",
    price: str = "100.00",
    quantity: str = "5",
) -> dict[str, object]:
    return {
        "user_id": 1,
        "symbol": "BTC-USD",
        "side": side,
        "type": "LIMIT",
        "price": price,
        "quantity": quantity,
    }


@pytest.mark.asyncio
async def test_place_order_returns_created_order(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post("/api/orders", json=_limit_order_payload())

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == 1
    assert data["symbol"] == "BTC-USD"
    assert data["side"] == "BUY"
    assert data["type"] == "LIMIT"
    assert data["status"] == "OPEN"
    assert Decimal(data["remaining"]) == Decimal("5")
    assert data["sequence"] > 0
    assert "created_at" in data


@pytest.mark.asyncio
async def test_place_order_validation_error(api_client: httpx.AsyncClient) -> None:
    response = await api_client.post(
        "/api/orders",
        json=_limit_order_payload(price=None), # type: ignore
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_get_order_returns_persisted_order(api_client: httpx.AsyncClient) -> None:
    created = await api_client.post("/api/orders", json=_limit_order_payload(side="SELL"))
    order_id = created.json()["id"]

    response = await api_client.get(f"/api/orders/{order_id}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == order_id
    assert response.json()["status"] == "OPEN"


@pytest.mark.asyncio
async def test_get_order_not_found(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/orders/999")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Order not found"}


@pytest.mark.asyncio
async def test_cancel_order_cancels_resting_order(api_client: httpx.AsyncClient) -> None:
    created = await api_client.post("/api/orders", json=_limit_order_payload(side="SELL"))
    order_id = created.json()["id"]

    response = await api_client.post(f"/api/orders/{order_id}/cancel")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_order_conflict_for_filled_order(
    api_client: httpx.AsyncClient,
) -> None:
    await api_client.post(
        "/api/orders",
        json=_limit_order_payload(side="SELL", quantity="5"),
    )
    taker = await api_client.post(
        "/api/orders",
        json=_limit_order_payload(side="BUY", quantity="5"),
    )
    order_id = taker.json()["id"]

    response = await api_client.post(f"/api/orders/{order_id}/cancel")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json() == {"detail": "Order cannot be cancelled"}


@pytest.mark.asyncio
async def test_get_order_book_empty_symbol(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/order_book/BTC-USD", params={"depth": 5})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "symbol": "BTC-USD",
        "asks": [],
        "bids": [],
    }


@pytest.mark.asyncio
async def test_get_order_book_returns_resting_levels(
    api_client: httpx.AsyncClient,
) -> None:
    await api_client.post(
        "/api/orders",
        json=_limit_order_payload(side="SELL", price="101.00", quantity="3"),
    )
    await api_client.post(
        "/api/orders",
        json=_limit_order_payload(side="BUY", price="99.00", quantity="2"),
    )

    response = await api_client.get("/api/order_book/BTC-USD", params={"depth": 5})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["symbol"] == "BTC-USD"
    assert len(data["asks"]) == 1
    assert Decimal(data["asks"][0][0]) == Decimal("101")
    assert Decimal(data["asks"][0][1]) == Decimal("3")
    assert len(data["bids"]) == 1
    assert Decimal(data["bids"][0][0]) == Decimal("99")
    assert Decimal(data["bids"][0][1]) == Decimal("2")
