from dataclasses import dataclass
from enum import StrEnum
from decimal import Decimal


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    id: int
    symbol: str
    side: Side
    type: OrderType
    price: Decimal | None
    quantity: Decimal
    remaining: Decimal
    status: OrderStatus
    sequence: int


@dataclass
class Trade:
    symbol: str
    price: Decimal
    quantity: Decimal
    maker_order_id: int
    taker_order_id: int
    aggressor_side: Side
    sequence: int
