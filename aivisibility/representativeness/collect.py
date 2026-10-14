"""Collect real payment-provider questions from free public APIs (no keys, no LLM calls)."""

import asyncio
import html
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel

from aivisibility.prober.retry import with_retry

HN_URL = "https://hn.algolia.com/api/v1/search"
SE_URL = "https://api.stackexchange.com/2.3/search/advanced"

# Search terms sent to both sources; the filter in clean.py drops what is off-topic.
SEARCH_TERMS = [
    "Stripe", "Paddle", "Lemon Squeezy", "PayPal alternative", "Adyen", "Braintree",
    "Checkout.com", "Mollie", "merchant of record", "payment gateway", "payment provider",
    "payment processor", "subscription billing", "accept payments SaaS",
]

REQUEST_PAUSE_S = 0.5  # polite delay between calls


class RealQuery(BaseModel):
    text: str
    source: str  # "hackernews" | "stackoverflow"
    url: str
    created_at: str  # ISO 8601, UTC


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> dict:
    async def call() -> dict:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    await asyncio.sleep(REQUEST_PAUSE_S)
    return await with_retry(
        call, base_delay=REQUEST_PAUSE_S * 2, retry_on=(httpx.TransportError, httpx.HTTPStatusError)
    )


async def collect_hn(client: httpx.AsyncClient, terms: list[str], per_term: int = 100) -> list[RealQuery]:
    """Hacker News titles (stories and Ask HN) matching each term."""
    out: list[RealQuery] = []
    for term in terms:
        data = await _get_json(client, HN_URL, {"query": term, "tags": "story", "hitsPerPage": per_term})
        for hit in data.get("hits", []):
            title = (hit.get("title") or "").strip()
            if not title:
                continue
            out.append(
                RealQuery(
                    text=title,
                    source="hackernews",
                    url=f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    created_at=hit.get("created_at", ""),
                )
            )
    return out


async def collect_stackexchange(
    client: httpx.AsyncClient, terms: list[str], per_term: int = 100
) -> list[RealQuery]:
    """Stack Overflow question titles matching each term."""
    out: list[RealQuery] = []
    for term in terms:
        params = {"q": term, "site": "stackoverflow", "order": "desc", "sort": "relevance", "pagesize": per_term}
        data = await _get_json(client, SE_URL, params)
        for item in data.get("items", []):
            title = html.unescape(item.get("title", "")).strip()
            if not title:
                continue
            created = datetime.fromtimestamp(item.get("creation_date", 0), tz=UTC).isoformat()
            out.append(RealQuery(text=title, source="stackoverflow", url=item.get("link", ""), created_at=created))
    return out
