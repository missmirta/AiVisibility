"""Build the grid of pairwise comparisons (no API calls).

Every (pair, attribute, context, repeat) cell is asked in both orders, so
position bias can be measured and cancelled out.
"""

from dataclasses import dataclass
from itertools import combinations

from ..common.config import (
    PERCEPTION_ATTRIBUTES,
    PERCEPTION_BRANDS,
    PERCEPTION_CONTEXTS,
    PERCEPTION_REPEATS,
)

PROMPT_TEMPLATE = (
    "Consider two payment providers for {context}.\n"
    "A: {first}\n"
    "B: {second}\n"
    "Which one is {criterion}? Answer with exactly one letter: A or B."
)


@dataclass(frozen=True)
class Comparison:
    first: str  # brand shown as option A
    second: str  # brand shown as option B
    attribute: str
    context: str
    repeat: int
    prompt: str

    def winner(self, choice: str | None) -> str | None:
        """Map the parsed letter back to a brand name."""
        if choice == "A":
            return self.first
        if choice == "B":
            return self.second
        return None


def build_comparisons(
    brands: list[str] = PERCEPTION_BRANDS,
    attributes: dict[str, str] = PERCEPTION_ATTRIBUTES,
    contexts: list[str] = PERCEPTION_CONTEXTS,
    n_repeats: int = PERCEPTION_REPEATS,
) -> list[Comparison]:
    out = []
    for a, b in combinations(brands, 2):
        for attribute, criterion in attributes.items():
            for context in contexts:
                for repeat in range(n_repeats):
                    for first, second in ((a, b), (b, a)):
                        prompt = PROMPT_TEMPLATE.format(
                            context=context, first=first, second=second, criterion=criterion
                        )
                        out.append(Comparison(first, second, attribute, context, repeat, prompt))
    return out
