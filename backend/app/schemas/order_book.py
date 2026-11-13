from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderBookSnapshotPayload(BaseModel):
    symbol: str = Field(description="Trading pair symbol.")
    asks: list[tuple[Decimal, Decimal]] = Field(
        description="Sell levels as `(price, total_quantity)` pairs, best ask first.",
    )
    bids: list[tuple[Decimal, Decimal]] = Field(
        description="Buy levels as `(price, total_quantity)` pairs, best bid first.",
    )


class OrderBookSnapshotEvent(OrderBookSnapshotPayload):
    event_type: Literal["order_book.snapshot"] = "order_book.snapshot"
