from app.engine.rust_engine import MatchingEngine


class EngineRegistry:
    def __init__(self):
        self._registry: dict[str, MatchingEngine] = dict()

    def get_engine(self, symbol: str) -> MatchingEngine:
        if symbol not in self._registry:
            self._registry[symbol] = MatchingEngine(symbol)
        return self._registry[symbol]
