import asyncio
from typing import Any

from app.config import settings
from app.schemas.trades import TradeEvent, TradeSettledEvent


def publish_trade_events(trade_events: list[TradeEvent], sqs: Any) -> None:
    if not trade_events:
        return

    for event in trade_events:
        sqs.send_message(
            QueueUrl=settings.trades_queue_url,
            MessageBody=event.model_dump_json(),
        )


async def publish_trade_settled(event: TradeSettledEvent, sns: Any) -> None:
    await asyncio.to_thread(
        sns.publish,
        TopicArn=settings.trades_settled_topic_arn,
        Message=event.model_dump_json(),
    )
