"""Paths, constants, and config for the Discovery, Query Generator, and
Prober pipeline."""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
BRANDS_DIR = DATA_DIR / "brands"
QUERIES_DIR = DATA_DIR / "queries"
QUERIES_FILE = QUERIES_DIR / "queries.json"
DB_PATH = DATA_DIR / "db" / "aivisibility.sqlite3"

# Pilot set for week 1 (docs/weeks/week1.md) — deliberately contrasting pair,
# enterprise vs SaaS/no-code. Expanding to the master plan's full list
# (Adyen, Checkout.com, Mollie) is just adding entries here, no code changes.
PILOT_BRANDS = [
    {"name": "Stripe", "url": "https://stripe.com"},
    {"name": "Paddle", "url": "https://paddle.com"},
]

INTENT_CATEGORIES = [
    "awareness",
    "comparison",
    "transactional",
    "use-case",
    "fees_pricing",
    "geography_coverage",
]

QUERIES_PER_CATEGORY = 2

# Safety cap on cost per query() call, so a bad prompt or a looping agent
# can't silently burn through the budget.
MAX_BUDGET_USD_PER_CALL = 0.50

# Pinned explicitly (not the CLI default) for week 2+: the Prober is a
# measurement instrument from here on, so the model must stay reproducible
# across runs. See docs/weeks/week2.md for the Claude Agent SDK caveat.
CLAUDE_MODEL = "claude-sonnet-5"

OPENAI_MODEL = "gpt-4o-mini"

# USD per 1M tokens. OpenAI's API doesn't return cost directly, so we compute
# it ourselves from token counts. Check https://openai.com/api/pricing/ and
# update this table by hand if OpenAI changes rates.
OPENAI_PRICING_PER_MTOK = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}
