"""Query Generator: BrandProfile -> classified user queries per intent category."""

import json
import re

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from ..common.config import MAX_BUDGET_USD_PER_CALL, QUERIES_PER_CATEGORY
from ..common.schemas import BrandProfile, IntentCategory, Query

MAX_ATTEMPTS = 3

CATEGORY_GUIDANCE: dict[str, str] = {
    "awareness": "General questions about what the brand is, what it does, or how it works. Do not name any competitor.",
    "comparison": "Questions that explicitly compare the brand to one of its competitors. Each query must name at least one competitor by name.",
    "transactional": "Questions from someone close to signing up or "
    "integrating: pricing page, sign-up flow, account setup, API/SDK integration steps.",
    "use-case": "Questions framed around a specific scenario or use case asking whether/how the brand fits that scenario.",
    "fees_pricing": "Questions specifically about pricing plans, fees, hidden costs, or fee comparisons.",
    "geography_coverage": "Questions about which countries, regions, or currencies the brand supports, or whether it's available in a specific market.",
}

_PROMPT_TEMPLATE = """\
You are simulating real questions that potential customers type into a \
search engine or ask an AI assistant about the brand "{brand}".

Brand context:
- niche: {niche}
- competitors: {competitors}
- target audience: {target_audience}
- key use cases: {key_use_cases}

Generate exactly {n} realistic, distinct user questions of this type:
{category} — {guidance}

Style: informal, like something typed into Google, Reddit, or asked to an \
AI assistant — not marketing copy. Vary phrasing and length.{exclude_hint}

Return ONLY a JSON array of {n} strings, no surrounding text, no markdown \
fence, no numbering.
"""

_RETRY_SUFFIX = """

The previous attempt was not a valid JSON array of exactly {n} strings. \
Respond with STRICTLY a JSON array of {n} strings, no explanations, no \
markdown fence ```."""


def _extract_json_array(text: str) -> list[str]:
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text.strip()
    data = json.loads(candidate)
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("Expected a JSON array of strings")
    return data


async def _run_query(prompt: str) -> tuple[str, float | None]:
    options = ClaudeAgentOptions(
        tools=[],
        max_budget_usd=MAX_BUDGET_USD_PER_CALL,
    )
    result_text = ""
    cost_usd = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""
            cost_usd = message.total_cost_usd
    return result_text, cost_usd


def _build_prompt(
    profile: BrandProfile, category: str, n: int, existing: list[str]
) -> str:
    exclude_hint = ""
    if existing:
        joined = "; ".join(existing)
        exclude_hint = f" Do not repeat or rephrase any of these: {joined}."
    return _PROMPT_TEMPLATE.format(
        brand=profile.brand,
        niche=profile.niche,
        competitors=", ".join(profile.competitors),
        target_audience=profile.target_audience,
        key_use_cases=", ".join(profile.key_use_cases),
        n=n,
        category=category,
        guidance=CATEGORY_GUIDANCE[category],
        exclude_hint=exclude_hint,
    )


async def generate_category_queries(
    profile: BrandProfile, category: str, n: int = QUERIES_PER_CATEGORY
) -> tuple[list[str], float]:
    """Generate up to `n` deduplicated query texts for one intent category."""
    collected: list[str] = []
    seen: set[str] = set()
    total_cost = 0.0

    for attempt in range(1, MAX_ATTEMPTS + 1):
        missing = n - len(collected)
        if missing <= 0:
            break
        prompt = _build_prompt(profile, category, missing, collected)
        if attempt > 1:
            prompt += _RETRY_SUFFIX.format(n=missing)

        text, cost_usd = await _run_query(prompt)
        total_cost += cost_usd or 0.0
        print(
            f"  [query_gen:{profile.brand}:{category}] attempt {attempt}, "
            f"cost ~${cost_usd or 0:.4f}"
        )
        try:
            candidates = _extract_json_array(text)
        except (json.JSONDecodeError, ValueError):
            continue

        for candidate in candidates:
            key = candidate.strip().lower()
            if key and key not in seen:
                seen.add(key)
                collected.append(candidate.strip())

    return collected[:n], total_cost


def _mentions_competitors(text: str, competitors: list[str]) -> list[str]:
    lowered = text.lower()
    return [c for c in competitors if c.lower() in lowered]


async def generate_queries_for_brand(
    profile: BrandProfile, n_per_category: int = QUERIES_PER_CATEGORY
) -> tuple[list[Query], float]:
    """Generate the full query set (all intent categories) for one brand."""
    all_queries: list[Query] = []
    seen: set[str] = set()
    total_cost = 0.0

    for category in CATEGORY_GUIDANCE:
        texts, cost = await generate_category_queries(profile, category, n_per_category)
        total_cost += cost
        for text in texts:
            key = text.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            all_queries.append(
                Query(
                    text=text,
                    intent=category,  # type: ignore[arg-type]
                    brand=profile.brand,
                    mentions_competitors=_mentions_competitors(text, profile.competitors),
                )
            )

    return all_queries, total_cost


assert set(CATEGORY_GUIDANCE) == set(IntentCategory.__args__)  # keep in sync
