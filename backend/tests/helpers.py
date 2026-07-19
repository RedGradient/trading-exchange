import itertools
from decimal import Decimal

from app.engine.matching_engine import MatchingEngine
from app.engine.models import Order, OrderStatus, OrderType, Side
from app.engine.order_book import OrderBook

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
