import httpx
import pytest

from aivisibility.representativeness import collect
from aivisibility.representativeness.clean import clean, normalize
from aivisibility.representativeness.collect import RealQuery, collect_hn, collect_stackexchange


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(collect, "REQUEST_PAUSE_S", 0)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_collect_hn_parses_hits():
    def handler(request):
        assert request.url.params["query"] == "Stripe"
        return httpx.Response(200, json={"hits": [
            {"title": "Ask HN: Stripe or Paddle?", "objectID": "1", "created_at": "2024-01-01T00:00:00Z"},
            {"title": None, "objectID": "2"},
        ]})

    async with _client(handler) as client:
        got = await collect_hn(client, ["Stripe"])
    assert [q.text for q in got] == ["Ask HN: Stripe or Paddle?"]
    assert got[0].source == "hackernews" and got[0].url.endswith("id=1")


async def test_collect_stackexchange_unescapes_and_converts_date():
    def handler(request):
        return httpx.Response(200, json={"items": [
            {"title": "How to use Stripe &amp; webhooks?", "link": "https://so/q/1", "creation_date": 1700000000},
        ]})

    async with _client(handler) as client:
        got = await collect_stackexchange(client, ["Stripe"])
    assert got[0].text == "How to use Stripe & webhooks?"
    assert got[0].created_at.startswith("2023-11-14")


async def test_http_error_is_retried_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"hits": []})

    async with _client(handler) as client:
        assert await collect_hn(client, ["x"]) == []
    assert calls["n"] == 2


def _q(text: str) -> RealQuery:
    return RealQuery(text=text, source="hackernews", url="u", created_at="")


def test_clean_filters_each_stage():
    kept, counts = clean([
        _q("Ask HN: Which is better for SaaS, Stripe or Paddle?"),
        _q("Which is better for SaaS, Stripe or Paddle?!"),  # duplicate after normalizing
        _q("Show HN: My Stripe dashboard"),  # skipped
        _q("Stripe raises new funding round"),  # on topic, not a question
        _q("How do I bake bread at home?"),  # off topic
        _q("Why?"),  # too short
    ])
    assert [q.text for q in kept] == ["Which is better for SaaS, Stripe or Paddle?"]
    assert counts == {"collected": 6, "length_ok": 4, "unique": 3, "on_topic": 2, "question_like": 1}


def test_normalize_ignores_case_and_punctuation():
    assert normalize("Stripe vs. Paddle?") == normalize("stripe vs paddle")


def test_ambiguous_brand_needs_payment_context():
    kept, _ = clean([
        _q("Why are black students being paddled more in schools?"),
        _q("How do I fix a paddle collision bug in my Pong game?"),
        _q("Anyone using Paddle as a payment provider?"),
    ])
    assert [q.text for q in kept] == ["Anyone using Paddle as a payment provider?"]
