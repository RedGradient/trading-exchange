from decimal import Decimal

import pytest

from app.engine.matching_engine import SymbolMismatchError
from helpers import filled_engine, make_order, empty_engine
from app.engine.models import OrderStatus, OrderType, Side


def test_place_limit_buy_matches_resting_ask() -> None:
    engine = filled_engine(
        asks=[("101", "2"), ("103", "2"), ("105", "1")],
    )
    order = make_order(side=Side.BUY, type=OrderType.LIMIT, price="105", quantity="5")
    trades = engine.place(order)

    assert len(trades) == 3

    assert trades[0].price == Decimal("101")
    assert trades[0].quantity == Decimal("2")

    assert trades[1].price == Decimal("103")
    assert trades[1].quantity == Decimal("2")

    assert trades[2].price == Decimal("105")
    assert trades[2].quantity == Decimal("1")

    assert order.status == OrderStatus.FILLED
    assert order.remaining == Decimal("0")
    assert engine._order_book.peek_best_ask() is None


def test_place_limit_sell_matches_resting_bid() -> None:
    engine = filled_engine(
        bids=[("99", "2"), ("95", "2"), ("90", "1")],
    )
    order = make_order(side=Side.SELL, type=OrderType.LIMIT, price="90", quantity="5")
    trades = engine.place(order)

    assert len(trades) == 3

    assert trades[0].price == Decimal("99")
    assert trades[0].quantity == Decimal("2")

    assert trades[1].price == Decimal("95")
    assert trades[1].quantity == Decimal("2")

    assert trades[2].price == Decimal("90")
    assert trades[2].quantity == Decimal("1")

    assert order.status == OrderStatus.FILLED
    assert order.remaining == Decimal("0")
    assert engine._order_book.peek_best_bid() is None


def test_place_market_buy_matches_resting_ask() -> None:
    engine = filled_engine(
        asks=[("101", "2"), ("103", "5"), ("105", "1")],
    )
    order = make_order(side=Side.BUY, type=OrderType.MARKET, price=None, quantity="5")
    trades = engine.place(order)

    assert len(trades) == 2

    assert trades[0].price == Decimal("101")
    assert trades[0].quantity == Decimal("2")

    assert trades[1].price == Decimal("103")
    assert trades[1].quantity == Decimal("3")

    assert order.status == OrderStatus.FILLED
    assert order.remaining == Decimal("0")
    assert engine._order_book.peek_best_ask() is not None


def test_place_market_sell_matches_resting_bid() -> None:
    engine = filled_engine(
        bids=[("99", "2"), ("95", "5"), ("90", "1")],
    )
    order = make_order(side=Side.SELL, type=OrderType.MARKET, price=None, quantity="5")
    trades = engine.place(order)

    assert len(trades) == 2

    assert trades[0].price == Decimal("99")
    assert trades[0].quantity == Decimal("2")

    assert trades[1].price == Decimal("95")
    assert trades[1].quantity == Decimal("3")

    assert order.status == OrderStatus.FILLED
    assert order.remaining == Decimal("0")
    assert engine._order_book.peek_best_bid() is not None


def test_filled_engine_has_resting_orders() -> None:
    engine = filled_engine(
        asks=[("101", "5")],
        bids=[("99", "2")],
    )
    book = engine._order_book

    assert book.peek_best_ask() is not None
    assert book.peek_best_bid() is not None
    assert book.peek_best_ask().price == Decimal("101") # type: ignore
    assert book.peek_best_bid().price == Decimal("99") # type: ignore


def test_symbol_mismatch_exception() -> None:
    engine = empty_engine(symbol="BTC-USD")
    order = make_order(symbol="BAD-SYMBOL")

    with pytest.raises(SymbolMismatchError):
        engine.place(order)


def test_limit_buy_empty_book_resting() -> None:
    engine = empty_engine()
    order = make_order(side=Side.BUY, type=OrderType.LIMIT, price="100", quantity="5")
    trades = engine.place(order)

    assert trades == []
    assert order.status == OrderStatus.OPEN
    assert order.remaining == Decimal("5")

    best_bid = engine._order_book.peek_best_bid()
    assert best_bid is not None
    assert best_bid.id == order.id
    assert best_bid.price == Decimal("100")


