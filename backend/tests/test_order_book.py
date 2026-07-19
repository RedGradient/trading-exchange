from decimal import Decimal

import pytest

from app.engine.models import OrderStatus, Side
from app.engine.order_book import OrderBook
from helpers import make_order


@pytest.fixture
def book() -> OrderBook:
    return OrderBook()


def test_add_places_buy_on_bid_side(book: OrderBook) -> None:
    order = make_order(order_id=1, side=Side.BUY, price="99", quantity="3")
    book.add(order)

    best_bid = book.peek_best_bid()
    assert best_bid is order
    assert book.peek_best_ask() is None


def test_add_places_sell_on_ask_side(book: OrderBook) -> None:
    order = make_order(order_id=1, side=Side.SELL, price="101", quantity="3")
    book.add(order)

    best_ask = book.peek_best_ask()
    assert best_ask is order
    assert book.peek_best_bid() is None


def test_add_queues_orders_at_same_price_fifo(book: OrderBook) -> None:
    first = make_order(order_id=1, side=Side.SELL, price="101", quantity="1")
    second = make_order(order_id=2, side=Side.SELL, price="101", quantity="2")
    book.add(first)
    book.add(second)

    assert book.peek_best_ask() is first


def test_cancel_removes_buy_order(book: OrderBook) -> None:
    order = make_order(order_id=1, side=Side.BUY, price="99", quantity="3")
    book.add(order)

    result = book.cancel(1)
    assert result is not None
    assert result is order
    assert order.status == OrderStatus.CANCELLED
    assert book.peek_best_bid() is None


def test_cancel_removes_sell_order(book: OrderBook) -> None:
    order = make_order(order_id=1, side=Side.SELL, price="101", quantity="3")
    book.add(order)

    result = book.cancel(1)
    assert result is not None
    assert result is order
    assert order.status == OrderStatus.CANCELLED
    assert book.peek_best_ask() is None


def test_cancel_removes_empty_price_level(book: OrderBook) -> None:
    """After canceling the last order at a price level, no empty deque should remain."""

    order = make_order(order_id=1, side=Side.SELL, price="101", quantity="3")
    book.add(order)

    book.cancel(1)

    assert book.snapshot() == {"asks": [], "bids": []}


def test_cancel_unknown_order_returns_none(book: OrderBook) -> None:
    assert book.cancel(999) is None


def test_snapshot_aggregates_levels() -> None:
    book = OrderBook()
    for price, qty in [
        ("101", "1"),
        ("102", "2"),
        ("103", "3"),
        ("104", "4"),
        ("105", "5"),
        ("106", "6"),
        ("107", "7"),
        ("108", "8"),
    ]:
        book.add(
            make_order(order_id=int(price), side=Side.SELL, price=price, quantity=qty)
        )

    for price, qty in [("99", "1"), ("98", "2"), ("97", "3"), ("96", "4")]:
        book.add(
            make_order(
                order_id=200 + int(price),
                side=Side.BUY,
                price=price,
                quantity=qty,
            )
        )

    snapshot = book.snapshot(depth=6)

    assert snapshot["asks"] == [
        (Decimal("101"), Decimal("1")),
        (Decimal("102"), Decimal("2")),
        (Decimal("103"), Decimal("3")),
        (Decimal("104"), Decimal("4")),
        (Decimal("105"), Decimal("5")),
        (Decimal("106"), Decimal("6")),
    ]
    assert snapshot["bids"] == [
        (Decimal("99"), Decimal("1")),
        (Decimal("98"), Decimal("2")),
        (Decimal("97"), Decimal("3")),
        (Decimal("96"), Decimal("4")),
    ]


def test_peek_best_ask_empty(book: OrderBook) -> None:
    assert book.peek_best_ask() is None


def test_peek_best_ask_returns_cheapest_order(book: OrderBook) -> None:
    book.add(make_order(order_id=1, side=Side.SELL, price="103", quantity="1"))
    cheapest = make_order(order_id=2, side=Side.SELL, price="101", quantity="2")
    book.add(cheapest)

    assert book.peek_best_ask() is cheapest


def test_peek_best_bid_empty(book: OrderBook) -> None:
    assert book.peek_best_bid() is None


def test_peek_best_bid_returns_highest_order(book: OrderBook) -> None:
    book.add(make_order(order_id=1, side=Side.BUY, price="97", quantity="1"))
    highest = make_order(order_id=2, side=Side.BUY, price="99", quantity="2")
    book.add(highest)

    assert book.peek_best_bid() is highest


def test_pop_best_ask_empty(book: OrderBook) -> None:
    assert book.pop_best_ask() is None


def test_pop_best_ask_removes_order_and_clears_level(book: OrderBook) -> None:
    order = make_order(order_id=1, side=Side.SELL, price="101", quantity="3")
    book.add(order)

    popped = book.pop_best_ask()

    assert popped is order
    assert book.peek_best_ask() is None
    assert book.cancel(1) is None


def test_pop_best_ask_keeps_remaining_orders_at_level(book: OrderBook) -> None:
    first = make_order(order_id=1, side=Side.SELL, price="101", quantity="1")
    second = make_order(order_id=2, side=Side.SELL, price="101", quantity="2")
    book.add(first)
    book.add(second)

    assert book.pop_best_ask() is first
    assert book.peek_best_ask() is second


def test_pop_best_bid_empty(book: OrderBook) -> None:
    assert book.pop_best_bid() is None


def test_pop_best_bid_removes_order_and_clears_level(book: OrderBook) -> None:
    order = make_order(order_id=1, side=Side.BUY, price="99", quantity="3")
    book.add(order)

    popped = book.pop_best_bid()

    assert popped is order
    assert book.peek_best_bid() is None
    assert book.cancel(1) is None


def test_pop_best_bid_keeps_remaining_orders_at_level(book: OrderBook) -> None:
    first = make_order(order_id=1, side=Side.BUY, price="99", quantity="1")
    second = make_order(order_id=2, side=Side.BUY, price="99", quantity="2")
    book.add(first)
    book.add(second)

    assert book.pop_best_bid() is first
    assert book.peek_best_bid() is second
