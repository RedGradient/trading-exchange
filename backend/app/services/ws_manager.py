import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket
from pydantic import ValidationError

from app.aws import get_aws_client
from app.config import settings
from app.schemas.trades import TradeSettledEvent

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("WS connected, clients=%s", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("WS disconnected, clients=%s", len(self._connections))

    async def broadcast_json(self, message: dict) -> None:
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)


ws_manager = ConnectionManager()


def receive_from_ws_fanout_queue(sqs: Any) -> list[dict]:
    response = sqs.receive_message(
        QueueUrl=settings.ws_fanout_queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=20,
    )
    return response.get("Messages", [])


def parse_trade_settled(msg: dict) -> dict:
    """Parse SQS message body into a TradeSettledEvent payload dict.

    SNS→SQS delivery wraps the original JSON in an envelope with a Message field.
    """
    body = json.loads(msg["Body"])
    if isinstance(body, dict) and "Message" in body:
        raw_event = body["Message"]
        payload = json.loads(raw_event) if isinstance(raw_event, str) else raw_event
    else:
        payload = body

    event = TradeSettledEvent.model_validate(payload)
    return event.model_dump(mode="json")


def delete_message(sqs: Any, msg: dict) -> None:
    sqs.delete_message(
        QueueUrl=settings.ws_fanout_queue_url,
        ReceiptHandle=msg["ReceiptHandle"],
    )


async def ws_fanout_loop() -> None:
    sqs = get_aws_client("sqs")
    logger.info(
        "WS fan-out loop started, polling %s",
        settings.ws_fanout_queue_url,
    )

    while True:
        try:
            messages = await asyncio.to_thread(receive_from_ws_fanout_queue, sqs)
            for msg in messages:
                try:
                    payload = parse_trade_settled(msg)
                    await ws_manager.broadcast_json(
                        {
                            "type": "trade.settled",
                            "payload": payload,
                        }
                    )
                    await asyncio.to_thread(delete_message, sqs, msg)
                except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                    logger.warning(
                        "Invalid fan-out message (MessageId=%s), deleting: %s",
                        msg.get("MessageId"),
                        exc,
                    )
                    await asyncio.to_thread(delete_message, sqs, msg)
                except Exception:
                    logger.exception(
                        "Failed to broadcast fan-out message (MessageId=%s)",
                        msg.get("MessageId"),
                    )
        except asyncio.CancelledError:
            logger.info("WS fan-out loop cancelled")
            raise
        except Exception:
            logger.exception("WS fan-out poll failed")
            await asyncio.sleep(1)
