from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Trade
from app.schemas.trades import TradeEvent


async def settle_trade(
    trade_event: TradeEvent,
    session: AsyncSession,
) -> tuple[Trade, bool]:
    existing = await session.scalar(
        select(Trade).where(Trade.dedup == trade_event.dedup)
    )
    if existing is not None:
        return existing, False

    trade = Trade(
        dedup=trade_event.dedup,
        symbol=trade_event.symbol,
        price=trade_event.price,
        quantity=trade_event.quantity,
        maker_order_id=trade_event.maker_order_id,
        taker_order_id=trade_event.taker_order_id,
        aggressor_side=trade_event.aggressor_side,
        sequence=trade_event.sequence,
    )
    session.add(trade)
    await session.commit()
    return trade, True
