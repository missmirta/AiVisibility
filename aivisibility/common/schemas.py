"""Pydantic schemas for brand profiles and queries."""

from typing import Literal

from pydantic import BaseModel, Field

from .config import INTENT_CATEGORIES

IntentCategory = Literal[
    "awareness",
    "comparison",
    "transactional",
    "use-case",
    "fees_pricing",
    "geography_coverage",
]


class BrandProfile(BaseModel):
    """Discovery Agent output — confirmed by a human before use."""

    brand: str
    niche: str = Field(min_length=1)
    competitors: list[str] = Field(min_length=2)
    target_audience: str = Field(min_length=1)
    key_use_cases: list[str] = Field(default_factory=list)


class Query(BaseModel):
    """One generated query for the Query Generator (day 2)."""

    text: str = Field(min_length=1)
    intent: IntentCategory
    brand: str
    mentions_competitors: list[str] = Field(default_factory=list)


assert set(IntentCategory.__args__) == set(INTENT_CATEGORIES)  # keep in sync
