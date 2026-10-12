from aivisibility.classifier.labeler import BATCH_SIZE, build_prompt, label_snippets, parse_labels
from aivisibility.classifier.snippets import Snippet, extract_snippet
from aivisibility.prober.base import ProbeResult

TEXT = "Intro line. Stripe is great for startups. It has a clean API. Other tools exist. Last one."


def test_extract_snippet_takes_neighbouring_sentences():
    snippet = extract_snippet(TEXT, "Stripe")
    assert snippet == "Intro line. Stripe is great for startups. It has a clean API."


def test_extract_snippet_missing_brand():
    assert extract_snippet(TEXT, "Paddle") is None


def test_extract_snippet_is_whole_word_and_case_sensitive():
    assert extract_snippet("A public square. Squarespace sells sites.", "Square") is None


def test_parse_labels_keeps_only_valid_items():
    text = 'Sure! [{"id": 0, "label": "recommended"}, {"id": 1, "label": "love"}, {"id": 9, "label": "neutral"}]'
    assert parse_labels(text, n=2) == {0: "recommended"}


def test_parse_labels_garbage():
    assert parse_labels("no json here", n=3) == {}
    assert parse_labels("[not json]", n=3) == {}


def _result(text: str, cost: float, error: str | None = None) -> ProbeResult:
    return ProbeResult(text, None, None, cost, 1, "mock", error)


def _snippets(n: int) -> list[Snippet]:
    return [Snippet(i, "Stripe", f"Stripe sentence {i}.") for i in range(n)]


async def test_label_snippets_maps_ids_back_to_snippets():
    async def probe(prompt: str) -> ProbeResult:
        return _result('[{"id": 0, "label": "negative"}, {"id": 1, "label": "neutral"}]', 0.01)

    labeled, spent = await label_snippets(_snippets(2), probe, max_budget_usd=1.0)
    assert [(s.response_id, label) for s, label in labeled] == [(0, "negative"), (1, "neutral")]
    assert spent == 0.01


async def test_label_snippets_stops_at_budget():
    calls = []

    async def probe(prompt: str) -> ProbeResult:
        calls.append(prompt)
        return _result("[]", 0.5)

    await label_snippets(_snippets(BATCH_SIZE * 5), probe, max_budget_usd=1.0)
    assert len(calls) == 2


async def test_label_snippets_skips_errored_batch():
    async def probe(prompt: str) -> ProbeResult:
        return _result("", 0.0, error="boom")

    labeled, _ = await label_snippets(_snippets(3), probe, max_budget_usd=1.0)
    assert labeled == []


def test_prompt_lists_every_snippet():
    prompt = build_prompt(_snippets(3))
    assert "0. brand=Stripe" in prompt and "2. brand=Stripe" in prompt
