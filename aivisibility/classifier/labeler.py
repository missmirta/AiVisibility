"""Label stance snippets with Claude (a "teacher"), in batches to keep cost low.

One call labels BATCH_SIZE snippets and returns JSON. Calls go through the
regular Claude prober, so retries and cost accounting are shared. Tests mock
`probe`; nothing here is called without an explicit budget (see
scripts/label_stance.py).
"""

import json
import re
from collections.abc import Awaitable, Callable

from aivisibility.common import config
from aivisibility.prober.base import ProbeResult

from .snippets import Snippet

BATCH_SIZE = 15

_PROMPT = """You label how ONE tagged brand is presented in a snippet of an AI assistant's answer.
The label is about the tagged brand only. Other brands in the snippet are context, not the target.

Labels:
- recommended: the text explicitly endorses the tagged brand - it advises choosing or using it,
  praises it, or says it fits the user's need or beats an alternative.
- neutral: the text only mentions, describes or explains the tagged brand (what it is,
  how it works, its prices) without praising it or showing it meets the user's need.
- negative: the text explicitly criticises the tagged brand, warns against it, names a drawback,
  or says another option is better than it.

Rules:
1. Praise or an advantage given to a DIFFERENT brand is NOT negative for the tagged brand by itself.
   "Paddle handles tax for you, unlike raw Stripe" describes how the products differ: neutral for
   Stripe. It is negative for Stripe only if the text says Stripe is worse, risky or unsuitable.
2. If the text shows the tagged brand meeting the user's stated need ("yes, Paddle handles VAT for
   your EU sales") or praises it ("strong support", "a great fit"), it is recommended, even without
   the words "choose it". A plain statement of what the brand is, offers or supports, with no praise
   and no link to the user's need ("Stripe is a payments platform with many features", "Stripe lets
   you get paid in EUR"), is neutral. A feature list is not an endorsement.
3. If the text says another brand is the better choice, cheaper or more suitable for the user,
   the tagged brand is negative.
4. In a comparison, the winner is recommended and the loser is negative only when the text
   says so. A balanced list of differences is neutral for both.
5. If the brand is only named in passing and nothing is said about it, choose neutral.
6. "There are reasons to consider X better for ..." or "X is stronger for large teams" counts as
   saying another option is better than the tagged brand (rule 3), so the tagged brand is negative.
   Mere "both are popular options" or "here are the differences" stays neutral.

Examples (brand | snippet -> label):
- Stripe | Paddle is a merchant of record, so unlike Stripe it files your sales tax for you. -> neutral
- Stripe | Stripe is a bad fit here: its fees are high and Paddle is cheaper for your volume. -> negative
- Paddle | Yes, Paddle handles VAT for EU buyers automatically, which covers your use case. -> recommended
- Paddle | Paddle is a merchant of record that sells software on your behalf. -> neutral
- Stripe | Stripe supports payouts in EUR and GBP depending on your account setup. -> neutral
- Adyen | Both Stripe and Adyen are well-known platforms; here is how they differ. -> neutral
- Stripe | Some teams find Adyen the better choice for large enterprises. -> negative
- PayPal | PayPal is worth it if your buyers already use PayPal, otherwise skip it. -> neutral
- Lemon Squeezy | For a solo creator selling ebooks, Lemon Squeezy is the simplest choice. -> recommended

Reply with ONLY a JSON list like [{{"id": 0, "label": "neutral"}}], one item per snippet.

Snippets:
{items}"""

Probe = Callable[[str], Awaitable[ProbeResult]]


def build_prompt(batch: list[Snippet]) -> str:
    items = "\n".join(f"{i}. brand={s.brand} | {s.text}" for i, s in enumerate(batch))
    return _PROMPT.format(items=items)


def parse_labels(text: str, n: int) -> dict[int, str]:
    """id -> label for valid items only; anything malformed is dropped."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return {}
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    out = {}
    for item in items:
        if isinstance(item, dict) and item.get("label") in config.STANCE_LABELS and item.get("id") in range(n):
            out[item["id"]] = item["label"]
    return out


async def label_snippets(
    snippets: list[Snippet],
    probe: Probe,
    max_budget_usd: float,
) -> tuple[list[tuple[Snippet, str]], float]:
    """Returns (labeled pairs, spent USD). Stops before a batch once the cap is reached."""
    labeled: list[tuple[Snippet, str]] = []
    spent = 0.0
    for start in range(0, len(snippets), BATCH_SIZE):
        if spent >= max_budget_usd:
            break
        batch = snippets[start : start + BATCH_SIZE]
        result = await probe(build_prompt(batch))
        spent += result.cost_usd or 0.0
        if result.error:
            continue
        for i, label in parse_labels(result.text, len(batch)).items():
            labeled.append((batch[i], label))
    return labeled, spent
