"""Brand masking: hide brand names so the model learns stance, not brand identity.

Input is a snippet in the form "[Brand] text". The target brand becomes
TARGETBRAND and every other known brand becomes OTHERBRAND, so the model can
tell "praise for the target" from "praise for a rival".
"""

import re
from functools import cache

from aivisibility.common import config

TARGET_TOKEN = "TARGETBRAND"
OTHER_TOKEN = "OTHERBRAND"

_PREFIX = re.compile(r"^\[([^\]]+)\]\s*")


def _pattern(names: tuple[str, ...]) -> re.Pattern[str] | None:
    if not names:
        return None
    # Longest first, so "Lemon Squeezy" wins over a shorter overlapping name.
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


@cache
def _compiled(names: tuple[str, ...]) -> re.Pattern[str] | None:
    return _pattern(names)


def mask_brands(text: str, known_brands: list[str] | None = None) -> str:
    """Replace the target brand (from the "[Brand]" prefix) and other known brands."""
    known = tuple(known_brands if known_brands is not None else config.STANCE_KNOWN_BRANDS)
    match = _PREFIX.match(text)
    if not match:
        # No prefix: no target, so every brand counts as "other".
        pattern = _compiled(known)
        return pattern.sub(OTHER_TOKEN, text) if pattern else text

    target, body = match.group(1), text[match.end() :]
    target_pattern = _compiled((target,))
    body = target_pattern.sub(TARGET_TOKEN, body)
    others = tuple(b for b in known if b.lower() != target.lower())
    other_pattern = _compiled(others)
    if other_pattern:
        body = other_pattern.sub(OTHER_TOKEN, body)
    return f"{TARGET_TOKEN} {body}"


def mask_all(texts: list[str]) -> list[str]:
    return [mask_brands(t) for t in texts]
