import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the --engine option for selecting benchmark implementations.

    Example (from /backend directory):
        python -m pytest benchmarks/ --benchmark-only --engine=all
    """
    parser.addoption(
        "--engine",
        choices=("rust", "python", "all"),
        default="rust",
        help="Matching engine for benchmarks (default: rust).",
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Read --engine parameter and pass the selected implementations to the engine_factory fixture."""
    if "engine_factory" in metafunc.fixturenames:
        selected = metafunc.config.getoption("--engine")
        engines = ["python", "rust"] if selected == "all" else [selected]
        metafunc.parametrize("engine_factory", engines, indirect=True, ids=engines)


@pytest.fixture
def engine_factory(request: pytest.FixtureRequest):
    if request.param == "python":
        from app.engine.matching_engine import MatchingEngine
        from app.engine.order_book import OrderBook

        return lambda symbol: MatchingEngine(symbol, OrderBook())

    from app.engine.rust_engine import MatchingEngine

    return MatchingEngine
