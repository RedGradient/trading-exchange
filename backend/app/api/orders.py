from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.registry import EngineRegistry
from app.schemas.orders import OrderBookSnapshotResponse, OrderCreate, OrderResponse
from app.services.order_service import OrderService
from app.session import get_db_session

router = APIRouter(
    prefix="/api",
    tags=["Orders"],
)

_ORDER_NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Order with the given id does not exist.",
    },
}
_VALIDATION_ERROR = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "Invalid request body or query parameters.",
    },
}


def get_engine_registry(request: Request) -> EngineRegistry:
    return request.app.state.registry


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place a new order to the order book",
    description=(
        "Creates an order in the database and submits it to the matching engine "
        "for the given symbol. LIMIT orders require `price`; MARKET orders must "
        "not include `price`. The order is matched immediately against the resting "
        "book; any remainder is added to the book (LIMIT) or discarded (MARKET)."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "Invalid symbol for the engine or database constraint violation "
                "(for example, unknown `user_id`)."
            ),
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Failed to sync matching engine state to the database.",
        },
        **_VALIDATION_ERROR,
    },
)
async def place_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_db_session),
    registry: EngineRegistry = Depends(get_engine_registry),
) -> OrderResponse:
    service = OrderService()
    order = await service.place_order(payload, session, registry)
    return OrderResponse.from_orm(order)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    summary="Get order by id",
    description="Returns the current persisted state of a single order.",
    responses=_ORDER_NOT_FOUND,  # type: ignore
)
async def get_order(
    order_id: Annotated[int, Path(description="Unique order identifier.", ge=1)],
    session: AsyncSession = Depends(get_db_session),
) -> OrderResponse:
    service = OrderService()
    order = await service.get_order(order_id, session)
    return OrderResponse.from_orm(order)


@router.post(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel a resting order",
    description=(
        "Cancels a LIMIT order that is still open in the order book. "
        "Orders that are already filled, cancelled, rejected, or no longer "
        "resting in the in-memory book cannot be cancelled."
    ),
    responses={
        **_ORDER_NOT_FOUND,
        status.HTTP_409_CONFLICT: {
            "description": (
                "Order is in a terminal state or is not resting in the order book."
            ),
        },
    },
)
async def cancel_order(
    order_id: Annotated[int, Path(description="Unique order identifier.", ge=1)],
    session: AsyncSession = Depends(get_db_session),
    registry: EngineRegistry = Depends(get_engine_registry),
) -> OrderResponse:
    service = OrderService()
    order = await service.cancel_order(order_id, session, registry)
    return OrderResponse.from_orm(order)


@router.get(
    "/order_book/{symbol}",
    response_model=OrderBookSnapshotResponse,
    summary="Get order book snapshot",
    description=(
        "Returns aggregated bid and ask levels for a trading symbol. "
        "Each level is a `(price, total_quantity)` pair. "
        "An empty book is returned if the symbol has not traded yet."
    ),
    responses=_VALIDATION_ERROR,  # type: ignore
)
async def get_order_book(
    symbol: Annotated[
        str,
        Path(description="Trading pair symbol, for example `BTC-USD`."),
    ],
    depth: Annotated[
        int,
        Query(
            description="Maximum number of price levels per side.",
            ge=1,
            le=100,
        ),
    ] = 10,
    registry: EngineRegistry = Depends(get_engine_registry),
) -> OrderBookSnapshotResponse:
    service = OrderService()
    book = await service.get_order_book(symbol, depth, registry)
    return OrderBookSnapshotResponse(
        symbol=symbol,
        asks=book["asks"],
        bids=book["bids"],
    )
