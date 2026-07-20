import itertools
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.matching_engine import MatchingEngine
from app.engine.models import Order, OrderStatus, OrderType, Side
from app.engine.order_book import OrderBook
from app.models.orders import Order as OrderORM
from app.models.users import User
from app.schemas.trades import TradeEvent

_order_id = itertools.count(1)


def make_order(
    *,
    side: Side = Side.BUY,
    type: OrderType = OrderType.LIMIT,
    price: Decimal | str | int | float | None = "100",
    quantity: Decimal | str | int | float = "1",
    symbol: str = "BTC-USD",
    order_id: int | None = None,
) -> Order:
    if order_id is None:
        order_id = next(_order_id)

    qty = Decimal(str(quantity))
    order_price = None if price is None else Decimal(str(price))

    return Order(
        id=order_id,
        symbol=symbol,
        side=side,
        type=type,
        price=order_price,
        quantity=qty,
        remaining=qty,
        status=OrderStatus.OPEN,
        sequence=0,
    )


def empty_engine(symbol: str = "BTC-USD") -> MatchingEngine:
    return MatchingEngine(symbol, OrderBook())


def filled_engine(
    *,
    symbol: str = "BTC-USD",
    asks: list[tuple[Decimal | str | int | float, Decimal | str | int | float]]
    | None = None,
    bids: list[tuple[Decimal | str | int | float, Decimal | str | int | float]]
    | None = None,
) -> MatchingEngine:
    """MatchingEngine with resting limit orders in the book.

    asks — sell limits (rest on ask side)
    bids — buy limits (rest on bid side)

    Keep ask prices above bid prices,
    otherwise orders will match while building the book.
    """
    engine = empty_engine(symbol)

    for price, quantity in asks or []:
        engine.place(
            make_order(
                side=Side.SELL,
                price=price,
                quantity=quantity,
                symbol=symbol,
            )
        )

    for price, quantity in bids or []:
        engine.place(
            make_order(
                side=Side.BUY,
                price=price,
                quantity=quantity,
                symbol=symbol,
            )
        )

    return engine


async def seed_matched_orders(
    session: AsyncSession,
    *,
    symbol: str,
    price: Decimal,
    maker_quantity: Decimal,
    trade_quantity: Decimal,
) -> tuple[OrderORM, OrderORM]:
    """Insert a user and maker/taker orders for settlement tests."""
    session.add(User())
    await session.flush()

    maker = OrderORM(
        user_id=1,
        symbol=symbol,
        side=Side.SELL,
        order_type=OrderType.LIMIT,
        price=price,
        quantity=maker_quantity,
        remaining=maker_quantity - trade_quantity,
        status=OrderStatus.PARTIALLY_FILLED,
        sequence=1,
    )
    taker = OrderORM(
        user_id=1,
        symbol=symbol,
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        price=price,
        quantity=trade_quantity,
        remaining=Decimal("0"),
        status=OrderStatus.FILLED,
        sequence=2,
    )
    session.add_all([maker, taker])
    await session.commit()
    return maker, taker


def make_trade_event(
    *,
    maker_order_id: int,
    taker_order_id: int,
    symbol: str,
    price: Decimal,
    quantity: Decimal,
    sequence: int,
    aggressor_side: Side,
) -> TradeEvent:
    return TradeEvent(
        dedup=f"{symbol}:{sequence}",
        symbol=symbol,
        price=price,
        quantity=quantity,
        maker_order_id=maker_order_id,
        taker_order_id=taker_order_id,
        aggressor_side=aggressor_side,
        sequence=sequence,
    )


def make_sqs_message(
    body: str,
    *,
    message_id: str = "msg-1",
    receipt_handle: str = "rh-1",
) -> dict[str, str]:
    return {
        "MessageId": message_id,
        "ReceiptHandle": receipt_handle,
        "Body": body,
    }
