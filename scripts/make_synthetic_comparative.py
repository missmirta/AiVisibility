"""Write synthetic comparative snippets: mild negative, neutral and recommended.

Run: uv run python scripts/make_synthetic_comparative.py [--seed 42]

The real classifier misses mild comparative negatives ("less feature-rich than X",
"no equivalent"). The older synthetic rows have no `neutral`, so this set adds all
three classes in the same comparative style: the model must see that a comparison
alone is not negative. Templates are hand-written; slots are filled from a fixed seed.
No API calls. The output is NOT merged into stance.csv automatically.
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.classifier.data import write_rows
from aivisibility.common import config

OUT_FILE = config.STANCE_LABELS_FILE.with_name("stance_synthetic_comparative.csv")
FIRST_ID = 300000

BRANDS = ["Stripe", "Paddle", "PayPal", "Adyen", "Lemon Squeezy", "Braintree", "Square", "Chargebee"]
FEATURES = [
    "subscription billing", "tax handling", "invoicing", "fraud tooling", "payouts to sellers",
    "local payment methods", "dunning and retries", "usage-based pricing", "reporting", "checkout customisation",
]
COUNTRIES = ["Ukraine", "Nigeria", "Belarus", "Pakistan", "Vietnam", "Egypt", "Kazakhstan", "Bangladesh"]
# {T} is the target brand, {O} a rival, {F} a feature, {C} a country
NEGATIVE = [
    # the target loses a comparison without any "bad" word
    "{O} is generally the better fit than {T} for {F}.",
    "For {F}, {O} is the stronger choice over {T}.",
    "Many larger teams prefer {O} to {T} because of {F}.",
    "{T} is almost always more expensive than {O} once you add {F}, and the gap grows with volume.",
    "Reasons some teams pick {O} over {T}: better {F}, lower fees and less setup.",
    "{O} handles {F} better than {T}, so {T} is the weaker option there.",
    "{T}'s rails are fine, but {O} is the one most teams end up choosing for {F}.",
    "If {F} is a priority, {O} is the better pick; {T} is a step behind.",
    # the target is not available or not supported
    "Short answer: {T} still does not support businesses registered in {C}; you cannot open a standard account.",
    "{T} is not available in {C}, so you cannot use its {F} there.",
    "As of my knowledge, {T} does not offer {F} for sellers in {C}, and this has not changed.",
    "{C} is not on {T}'s list of supported countries, so sign-up is not possible.",
    # mild negatives
    "{T} has no real equivalent to {O}'s {F}; you end up building that part yourself.",
    "{T} is a step behind {O} on {F}, which is the main reason some teams moved away.",
    "{T} does cover {F}, but it is noticeably weaker than {O}, so expect workarounds.",
]
NEUTRAL = [
    "{T} and {O} both support {F}, though they take different approaches to it.",
    "{T} handles {F} through its dashboard, while {O} exposes it mainly through the API.",
    "Both {T} and {O} offer {F}; the choice depends on where you sell and how you bill.",
    "{T} provides {F} in a similar way to {O}, and pricing for it is listed on their sites.",
    "{O} bundles {F} into its core plan, whereas {T} sells it as a separate module.",
    "For {F}, {T} uses its own terminology, which differs a little from {O}'s.",
    "{T} added {F} after {O} did, and both are documented in their public guides.",
    "{T} and {O} differ in how {F} is priced: {T} charges a percentage, {O} a flat fee.",
    "{T} is a payments provider that supports {F}; {O} is a comparable provider in the same space.",
    "{T} offers {F} in most regions, and {O} offers it in a similar set of countries.",
    "Teams comparing {T} with {O} usually look at {F}, fees and supported countries.",
    "{T} describes its {F} in the docs, and {O} publishes a similar overview.",
    "{T} lists {C} among its supported countries, and the payout options are described in the help centre.",
    "Whether {T} or {O} fits depends on your volume; both publish their fees for {F}.",
    "{O} is often mentioned next to {T} for {F}; the two work differently under the hood.",
]
RECOMMENDED = [
    "{T} is generally the better fit than {O} for {F}.",
    "For {F}, {T} is the stronger choice over {O}.",
    "{T} supports businesses registered in {C}, and {F} works out of the box.",
    "{T} is stronger than {O} on {F}, so it is the one I would pick for this.",
    "For {F}, {T} beats {O}: the setup is shorter and the defaults are sensible.",
    "{T} handles {F} better than {O}, which is why many teams choose it.",
    "{T} is the better fit than {O} if {F} matters, and it needs less custom code.",
    "Next to {O}, {T} gives you more out of the box for {F}; I would go with {T}.",
    "{T} has the edge over {O} on {F}, and the pricing is easier to predict.",
]


def build(seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows = []
    for label, templates, per_template in [("negative", NEGATIVE, 8), ("neutral", NEUTRAL, 8), ("recommended", RECOMMENDED, 8)]:
        for template in templates:
            seen = set()
            while len(seen) < per_template:
                target = rng.choice(BRANDS)
                rival = rng.choice([b for b in BRANDS if b != target])
                seen.add((target, rival, rng.choice(FEATURES), rng.choice(COUNTRIES)))
            for target, rival, feature, country in sorted(seen):
                body = template.format(T=target, O=rival, F=feature, C=country)
                rows.append({"text": f"[{target}] {body}", "label": label, "brand": target})
    rng.shuffle(rows)
    for i, row in enumerate(rows):
        row["response_id"] = str(FIRST_ID + i)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rows = build(args.seed)
    write_rows(OUT_FILE, rows, ["text", "label", "brand", "response_id"])
    counts = {lab: sum(r["label"] == lab for r in rows) for lab in config.STANCE_LABELS}
    print(f"wrote {len(rows)} rows to {OUT_FILE}: {counts}")


if __name__ == "__main__":
    main()
