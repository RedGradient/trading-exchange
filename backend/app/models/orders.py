from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Integer, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.engine.models import OrderStatus, OrderType, Side
from app.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_user_id_symbol", "user_id", "symbol"),)

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[Side] = mapped_column(String(8), nullable=False)
    order_type: Mapped[OrderType] = mapped_column(String(10), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    remaining: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)

    status: Mapped[OrderStatus] = mapped_column(String(20), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
