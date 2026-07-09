from datetime import datetime
from decimal import Decimal
from typing import Self, Literal

from pydantic import BaseModel, Field

from app.engine.models import Side, Trade as TradeDTO
from app.models import Trade as TradeORM


class TradeEvent(BaseModel):
    event_type: Literal["trade.matched"] = "trade.matched"
    dedup: str = Field(max_length=128)
    symbol: str = Field(max_length=32)
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    maker_order_id: int = Field(ge=1)
    taker_order_id: int = Field(ge=1)
    aggressor_side: Side
    sequence: int = Field(ge=1)

    @classmethod
    def from_trade_dto(cls, trade: TradeDTO) -> Self:
        return cls(
            dedup=f"{trade.symbol}:{trade.sequence}",
            symbol=trade.symbol,
            price=trade.price,
            quantity=trade.quantity,
            maker_order_id=trade.maker_order_id,
            taker_order_id=trade.taker_order_id,
            aggressor_side=trade.aggressor_side,
            sequence=trade.sequence,
        )


class TradeSettledEvent(BaseModel):
    event_type: Literal["trade.settled"] = "trade.settled"
    trade_id: int = Field(ge=1)
    dedup: str = Field(max_length=128)
    symbol: str = Field(max_length=32)
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    maker_order_id: int = Field(ge=1)
    taker_order_id: int = Field(ge=1)
    aggressor_side: Side
    sequence: int = Field(ge=1)
    created_at: datetime

    @classmethod
    def from_orm(cls, trade: TradeORM) -> Self:
        return cls(
            trade_id=trade.id,
            dedup=trade.dedup,
            symbol=trade.symbol,
            price=trade.price,
            quantity=trade.quantity,
            maker_order_id=trade.maker_order_id,
            taker_order_id=trade.taker_order_id,
            aggressor_side=trade.aggressor_side,
            sequence=trade.sequence,
            created_at=trade.created_at,
        )
