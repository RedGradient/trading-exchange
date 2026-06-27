from sortedcontainers import SortedDict
from collections import deque
from decimal import Decimal
from app.engine.models import Order, Side, OrderStatus

class OrderBook:
    def __init__(self):
        self._index: dict[int, Order] = dict()
        self._asks: dict[Decimal, deque[Order]] = SortedDict()
        self._bids: dict[Decimal, deque[Order]] = SortedDict()

    def add(self, order: Order) -> None:
        if order.side == Side.BUY:
            self._bids.setdefault(order.price, deque()).append(order) # type: ignore
        elif order.side == Side.SELL:
            self._asks.setdefault(order.price, deque()).append(order) # type: ignore
        self._index[order.id] = order

    def cancel(self, order_id: int) -> bool:
        if (order := self._index.get(order_id)) is None:
            return False
        assert order.price is not None, "Only limit orders rest in the book"
        if order.side == Side.BUY:
            self._bids[order.price].remove(order)
            if not self._bids[order.price]:
                del self._bids[order.price]
        elif order.side == Side.SELL:
            self._asks[order.price].remove(order)
            if not self._asks[order.price]:
                del self._asks[order.price]
        
        del self._index[order.id]
        order.status = OrderStatus.CANCELLED
        
        return True

    def snapshot(self, depth: int = 10) -> dict[str, list[tuple[Decimal, Decimal]]]:
        asks = []
        for price, level in self._asks.items():
            asks.append((price, sum(o.remaining for o in level)))
            if len(asks) == depth:
                break

        bids = []
        for price in reversed(self._bids.keys()):
            level = self._bids[price]
            bids.append((price, sum(o.remaining for o in level)))
            if len(bids) == depth:
                break

        return {
            "asks": asks,
            "bids": bids
        }

    def peek_best_ask(self) -> Order | None:
        if not self._asks:
            return None
        _, level = self._asks.peekitem(0) # type: ignore
        return level[0]

    def peek_best_bid(self) -> Order | None:
        if not self._bids:
            return None
        _, level = self._bids.peekitem(-1) # type: ignore
        return level[0]

    def pop_best_ask(self) -> Order | None:
        if not self._asks:
            return None
        _, level = self._asks.peekitem(0) # type: ignore

        order_to_pop = level.popleft()
        if not level:
            del self._asks[order_to_pop.price]
        del self._index[order_to_pop.id]

        return order_to_pop
    
    def pop_best_bid(self) -> Order | None:
        if not self._bids:
            return None
        _, level = self._bids.peekitem(-1) # type: ignore

        order_to_pop = level.popleft()
        if not level:
            del self._bids[order_to_pop.price]
        del self._index[order_to_pop.id]

        return order_to_pop