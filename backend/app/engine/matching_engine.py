from collections.abc import Callable
from typing import List

from app.engine.models import Order, Side, OrderType, Trade, OrderStatus
from app.engine.order_book import OrderBook, OrderBookSnapshot


class SymbolMismatchError(ValueError):
    """Order symbol does not match the engine symbol."""


class MatchingEngine:
    def __init__(self, symbol: str, order_book: OrderBook):
        self._sequence = 0
        self._order_book = order_book
        self._symbol = symbol

    def place(self, order: Order) -> List[Trade]:
        """
        Matches an order against the book.

        The incoming (taker) order is matched by price-time priority against opposite-side
        makers. LIMIT remainder is added to the book; MARKET remainder is
        discarded. Updates order status and returns all trades produced.

        Raises:
            SymbolMismatchError: if order.symbol does not match the engine.
        
        Returns:
            list[Trade]: Trades done by this matching process. Empty if no matching occurred.
        """

        if order.symbol != self._symbol:
            raise SymbolMismatchError()

        order.sequence = self._next_seq()

        if order.side == Side.BUY:

            match order.type:
                case OrderType.LIMIT:
                    assert order.price is not None, "LIMIT order must have a price"
                    limit_price = order.price
                    price_crosses = lambda maker: maker.price <= limit_price  # noqa: E731
                case OrderType.MARKET:
                    price_crosses = lambda _maker: True  # noqa: E731

            return self._match_loop(
                order,
                peek_maker=self._order_book.peek_best_ask,
                pop_maker=self._order_book.pop_best_ask,
                is_market=order.type == OrderType.MARKET,
                price_crosses=price_crosses,
            )

        if order.side == Side.SELL:
            match order.type:
                case OrderType.LIMIT:
                    assert order.price is not None, "LIMIT order must have a price"
                    limit_price = order.price
                    price_crosses = lambda maker: maker.price >= limit_price  # noqa: E731
                case OrderType.MARKET:
                    price_crosses = lambda _maker: True  # noqa: E731

            return self._match_loop(
                order,
                peek_maker=self._order_book.peek_best_bid,
                pop_maker=self._order_book.pop_best_bid,
                is_market=order.type == OrderType.MARKET,
                price_crosses=price_crosses,
            )

        return []

    def cancel(self, order_id: int) -> Order | None:
        """
        Cancel a resting order by id.

        Removes the order from the book and sets its status to CANCELLED.
        Has no effect on orders that are already filled or unknown.

        Returns:
            bool: True if the order was found and cancelled; False otherwise.
        """
        return self._order_book.cancel(order_id)
    
    def snapshot(self, depth: int) -> OrderBookSnapshot:
        return self._order_book.snapshot(depth)

    def _match_loop(
        self,
        order: Order,
        *,
        peek_maker: Callable[[], Order | None],
        pop_maker: Callable[[], Order | None],
        is_market: bool,
        price_crosses: Callable[[Order], bool],
    ) -> List[Trade]:
        trades: List[Trade] = []

        while order.remaining > 0:
            maker = peek_maker()
            if maker is None:
                break

            assert maker.price is not None

            if not is_market and not price_crosses(maker):
                order.status = OrderStatus.PARTIALLY_FILLED if trades else OrderStatus.OPEN
                self._order_book.add(order)
                return trades

            trades.append(self._match(order, maker))
            self._finalize_maker(maker, pop_maker)

        if order.remaining > 0:
            if is_market:
                order.status = (
                    OrderStatus.PARTIALLY_FILLED if trades else OrderStatus.CANCELLED
                )
            else:
                order.status = OrderStatus.PARTIALLY_FILLED if trades else OrderStatus.OPEN
                self._order_book.add(order)
        else:
            order.status = OrderStatus.FILLED

        return trades

    def _match(self, order: Order, maker: Order) -> Trade:
        qty = min(order.remaining, maker.remaining)
        maker.remaining -= qty
        order.remaining -= qty

        assert maker.price is not None

        return Trade(
            symbol=order.symbol,
            price=maker.price,
            quantity=qty,
            maker_order_id=maker.id,
            taker_order_id=order.id,
            aggressor_side=order.side,
            sequence=self._next_seq(),
        )

    def _finalize_maker(
        self,
        maker: Order,
        pop_maker: Callable[[], Order | None],
    ) -> None:
        if maker.remaining == 0:
            maker.status = OrderStatus.FILLED
            pop_maker()
        else:
            maker.status = OrderStatus.PARTIALLY_FILLED

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence
