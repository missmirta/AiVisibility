"""Discovery Agent: brand name (+URL) -> BrandProfile (niche, competitors, target audience)."""

import json
import re

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import ValidationError

from ..common.config import MAX_BUDGET_USD_PER_CALL
from ..common.schemas import BrandProfile

MAX_ATTEMPTS = 3

_PROMPT_TEMPLATE = """\
Research the company "{brand}"{url_hint} using web search. Find:
- niche: which exact niche/segment of its market it operates in
  (1-2 sentences)
- competitors: a list of at least 2 and at most 5 closest competitors.
  Each entry must be the plain brand name exactly as people write it in
  text (e.g. "PayPal"), with no parentheses, parent company, product
  names or other annotations (not "PayPal (Braintree)")
- target_audience: who the main target customer is (1-2 sentences)
- key_use_cases: 2-4 typical usage scenarios

Return ONLY a JSON object with no surrounding text and no markdown fence,
in exactly this shape:
{{"niche": "...", "competitors": ["...", "..."], "target_audience": "...", "key_use_cases": ["...", "..."]}}
"""

_RETRY_SUFFIX = """

The previous attempt was not valid JSON. Respond with STRICTLY one JSON
object in the format above, no explanations, no markdown fence ```."""


def _extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text.strip()
    return json.loads(candidate)


async def _run_query(prompt: str) -> tuple[str, float | None]:
    options = ClaudeAgentOptions(
        tools=["WebSearch"],
        allowed_tools=["WebSearch"],
        max_budget_usd=MAX_BUDGET_USD_PER_CALL,
    )
    result_text = ""
    cost_usd = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""
            cost_usd = message.total_cost_usd
    return result_text, cost_usd


async def research_brand(name: str, url: str | None = None) -> BrandProfile:
    """Run the Discovery Agent for one brand. Raises ValueError once all
    attempts to get a valid result are exhausted."""
    url_hint = f" (website: {url})" if url else ""
    prompt = _PROMPT_TEMPLATE.format(brand=name, url_hint=url_hint)

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text, cost_usd = await _run_query(prompt)
        print(f"  [discovery:{name}] attempt {attempt}, cost ~${cost_usd or 0:.4f}")
        try:
            data = _extract_json(text)
            data["brand"] = name
            return BrandProfile.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            prompt = _PROMPT_TEMPLATE.format(brand=name, url_hint=url_hint) + _RETRY_SUFFIX

    raise ValueError(
        f"Discovery Agent failed to get a valid BrandProfile for '{name}' "
        f"after {MAX_ATTEMPTS} attempts: {last_error}"
    )
