"""Adapt the Rust engine to the application's Python order models."""

from matching_engine_rust import MatchingEngine as RustMatchingEngine
from matching_engine_rust import SymbolMismatchError as RustSymbolMismatchError

from app.engine.matching_engine import SymbolMismatchError
from app.engine.models import Order, OrderStatus, OrderType, Side, Trade
from app.engine.order_book import OrderBookSnapshot


class _OrderBookView:
    """Expose resting Python orders for inspection without duplicating the book."""

    def __init__(self, engine: RustMatchingEngine, orders: dict[int, Order]):
        self._engine = engine
        self._orders = orders

    def peek_best_ask(self) -> Order | None:
        order_id = self._engine.best_ask_id()
        return self._orders.get(order_id) if order_id is not None else None

    def peek_best_bid(self) -> Order | None:
        order_id = self._engine.best_bid_id()
        return self._orders.get(order_id) if order_id is not None else None


class MatchingEngine:
    """Match in Rust while preserving updates to Python order objects."""

    def __init__(self, symbol: str):
        self._engine = RustMatchingEngine(symbol)
        # Keep references only for resting orders so existing callers observe fills.
        self._orders: dict[int, Order] = {}
        self._order_book = _OrderBookView(self._engine, self._orders)

    def place(self, order: Order) -> list[Trade]:
        try:
            result = self._engine.place(order)
        except RustSymbolMismatchError as exc:
            raise SymbolMismatchError(str(exc)) from exc

        order.remaining = result["remaining"]
        order.status = OrderStatus(result["status"])
        order.sequence = result["sequence"]

        for update in result["makers"]:
            maker = self._orders.get(update["id"])
            if maker is not None:
                maker.remaining = update["remaining"]
                maker.status = OrderStatus(update["status"])
                if maker.status == OrderStatus.FILLED:
                    del self._orders[maker.id]

        if order.type == OrderType.LIMIT and order.remaining > 0:
            self._orders[order.id] = order

        return [
            Trade(**{**trade, "aggressor_side": Side(trade["aggressor_side"])})
            for trade in result["trades"]
        ]

    def cancel(self, order_id: int) -> Order | None:
        update = self._engine.cancel(order_id)
        if update is None:
            return None
        order = self._orders.pop(order_id)
        order.remaining = update["remaining"]
        order.status = OrderStatus(update["status"])
        return order

    def snapshot(self, depth: int) -> OrderBookSnapshot:
        return self._engine.snapshot(depth)
