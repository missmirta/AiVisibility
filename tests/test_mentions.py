import pytest

from aivisibility.analysis.mentions import build_candidate_dictionary, detect_mentions
from aivisibility.common.schemas import BrandProfile


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Stripe is great", ["Stripe"]),
        ("I use stripe", []),  # case-sensitive
        ("Striped shirts", []),  # whole-word only
        ("Stripe and Paddle", ["Stripe", "Paddle"]),
        ("Stripe Stripe Stripe", ["Stripe"]),  # presence, not count
        ("", []),
    ],
)
def test_detect_mentions(text, expected):
    assert detect_mentions(text, ["Stripe", "Paddle"]) == expected


def test_detect_mentions_escapes_regex_chars():
    assert detect_mentions("Try C++ today", ["C++"]) == []  # \b before '+' never matches
    assert detect_mentions("Try Pay.com now", ["Pay.com"]) == ["Pay.com"]
    assert detect_mentions("Try PayXcom now", ["Pay.com"]) == []


def test_candidate_dictionary_dedupes_case_insensitively():
    profile = BrandProfile.model_construct(brand="Stripe", competitors=["stripe", " Paddle ", "Paddle"])
    assert build_candidate_dictionary(profile) == ["Stripe", "Paddle"]
