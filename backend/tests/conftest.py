import pytest

from helpers import (
    empty_engine, 
    filled_engine as build_filled_engine
)


@pytest.fixture
def engine():
    return empty_engine()


@pytest.fixture
def filled_engine():
    return build_filled_engine(
        asks=[
            ("101", "5"),
            ("102", "8"),
            ("103", "12"),
            ("104", "6"),
            ("105", "15"),
        ],
        bids=[
            ("99", "4"),
            ("98", "10"),
            ("97", "7"),
            ("96", "20"),
            ("95", "3"),
        ],
    )
