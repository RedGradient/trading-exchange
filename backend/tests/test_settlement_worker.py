import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.engine.models import Side
from app.models.trades import Trade
from app.schemas.trades import TradeSettledEvent
from app.workers.settlement_worker import handle_message
from helpers import make_sqs_message, make_trade_event, seed_matched_orders

SYMBOL = "BTC-USD"
PRICE = Decimal("100.00")
MAKER_QUANTITY = Decimal("5")
TRADE_QUANTITY = Decimal("3")
TRADE_SEQUENCE = 3
AGGRESSOR_SIDE = Side.BUY
RECEIPT_HANDLE = "rh-1"


@pytest.fixture
def sqs() -> MagicMock:
    return MagicMock()


@pytest.fixture
def sns() -> MagicMock:
    return MagicMock()


async def _seed_trade_message(
    session: AsyncSession,
) -> tuple[dict[str, str], str]:
    maker, taker = await seed_matched_orders(
        session,
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
    msg = make_sqs_message(
        trade_event.model_dump_json(),
        receipt_handle=RECEIPT_HANDLE,
    )
    return msg, trade_event.dedup


def _assert_deleted(sqs: MagicMock) -> None:
    sqs.delete_message.assert_called_once_with(
        QueueUrl=settings.trades_queue_url,
        ReceiptHandle=RECEIPT_HANDLE,
    )


def _assert_not_deleted(sqs: MagicMock) -> None:
    sqs.delete_message.assert_not_called()


def _assert_settled_published(sns: MagicMock, *, dedup: str) -> None:
    sns.publish.assert_called_once()
    _, kwargs = sns.publish.call_args
    assert kwargs["TopicArn"] == settings.trades_settled_topic_arn
    event = TradeSettledEvent.model_validate_json(kwargs["Message"])
    assert event.event_type == "trade.settled"
    assert event.dedup == dedup
    assert event.symbol == SYMBOL
    assert event.price == PRICE
    assert event.quantity == TRADE_QUANTITY
    assert event.sequence == TRADE_SEQUENCE
    assert event.aggressor_side == AGGRESSOR_SIDE


@pytest.mark.asyncio
async def test_handle_message_settles_publishes_and_deletes(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sqs: MagicMock,
    sns: MagicMock,
) -> None:
    msg, dedup = await _seed_trade_message(db_session)

    await handle_message(msg, db_sessionmaker, sqs, sns)

    async with db_sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(Trade))
        trade = await session.scalar(select(Trade).where(Trade.dedup == dedup))

    assert count == 1
    assert trade is not None
    _assert_settled_published(sns, dedup=dedup)
    _assert_deleted(sqs)


@pytest.mark.asyncio
async def test_handle_message_duplicate_still_publishes_and_deletes(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sqs: MagicMock,
    sns: MagicMock,
) -> None:
    msg, dedup = await _seed_trade_message(db_session)

    await handle_message(msg, db_sessionmaker, sqs, sns)
    await handle_message(msg, db_sessionmaker, sqs, sns)

    async with db_sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(Trade))

    assert count == 1
    assert sns.publish.call_count == 2
    assert sqs.delete_message.call_count == 2
    second_event = TradeSettledEvent.model_validate_json(
        sns.publish.call_args_list[1].kwargs["Message"]
    )
    assert second_event.dedup == dedup


@pytest.mark.asyncio
async def test_handle_message_invalid_body_deletes_without_publish(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sqs: MagicMock,
    sns: MagicMock,
) -> None:
    msg = make_sqs_message("{not-json", receipt_handle=RECEIPT_HANDLE)

    await handle_message(msg, db_sessionmaker, sqs, sns)

    sns.publish.assert_not_called()
    _assert_deleted(sqs)


@pytest.mark.asyncio
async def test_handle_message_unexpected_event_type_deletes_without_publish(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sqs: MagicMock,
    sns: MagicMock,
) -> None:
    body = json.dumps(
        {
            "event_type": "trade.settled",
            "dedup": f"{SYMBOL}:{TRADE_SEQUENCE}",
            "symbol": SYMBOL,
            "price": str(PRICE),
            "quantity": str(TRADE_QUANTITY),
            "maker_order_id": 1,
            "taker_order_id": 2,
            "aggressor_side": AGGRESSOR_SIDE.value,
            "sequence": TRADE_SEQUENCE,
        }
    )
    msg = make_sqs_message(body, receipt_handle=RECEIPT_HANDLE)

    await handle_message(msg, db_sessionmaker, sqs, sns)

    sns.publish.assert_not_called()
    _assert_deleted(sqs)


@pytest.mark.asyncio
async def test_handle_message_settle_failure_does_not_delete(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sqs: MagicMock,
    sns: MagicMock,
) -> None:
    msg, _ = await _seed_trade_message(db_session)

    with patch(
        "app.workers.settlement_worker.settle_trade",
        side_effect=RuntimeError("db down"),
    ):
        await handle_message(msg, db_sessionmaker, sqs, sns)

    sns.publish.assert_not_called()
    _assert_not_deleted(sqs)


@pytest.mark.asyncio
async def test_handle_message_sns_failure_does_not_delete(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sqs: MagicMock,
    sns: MagicMock,
) -> None:
    msg, _ = await _seed_trade_message(db_session)
    sns.publish.side_effect = RuntimeError("sns down")

    await handle_message(msg, db_sessionmaker, sqs, sns)

    sns.publish.assert_called_once()
    _assert_not_deleted(sqs)
