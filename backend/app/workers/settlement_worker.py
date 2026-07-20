import asyncio
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.aws import get_aws_client
from app.config import settings
from app.schemas.trades import TradeEvent, TradeSettledEvent
from app.services.publish_service import publish_trade_settled
from app.services.settlement_service import settle_trade
from app.session import get_sessionmaker

logger = logging.getLogger(__name__)


async def _delete_message(client: Any, msg: dict) -> None:
    await asyncio.to_thread(
        client.delete_message,
        QueueUrl=settings.trades_queue_url,
        ReceiptHandle=msg["ReceiptHandle"],
    )


async def _receive_messages(sqs: Any) -> dict:
    return await asyncio.to_thread(
        sqs.receive_message,
        QueueUrl=settings.trades_queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,
    )


async def _process_message(
    msg: dict,
    sessionmaker: async_sessionmaker[AsyncSession],
    sqs: Any,
    sns: Any,
) -> None:
    trade_event = TradeEvent.model_validate_json(msg["Body"])

    if trade_event.event_type != "trade.matched":
        logger.warning("Unexpected event_type=%s", trade_event.event_type)
        raise ValueError(f"Unexpected event_type={trade_event.event_type!r}")

    async with sessionmaker() as session:
        trade, is_new = await settle_trade(trade_event, session)

    if is_new:
        logger.info("Settled trade %s (id=%s)", trade.dedup, trade.id)
    else:
        logger.info("Duplicate trade %s, skipping insert", trade.dedup)

    # Publish even for duplicates so a retry after failed SNS still emits the event.
    await publish_trade_settled(TradeSettledEvent.from_orm(trade), sns)
    logger.info("Published settled event for trade %s", trade.dedup)

    await _delete_message(sqs, msg)


async def handle_message(
    msg: dict,
    sessionmaker: async_sessionmaker[AsyncSession],
    sqs: Any,
    sns: Any,
) -> None:
    """Process one SQS message and apply delete / retry policy."""
    message_id = msg.get("MessageId")
    try:
        await _process_message(msg, sessionmaker, sqs, sns)
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "Invalid trade event (MessageId=%s), deleting: %s",
            message_id,
            exc,
        )
        await _delete_message(sqs, msg)
    except Exception:
        logger.exception(
            "Failed to settle trade message (MessageId=%s)",
            message_id,
        )


async def main() -> None:
    sqs = get_aws_client("sqs")
    sns = get_aws_client("sns")
    sessionmaker = get_sessionmaker()

    logger.info("Settlement worker started, polling %s", settings.trades_queue_url)

    while True:
        response = await _receive_messages(sqs)

        for msg in response.get("Messages", []):
            await handle_message(msg, sessionmaker, sqs, sns)


if __name__ == "__main__":
    logging.basicConfig(level=settings.log_level)
    asyncio.run(main())
