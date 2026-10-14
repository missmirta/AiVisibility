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
# {T} is the target brand, {O} a rival, {F} a feature
NEGATIVE = [
    "{T} is less feature-rich than {O} when it comes to {F}, so teams that depend on it often add another tool.",
    "{T} has no real equivalent to {O}'s {F}; you end up building that part yourself.",
    "Compared with {O}, {T} feels older and its {F} is clunkier to set up.",
    "{T} is a step behind {O} on {F}, which is the main reason some teams moved away.",
    "{T} works, but {O} handles {F} more cleanly and with less custom code.",
    "{T} is the more expensive option next to {O}, and you get little extra for the {F} you pay for.",
    "{T} is only worth it if you can live with limited {F}; otherwise {O} is the better fit.",
    "On {F}, {T} trails {O}, and the gap shows once volume grows.",
    "{T} lacks the {F} depth that {O} offers, so it suits only simple setups.",
    "Support for {F} in {T} is thinner than in {O}, which can become a blocker for larger teams.",
    "Many teams find {T}'s {F} harder to configure than {O}'s, and the docs do not close that gap.",
    "{T} does cover {F}, but it is noticeably weaker than {O}, so expect workarounds.",
    "If {F} matters to you, {T} is not the strongest choice; {O} does it better.",
    "{T} costs more per transaction than {O} and does not make up for it on {F}.",
    "Unlike {O}, {T} offers no built-in {F}, so you need a third-party add-on.",
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
]
RECOMMENDED = [
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
                seen.add((target, rival, rng.choice(FEATURES)))
            for target, rival, feature in sorted(seen):
                body = template.format(T=target, O=rival, F=feature)
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
