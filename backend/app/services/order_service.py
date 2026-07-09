from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.aws import get_aws_client
from app.schemas.orders import OrderCreate
from app.engine.models import Order as EngineOrder, OrderStatus
from app.models.orders import Order as OrderORM
from app.engine.registry import EngineRegistry
from app.engine.order_book import OrderBookSnapshot
from app.schemas.trades import TradeEvent
from app.services.publish_service import publish_trade_events


class OrderNotFoundException(Exception):
    pass


class OrderNotCancellableException(Exception):
    pass


class OrderSyncError(Exception):
    """Engine state could not be synced to the database."""


_TERMINAL_STATUSES = frozenset({
    OrderStatus.CANCELLED,
    OrderStatus.FILLED,
    OrderStatus.REJECTED,
})


class OrderService:
    def __init__(self, sqs: Any | None = None) -> None:
        self._sqs = sqs if sqs is not None else get_aws_client("sqs")

    async def place_order(
        self, 
        payload: OrderCreate,
        session: AsyncSession,
        registry: EngineRegistry
    ) -> OrderORM:
        list_of_trades: List[TradeEvent] = []

        async with session.begin():
            # Creaete Order ORM
            order_orm = create_order_orm(payload)
            session.add(order_orm)
            await session.flush()

            # Convert to engine Order
            engine = registry.get_engine(payload.symbol)
            engine_order = to_engine_order(order_orm)

            # Match the order
            trades = engine.place(engine_order)

            # Update taker in database
            order_orm.remaining = engine_order.remaining
            order_orm.status = engine_order.status
            order_orm.sequence = engine_order.sequence

            for trade in trades:
                # Get maker ORM
                maker_orm = await session.get(OrderORM, trade.maker_order_id)

                if maker_orm is None:
                    raise OrderSyncError(
                        f"Maker order {trade.maker_order_id} missing in database"
                    )

                # Update maker in database
                maker_orm.remaining -= trade.quantity
                maker_orm.status = (
                    OrderStatus.FILLED if maker_orm.remaining == 0
                    else OrderStatus.PARTIALLY_FILLED
                )

                list_of_trades.append(TradeEvent.from_trade_dto(trade))

        publish_trade_events(list_of_trades, self._sqs)

        return order_orm

    async def get_order(self, order_id: int, session: AsyncSession) -> OrderORM:
        if (order := await session.get(OrderORM, order_id)) is None:
            raise OrderNotFoundException()
        return order
    
    async def cancel_order(
        self,
        order_id: int,
        session: AsyncSession,
        registry: EngineRegistry,
    ) -> OrderORM:
        if (order_orm := await session.get(OrderORM, order_id)) is None:
            raise OrderNotFoundException()

        if order_orm.status in _TERMINAL_STATUSES:
            raise OrderNotCancellableException()

        engine = registry.get_engine(order_orm.symbol)
        if (engine_order := engine.cancel(order_id)) is None:
            raise OrderNotCancellableException()

        order_orm.status = engine_order.status
        await session.commit()

        return order_orm
    
    async def get_order_book(
        self,
        symbol: str,
        depth: int,
        registry: EngineRegistry
    ) -> OrderBookSnapshot:
        engine = registry.get_engine(symbol)
        return engine.snapshot(depth)
        



            


def create_order_orm(payload: OrderCreate) -> OrderORM:
    return OrderORM(
        user_id=payload.user_id,
        symbol=payload.symbol,
        side=payload.side,
        order_type=payload.type,
        price=payload.price,
        quantity=payload.quantity,
        remaining=payload.quantity,
        status=OrderStatus.OPEN,
        sequence=0,
    )


def to_engine_order(order_orm: OrderORM) -> EngineOrder:
    return EngineOrder(
        id=order_orm.id,
        symbol=order_orm.symbol,
        side=order_orm.side,
        type=order_orm.order_type,
        price=order_orm.price,
        quantity=order_orm.quantity,
        remaining=order_orm.remaining,
        status=order_orm.status,
        sequence=0,
    )