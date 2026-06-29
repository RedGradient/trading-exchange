from app.engine.matching_engine import MatchingEngine
from app.engine.order_book import OrderBook


class EngineRegistry:
    def __init__(self):
        self._registry: dict[str, MatchingEngine] = dict()

    def get_engine(self, symbol: str) -> MatchingEngine:
        if symbol not in self._registry:
            self._registry[symbol] = MatchingEngine(symbol, OrderBook())
        return self._registry[symbol]