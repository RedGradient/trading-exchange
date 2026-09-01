from typing import Any, Literal

from pydantic import BaseModel, Field


class WsMessage(BaseModel):
    """Envelope for bidirectional WebSocket messages.

    Clients send requests with a client-generated `id`; the server echoes
    the same `id` in the corresponding response or error.
    """

    type: str
    id: str
    payload: dict[str, Any]


class WsError(BaseModel):
    """Error response sent to the client when a request cannot be processed."""

    type: Literal["error"] = "error"
    id: str | None = Field(
        default=None,
        description=(
            "Request correlation id. None when the message could not be parsed "
            "(for example, invalid JSON)."
        ),
    )
    code: str = Field(description="Machine-readable error code.")
    detail: str = Field(description="Human-readable error detail.")
