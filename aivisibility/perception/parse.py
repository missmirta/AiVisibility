"""Parse a one-letter A/B answer from a model reply."""

import re

_ANSWER = re.compile(r"^\W*(?:answer\W*)?(?:option\W*)?([AB])\b", re.IGNORECASE)


def parse_choice(text: str | None) -> str | None:
    """Return "A" or "B", or None for a refusal, a long reply or a mixed answer."""
    if not text:
        return None
    text = text.strip()
    match = _ANSWER.match(text)
    if not match:
        return None
    # "A or B", "A/B" and similar are not a decision.
    rest = text[match.end():]
    if re.match(r"\s*(?:or|/|and)\s*[AB]\b", rest, re.IGNORECASE):
        return None
    # "A great question..." is prose, not an answer: after the letter only end or punctuation may follow.
    if rest.strip() and rest[0] not in ".,:;)!*":
        return None
    return match.group(1).upper()
