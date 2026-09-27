"""Paths, constants, and config for week 1 (Discovery + Query Generator)."""

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
BRANDS_DIR = DATA_DIR / "brands"
QUERIES_DIR = DATA_DIR / "queries"
QUERIES_FILE = QUERIES_DIR / "queries.json"

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
