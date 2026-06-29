from decimal import Decimal

import pytest

from app.services.order_service import OrderNotCancellableException, OrderNotFoundException, OrderService
from app.engine.registry import EngineRegistry
from app.schemas.orders import OrderCreate
from app.engine.models import Side, OrderType, OrderStatus
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.users import User

from app.models.orders import Order


@pytest.mark.asyncio
async def test_place_order_resting_in_db(db_session: AsyncSession) -> None:
    db_session.add(User())
    await db_session.commit()
    service = OrderService()
    registry = EngineRegistry()

    placed = await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.BUY, type=OrderType.LIMIT,
        price=Decimal("100.00"), quantity=Decimal("5")
    ), db_session, registry)

    saved = await db_session.get(Order, placed.id)
    
    assert saved is not None
    assert saved.status == OrderStatus.OPEN
    assert saved.remaining == Decimal("5")
    assert saved.sequence > 0


@pytest.mark.asyncio
async def test_place_order_maker_in_db(db_session: AsyncSession) -> None:
    db_session.add(User())
    await db_session.commit()
    service = OrderService()
    registry = EngineRegistry()

    # 1) maker — sell 5 @ 100
    await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.SELL, type=OrderType.LIMIT,
        price=Decimal("100.00"), quantity=Decimal("5")
    ), db_session, registry)

    # 2) taker — buy 3 @ 100
    await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.BUY, type=OrderType.LIMIT,
        price=Decimal("100"), quantity=Decimal("3"),
    ), db_session, registry)

    maker = await db_session.get(Order, 1)
    taker = await db_session.get(Order, 2)

    # Maker
    assert maker is not None
    assert maker.remaining == Decimal("2")
    assert maker.status == OrderStatus.PARTIALLY_FILLED
    assert maker.sequence > 0

    # Taker
    assert taker is not None
    assert taker.remaining == Decimal("0")
    assert taker.status == OrderStatus.FILLED
    assert taker.sequence > 0


@pytest.mark.asyncio
async def test_cancel_order_ok(db_session: AsyncSession) -> None:
    db_session.add(User())
    await db_session.commit()
    service = OrderService()
    registry = EngineRegistry()

    placed = await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.SELL, type=OrderType.LIMIT,
        price=Decimal("100.00"), quantity=Decimal("5")
    ), db_session, registry)

    cancelled = await service.cancel_order(placed.id, db_session, registry)
    cancelled = await db_session.get(Order, cancelled.id)

    assert cancelled is not None
    assert cancelled.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_order_not_found(db_session: AsyncSession) -> None:
    service = OrderService()
    registry = EngineRegistry()

    with pytest.raises(OrderNotFoundException):
        await service.cancel_order(order_id=7, session=db_session, registry=registry)


@pytest.mark.asyncio
async def test_cancel_order_not_cancellable_due_cancelled_status(db_session: AsyncSession) -> None:
    db_session.add(User())
    await db_session.commit()
    service = OrderService()
    registry = EngineRegistry()

    placed = await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.SELL, type=OrderType.LIMIT,
        price=Decimal("100.00"), quantity=Decimal("5")
    ), db_session, registry)

    # Cancel placed order
    await service.cancel_order(placed.id, db_session, registry)

    with pytest.raises(OrderNotCancellableException):
        # Try cancel cancelled order
        await service.cancel_order(placed.id, db_session, registry)


@pytest.mark.asyncio
async def test_cancel_order_not_cancellable_due_filled_status(db_session: AsyncSession) -> None:
    db_session.add(User())
    await db_session.commit()
    service = OrderService()
    registry = EngineRegistry()

    _maker = await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.SELL, type=OrderType.LIMIT,
        price=Decimal("100.00"), quantity=Decimal("5")
    ), db_session, registry)
    taker = await service.place_order(OrderCreate(
        user_id=1, symbol="BTC-USD",
        side=Side.BUY, type=OrderType.LIMIT,
        price=Decimal("100.00"), quantity=Decimal("5")
    ), db_session, registry)

    with pytest.raises(OrderNotCancellableException):
        # Try cancel filled order
        await service.cancel_order(taker.id, db_session, registry)
