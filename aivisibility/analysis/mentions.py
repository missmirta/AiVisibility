"""Brand mention detection: candidate dictionary + substring matching.

Method: case-sensitive whole-word substring search, no separate LLM call —
deliberately cheap and deterministic (see docs/weeks/week3.md). `Square` is
an ordinary English word, so a case-insensitive search would false-positive
on phrases like "a public square" or "square peg". Matching with the
original case (`Square`, not `square`) and word boundaries (`\\b`) avoids
that, at the cost of missing a rare mention spelled in lowercase — a
conscious trade-off, not an oversight.
"""

import json
import re

from ..common.config import BRANDS_DIR
from ..common.schemas import BrandProfile

METHOD = "substring_cs_v1"

_PAREN_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _strip_parenthetical(name: str) -> str:
    """"PayPal (Braintree)" -> "PayPal", so it collapses onto the plain
    "PayPal" candidate instead of being tracked as a separate entity."""
    return _PAREN_SUFFIX_RE.sub("", name).strip()


def load_brand_profiles() -> dict[str, BrandProfile]:
    """brand name (as used in `queries.brand`) -> BrandProfile, read from
    data/brands/*.json."""
    profiles: dict[str, BrandProfile] = {}
    for path in sorted(BRANDS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = BrandProfile.model_validate(data)
        profiles[profile.brand] = profile
    return profiles


def build_candidate_dictionary(profile: BrandProfile) -> list[str]:
    """{brand} ∪ {competitors}, deduplicated on a lowercased,
    parenthetical-stripped key so "PayPal (Braintree)" and "PayPal" collapse
    into one candidate — the first-seen original-case spelling is kept as
    the string actually matched against response text."""
    seen: dict[str, str] = {}
    for raw_name in [profile.brand, *profile.competitors]:
        canonical = _strip_parenthetical(raw_name)
        key = canonical.lower()
        seen.setdefault(key, canonical)
    return list(seen.values())


def detect_mentions(text: str, candidates: list[str]) -> list[str]:
    """Which candidates are present in `text` — case-sensitive, whole-word.
    Presence only (not occurrence count): at most one entry per candidate."""
    found = []
    for candidate in candidates:
        pattern = r"\b" + re.escape(candidate) + r"\b"
        if re.search(pattern, text):
            found.append(candidate)
    return found