def test_limit_buy_price_does_not_cross() -> None:
    engine = filled_engine(asks=[("101", "5")])
    order = make_order(side=Side.BUY, type=OrderType.LIMIT, price="100", quantity="2")
    trades = engine.place(order)

    assert trades == []
    assert order.status == OrderStatus.OPEN

    best_bid = engine._order_book.peek_best_bid()
    assert best_bid is not None
    assert best_bid.price == Decimal("100")
    assert engine._order_book.peek_best_ask().price == Decimal("101") # type: ignore


def test_limit_buy_partial_fill_taker_rests() -> None:
    engine = filled_engine(asks=[("101", "3")])
    order = make_order(side=Side.BUY, type=OrderType.LIMIT, price="101", quantity="5")
    trades = engine.place(order)

    assert len(trades) == 1
    assert trades[0].quantity == Decimal("3")
    assert order.remaining == Decimal("2")
    assert order.status == OrderStatus.PARTIALLY_FILLED

    best_bid = engine._order_book.peek_best_bid()
    assert best_bid is not None
    assert best_bid.id == order.id
    assert best_bid.remaining == Decimal("2")


def test_limit_buy_partial_fill_maker_rests() -> None:
    engine = filled_engine(asks=[("101", "10")])
    order = make_order(side=Side.BUY, type=OrderType.LIMIT, price="101", quantity="3")
    trades = engine.place(order)

    assert len(trades) == 1
    assert trades[0].quantity == Decimal("3")

    best_ask = engine._order_book.peek_best_ask()
    assert best_ask is not None
    assert best_ask.remaining == Decimal("7")
    assert best_ask.status == OrderStatus.PARTIALLY_FILLED


def test_price_time_priority_fifo() -> None:
    engine = empty_engine()
    first = make_order(order_id=1, side=Side.SELL, price="101", quantity="3")
    second = make_order(order_id=2, side=Side.SELL, price="101", quantity="3")
    engine.place(first)
    engine.place(second)

    buy = make_order(order_id=3, side=Side.BUY, price="101", quantity="2")
    trades = engine.place(buy)

    assert len(trades) == 1
    assert trades[0].maker_order_id == 1
    assert first.remaining == Decimal("1")
    assert second.remaining == Decimal("3")


def test_market_buy_empty_book() -> None:
    engine = empty_engine()
    order = make_order(type=OrderType.MARKET, price=None, quantity="5")
    trades = engine.place(order)

    assert trades == []
    assert order.status == OrderStatus.CANCELLED
    assert order.remaining == Decimal("5")


def test_market_buy_partial_book_exhausted() -> None:
    engine = filled_engine(asks=[("101", "2"), ("103", "3")])
    order = make_order(type=OrderType.MARKET, price=None, quantity="10")
    trades = engine.place(order)

    assert len(trades) == 2
    assert trades[0].quantity == Decimal("2")
    assert trades[1].quantity == Decimal("3")
    assert order.remaining == Decimal("5")
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert engine._order_book.peek_best_ask() is None


def test_cancel_resting_order() -> None:
    engine = empty_engine()
    cancelled = make_order(order_id=10, side=Side.SELL, price="101", quantity="5")
    kept = make_order(order_id=11, side=Side.SELL, price="102", quantity="5")
    engine.place(cancelled)
    engine.place(kept)

    result = engine.cancel(10)
    assert result is not None
    assert result is cancelled
    assert cancelled.status == OrderStatus.CANCELLED

    buy = make_order(order_id=12, side=Side.BUY, price="102", quantity="5")
    trades = engine.place(buy)

    assert len(trades) == 1
    assert trades[0].price == Decimal("102")
    assert trades[0].maker_order_id == 11


def test_cancel_unknown_order() -> None:
    engine = empty_engine()
    assert engine.cancel(999) is None


def test_cancel_filled_order() -> None:
    engine = empty_engine()
    ask = make_order(order_id=1, side=Side.SELL, price="100", quantity="1")
    engine.place(ask)
    buy = make_order(order_id=2, side=Side.BUY, price="100", quantity="1")
    engine.place(buy)

    assert engine.cancel(1) is None


def test_deterministic_matching() -> None:
    def run():
        engine = empty_engine()
        engine.place(make_order(order_id=1, side=Side.SELL, price="100", quantity="5"))
        engine.place(make_order(order_id=2, side=Side.SELL, price="100", quantity="5"))
        taker = make_order(order_id=3, side=Side.BUY, price="100", quantity="3")
        trades = engine.place(taker)
        return [(t.maker_order_id, t.price, t.quantity) for t in trades]

    assert run() == run()
