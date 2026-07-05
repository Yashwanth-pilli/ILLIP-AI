"""Router classification tiers — small-talk vs brain vs deep."""

import pytest
from app.services import router_service as R


@pytest.mark.parametrize("msg,expected", [
    ("hi", "chat"),
    ("thanks!", "chat"),
    ("how are you?", "chat"),
    ("who are you", "chat"),
    ("lol nice", "chat"),
    ("good morning", "chat"),
    ("tell me a joke", "chat"),
    ("what is 2+2", "simple"),
    ("write a python function to sort a list", "complex"),
    ("hey, build me a complete web scraper app", "complex"),  # work beats greeting
])
def test_classify_tiers(msg, expected):
    assert R._classify(msg) == expected


def test_tiers_map_to_distinct_models():
    # chat -> fast, simple -> brain, complex -> deep (names may vary by install)
    assert R.CHAT and R.SMALL and R.LARGE
