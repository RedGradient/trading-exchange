from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.models import Side
from app.models.trades import Trade
from app.services.settlement_service import settle_trade
from helpers import make_trade_event, seed_matched_orders

SYMBOL = "BTC-USD"
PRICE = Decimal("100.00")
MAKER_QUANTITY = Decimal("5")
TRADE_QUANTITY = Decimal("3")
TRADE_SEQUENCE = 3
AGGRESSOR_SIDE = Side.BUY


@pytest.mark.asyncio
async def test_settle_trade_new(db_session: AsyncSession) -> None:
    maker, taker = await seed_matched_orders(
        db_session,
        symbol=SYMBOL,
        price=PRICE,
        maker_quantity=MAKER_QUANTITY,
        trade_quantity=TRADE_QUANTITY,
    )
    trade_event = make_trade_event(
        maker_order_id=maker.id,
        taker_order_id=taker.id,
        symbol=SYMBOL,
        price=PRICE,
        quantity=TRADE_QUANTITY,
        sequence=TRADE_SEQUENCE,
        aggressor_side=AGGRESSOR_SIDE,
    )

    trade, is_new = await settle_trade(trade_event, db_session)

    assert is_new is True
    assert trade.id is not None
    assert trade.dedup == f"{SYMBOL}:{TRADE_SEQUENCE}"
    assert trade.symbol == SYMBOL
    assert trade.price == PRICE
    assert trade.quantity == TRADE_QUANTITY
    assert trade.maker_order_id == maker.id
    assert trade.taker_order_id == taker.id
    assert trade.aggressor_side == AGGRESSOR_SIDE
    assert trade.sequence == TRADE_SEQUENCE

    saved = await db_session.get(Trade, trade.id)
    assert saved is not None
    assert saved.dedup == trade_event.dedup


@pytest.mark.asyncio
async def test_settle_trade_exists(db_session: AsyncSession) -> None:
    maker, taker = await seed_matched_orders(
        db_session,
        symbol=SYMBOL,
        price=PRICE,
        maker_quantity=MAKER_QUANTITY,
        trade_quantity=TRADE_QUANTITY,
    )
    trade_event = make_trade_event(
        maker_order_id=maker.id,
        taker_order_id=taker.id,
        symbol=SYMBOL,
        price=PRICE,
        quantity=TRADE_QUANTITY,
        sequence=TRADE_SEQUENCE,
        aggressor_side=AGGRESSOR_SIDE,
    )

    first_trade, is_new = await settle_trade(trade_event, db_session)
    assert is_new is True

    existing_trade, is_new = await settle_trade(trade_event, db_session)
    assert is_new is False
    assert existing_trade.id == first_trade.id
    assert existing_trade.dedup == f"{SYMBOL}:{TRADE_SEQUENCE}"
