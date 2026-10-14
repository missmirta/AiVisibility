"""Clean and filter collected questions: dedupe, drop noise, keep payment-provider questions."""

import re

from aivisibility.common import config

from .collect import RealQuery

MIN_LEN, MAX_LEN = 15, 200

# A title is on-topic if it names a known brand or one of these payment phrases.
TOPIC_KEYWORDS = [
    "payment", "billing", "merchant of record", "checkout", "subscription", "invoice", "payout", "paypal",
    "gateway", "processor", "psp", "vat", "sales tax",
]
# ...and question-like if it asks, compares or looks for something.
QUESTION_RE = re.compile(
    r"\?|^(how|what|which|why|should|can|is|are|does|do|any|best|looking for|recommend)\b"
    r"|\bvs\.?\b|\balternatives?\b|\bcompare\b",
    re.IGNORECASE,
)
PREFIX_RE = re.compile(r"^(ask hn|tell hn)\s*:\s*", re.IGNORECASE)
SKIP_RE = re.compile(r"^show hn\s*:", re.IGNORECASE)


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


# Everyday words that are also brand names: they count only with a payment keyword next to them.
AMBIGUOUS_BRANDS = {"paddle", "square"}


def _on_topic(text: str) -> bool:
    low = text.lower()
    has_keyword = any(k in low for k in TOPIC_KEYWORDS)
    brands = [b.lower() for b in config.STANCE_KNOWN_BRANDS if b.lower() not in AMBIGUOUS_BRANDS]
    named_brand = any(re.search(rf"\b{re.escape(b)}\b", low) for b in brands)
    return named_brand or has_keyword


def clean(queries: list[RealQuery]) -> tuple[list[RealQuery], dict[str, int]]:
    """Return kept queries plus counts after each filter stage (for the report)."""
    counts = {"collected": len(queries)}
    stage = [q for q in queries if not SKIP_RE.match(q.text)]
    stage = [q.model_copy(update={"text": PREFIX_RE.sub("", q.text).strip()}) for q in stage]
    stage = [q for q in stage if MIN_LEN <= len(q.text) <= MAX_LEN]
    counts["length_ok"] = len(stage)

    seen: set[str] = set()
    unique: list[RealQuery] = []
    for q in stage:
        key = normalize(q.text)
        if key not in seen:
            seen.add(key)
            unique.append(q)
    counts["unique"] = len(unique)

    topical = [q for q in unique if _on_topic(q.text)]
    counts["on_topic"] = len(topical)
    kept = [q for q in topical if QUESTION_RE.search(q.text)]
    counts["question_like"] = len(kept)
    return kept, counts
