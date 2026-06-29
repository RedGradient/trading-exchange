from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.engine.models import OrderStatus, OrderType, Side
from app.models.orders import Order as OrderORM


class OrderCreate(BaseModel):
    user_id: int = Field(description="Owner of the order. Must exist in the database.")
    symbol: str = Field(description="Trading pair symbol, for example `BTC-USD`.", max_length=32)
    side: Side = Field(description="Order side: `BUY` or `SELL`.")
    type: OrderType = Field(description="Order type: `LIMIT` or `MARKET`.")
    price: Decimal | None = Field(
        default=None,
        description="Limit price. Required for LIMIT orders; must be omitted for MARKET orders.",
    )
    quantity: Decimal = Field(description="Order quantity. Must be positive.", gt=0)

    @model_validator(mode="after")
    def validate_marker_order(self) -> Self:
        if self.type == OrderType.LIMIT and self.price is None:
            raise ValueError("LIMIT order requires price")
        if self.type == OrderType.MARKET and self.price is not None:
            raise ValueError("MARKET order must not have price")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        return self


class OrderResponse(BaseModel):
    id: int = Field(description="Unique order identifier assigned by the database.")
    user_id: int = Field(description="Owner of the order.")
    symbol: str = Field(description="Trading pair symbol, for example `BTC-USD`.")
    side: Side = Field(description="Order side: `BUY` or `SELL`.")
    type: OrderType = Field(description="Order type: `LIMIT` or `MARKET`.")
    price: Decimal | None = Field(
        description="Limit price. `null` for MARKET orders.",
    )
    quantity: Decimal = Field(description="Original order quantity.")
    remaining: Decimal = Field(
        description="Unfilled quantity still open or resting in the book.",
    )
    status: OrderStatus = Field(
        description=(
            "Current order status, for example `OPEN`, `PARTIALLY_FILLED`, "
            "`FILLED`, or `CANCELLED`."
        ),
    )
    sequence: int = Field(
        description="Matching engine sequence assigned when the order entered the book.",
        ge=0,
    )
    created_at: datetime = Field(description="Timestamp when the order was created.")

    @classmethod
    def from_orm(cls, order: OrderORM) -> Self: # type: ignore
        return cls(
            id=order.id,
            user_id=order.user_id,
            symbol=order.symbol,
            side=order.side,
            type=order.order_type,
            price=order.price,
            quantity=order.quantity,
            remaining=order.remaining,
            status=order.status,
            sequence=order.sequence,
            created_at=order.created_at,
        )


class OrderBookSnapshotResponse(BaseModel):
    symbol: str = Field(description="Trading pair symbol.")
    asks: list[tuple[Decimal, Decimal]] = Field(
        description="Sell levels as `(price, total_quantity)` pairs, best ask first.",
    )
    bids: list[tuple[Decimal, Decimal]] = Field(
        description="Buy levels as `(price, total_quantity)` pairs, best bid first.",
    )
