"""Cut short snippets around brand mentions: the unit that gets a stance label.

A whole answer often mentions several brands with different tone, so the label
belongs to one (brand, snippet) pair, not to the answer.
"""

import re
from dataclasses import dataclass

from aivisibility.common import db

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
MAX_SNIPPET_CHARS = 600


@dataclass
class Snippet:
    response_id: int
    brand: str
    text: str

    @property
    def model_input(self) -> str:
        """What the classifier sees: the brand tag plus its context."""
        return f"[{self.brand}] {self.text}"


def extract_snippet(text: str, brand: str, context: int = 1) -> str | None:
    """The sentence with the first whole-word `brand` match plus `context`
    sentences on each side, or None if the brand is absent."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text.replace("**", "")) if s.strip()]
    pattern = re.compile(r"\b" + re.escape(brand) + r"\b")
    for i, sentence in enumerate(sentences):
        if pattern.search(sentence):
            window = sentences[max(0, i - context) : i + context + 1]
            return " ".join(window)[:MAX_SNIPPET_CHARS]
    return None


def load_snippets() -> list[Snippet]:
    """One snippet per detected (response, brand) mention in the DB."""
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT m.response_id, m.brand_mentioned, r.raw_text
            FROM mentions m JOIN responses r ON r.id = m.response_id
            WHERE r.error IS NULL AND r.raw_text IS NOT NULL
            ORDER BY m.response_id, m.brand_mentioned
            """
        ).fetchall()
    snippets = []
    for row in rows:
        text = extract_snippet(row["raw_text"], row["brand_mentioned"])
        if text:
            snippets.append(Snippet(row["response_id"], row["brand_mentioned"], text))
    return snippets
