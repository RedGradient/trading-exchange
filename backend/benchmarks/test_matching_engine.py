from decimal import Decimal

import pytest

from app.engine.models import Order, OrderStatus, OrderType, Side


def _place(engine, order):
    return engine.place(order)


def _cancel(engine, order_id):
    return engine.cancel(order_id)


def test_place_throughput(benchmark, engine_factory):
    pair_count = 5_000
    symbol = "BENCHMARK"
    quantity = Decimal("1")
    ask_price = Decimal("101")

    def setup():
        engine = engine_factory(symbol)
        orders = []

        for index in range(pair_count):
            orders.append(
                Order(
                    id=2 * index + 1,
                    symbol=symbol,
                    side=Side.SELL,
                    type=OrderType.LIMIT,
                    price=ask_price,
                    quantity=quantity,
                    remaining=quantity,
                    status=OrderStatus.OPEN,
                    sequence=0,
                )
            )
            orders.append(
                Order(
                    id=2 * index + 2,
                    symbol=symbol,
                    side=Side.BUY,
                    type=OrderType.MARKET,
                    price=None,
                    quantity=quantity,
                    remaining=quantity,
                    status=OrderStatus.OPEN,
                    sequence=0,
                )
            )

        return (engine, orders), {}

    def replay(engine, orders):
        for order in orders:
            engine.place(order)

    benchmark.pedantic(
        replay,
        setup=setup,
        rounds=20,
        warmup_rounds=3,
    )


@pytest.mark.parametrize("maker_count", [10, 100, 1_000])
@pytest.mark.parametrize("price_step", [0, 1], ids=["one-level", "many-levels"])
def test_market_buy_sweep(benchmark, engine_factory, maker_count, price_step):
    symbol = "BENCHMARK"
    maker_quantity = Decimal("1")
    taker_quantity = Decimal(maker_count)
    prices = [Decimal(101 + index * price_step) for index in range(maker_count)]

    def setup():
        engine = engine_factory(symbol)
        for order_id, price in enumerate(prices, start=1):
            engine.place(
                Order(
                    id=order_id,
                    symbol=symbol,
                    side=Side.SELL,
                    type=OrderType.LIMIT,
                    price=price,
                    quantity=maker_quantity,
                    remaining=maker_quantity,
                    status=OrderStatus.OPEN,
                    sequence=0,
                )
            )

        taker = Order(
            id=maker_count + 1,
            symbol=symbol,
            side=Side.BUY,
            type=OrderType.MARKET,
            price=None,
            quantity=taker_quantity,
            remaining=taker_quantity,
            status=OrderStatus.OPEN,
            sequence=0,
        )
        return (engine, taker), {}

    benchmark.pedantic(
        _place,
        setup=setup,
        rounds=20,
        warmup_rounds=3,
    )


def _limit_order(order_id, side, price):
    quantity = Decimal("1")
    return Order(
        id=order_id,
        symbol="BENCHMARK",
        side=side,
        type=OrderType.LIMIT,
        price=price,
        quantity=quantity,
        remaining=quantity,
        status=OrderStatus.OPEN,
        sequence=0,
    )


def _populated_engine(engine_factory, level_count, orders_per_level):
    engine = engine_factory("BENCHMARK")
    order_id = 1
    for side, best_price, step in [(Side.BUY, 10_000, -1), (Side.SELL, 10_002, 1)]:
        for level in range(level_count):
            price = Decimal(best_price + step * level)
            for _ in range(orders_per_level):
                engine.place(_limit_order(order_id, side, price))
                order_id += 1
    return engine


@pytest.mark.parametrize("level_count", [10, 100, 1_000])
@pytest.mark.parametrize("price", [10_000, 10_001], ids=["existing-level", "new-level"])
def test_limit_buy_without_trade(benchmark, engine_factory, level_count, price):
    bid_price = Decimal(price)

    def setup():
        engine = _populated_engine(engine_factory, level_count, orders_per_level=1)
        order = _limit_order(2 * level_count + 1, Side.BUY, bid_price)
        return (engine, order), {}

    benchmark.pedantic(
        _place,
        setup=setup,
        rounds=20,
        warmup_rounds=3,
    )


@pytest.mark.parametrize("order_id", [1, 501, 1_000], ids=["first", "middle", "last"])
def test_cancel_in_long_queue(benchmark, engine_factory, order_id):
    queue_size = 1_000
    price = Decimal("101")

    def setup():
        engine = engine_factory("BENCHMARK")
        for resting_id in range(1, queue_size + 1):
            engine.place(_limit_order(resting_id, Side.SELL, price))
        return (engine, order_id), {}

    benchmark.pedantic(
        _cancel,
        setup=setup,
        rounds=20,
        warmup_rounds=3,
    )


@pytest.mark.parametrize("depth", [10, 50])
@pytest.mark.parametrize("orders_per_level", [1, 10, 100])
def test_order_book_snapshot(benchmark, engine_factory, depth, orders_per_level):
    engine = _populated_engine(
        engine_factory, level_count=100, orders_per_level=orders_per_level
    )
    benchmark(engine.snapshot, depth)
