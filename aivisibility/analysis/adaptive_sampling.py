"""Adaptive sampling: simulate which (brand, engine) to probe next.

Goal: get precise competitor-mention numbers with fewer calls than
round-robin. Runs offline on data from weeks 2-4 (no new API calls).
Details: docs/weeks/week5.md.

One arm = (subject_brand, engine). One call returns one response that is
checked against all competitors at once, so a simulated draw reuses a
whole old response row.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ..common import db
from .bootstrap import bootstrap_ci
from .mentions import build_candidate_dictionary, load_brand_profiles
from .precision import BOOTSTRAP_RESAMPLES


@dataclass
class BanditArm:
    subject_brand: str
    engine: str
    entities: list[str]  # competitors of subject_brand (own brand excluded)
    response_pool: list[dict[str, bool]]  # real historical rows: entity -> mentioned
    history: list[dict[str, bool]] = field(default_factory=list)  # this simulation run's draws


def build_arms() -> list[BanditArm]:
    """Make one arm for each (brand, engine) found in the DB."""
    profiles = load_brand_profiles()
    candidates_by_brand = {
        brand: [e for e in build_candidate_dictionary(profile) if e != brand]
        for brand, profile in profiles.items()
    }

    responses = db.get_responses_with_brand()
    grouped: dict[tuple[str, str], list[int]] = {}
    for row in responses:
        if row["error"] or not row["raw_text"]:
            continue
        grouped.setdefault((row["subject_brand"], row["engine"]), []).append(row["response_id"])

    all_response_ids = [rid for ids in grouped.values() for rid in ids]
    mentions_by_response = db.get_mentions_for_responses(all_response_ids)

    arms = []
    for (subject_brand, engine), response_ids in grouped.items():
        entities = candidates_by_brand.get(subject_brand, [])
        pool = [
            {entity: entity in mentions_by_response[rid] for entity in entities}
            for rid in response_ids
        ]
        arms.append(BanditArm(subject_brand=subject_brand, engine=engine, entities=entities, response_pool=pool))
    return arms


def draw(arm: BanditArm, rng: np.random.Generator) -> dict[str, bool]:
    """Fake one API call: pick a random old response from the arm."""
    idx = int(rng.integers(len(arm.response_pool)))
    return arm.response_pool[idx]


@dataclass
class SimContext:
    arms: list[BanditArm]
    active: list[bool]
    target_pp: float
    stability_window: int
    n_resamples: int
    boot_rng: np.random.Generator
    stable_streak: dict[tuple[str, str, str], int] = field(default_factory=dict)
    arm_scores: list[float] = field(default_factory=list)
    _rr_cursor: int = 0


def _next_seed(rng: np.random.Generator) -> int:
    """A fresh seed for one `bootstrap_ci` call, so the whole session is
    reproducible from the single `seed` given to `simulate`."""
    return int(rng.integers(2**32))


def _entity_history(arm: BanditArm, entity: str) -> list[bool]:
    """Mentioned / not mentioned for one competitor, over all draws so far."""
    return [row[entity] for row in arm.history]


def _compute_arm_score(arm: BanditArm, ctx: SimContext) -> float:
    """Priority of an arm: its widest CI among competitors not yet stable.

    Wide CI = still unsure = probe more. Fewer than 2 draws gives inf,
    because one data point would wrongly look "precise"."""
    scores = []
    for entity in arm.entities:
        key = (arm.subject_brand, arm.engine, entity)
        if ctx.stable_streak.get(key, 0) >= ctx.stability_window:
            continue
        hist = _entity_history(arm, entity)
        if len(hist) < 2:
            scores.append(math.inf)
            continue
        _, lower, upper = bootstrap_ci(hist, n_resamples=ctx.n_resamples, seed=_next_seed(ctx.boot_rng))
        scores.append((upper - lower) / 2 * 100)
    return max(scores) if scores else -math.inf


def _update_stability(
    stable_streak: dict[tuple[str, str, str], int],
    key: tuple[str, str, str],
    width_pp: float,
    target_pp: float,
    stability_window: int,
) -> bool:
    """Check if a competitor is stable (precise enough for long enough).

    The CI must stay at or below the target for `stability_window` checks
    in a row. One bad check resets the count. Returns True when stable."""
    if width_pp <= target_pp:
        stable_streak[key] = stable_streak.get(key, 0) + 1
    else:
        stable_streak[key] = 0
    return stable_streak[key] >= stability_window


def uniform_policy(ctx: SimContext) -> int:
    """Round-robin: take the active arms in turn."""
    active_indices = [i for i, active in enumerate(ctx.active) if active]
    idx = active_indices[ctx._rr_cursor % len(active_indices)]
    ctx._rr_cursor += 1
    return idx


def variance_policy(ctx: SimContext) -> int:
    """Adaptive: take the arm we are least sure about."""
    return int(np.argmax(ctx.arm_scores))


Policy = Callable[[SimContext], int]


@dataclass
class SimResult:
    total_draws: int
    draws_per_arm: list[int]
    hit_cap: bool


def simulate(
    arms: list[BanditArm],
    policy: Policy,
    target_pp: float = 5.0,
    stability_window: int = 5,
    max_draws: int = 4000,
    n_resamples: int = 150,
    seed: int | None = None,
) -> SimResult:
    """Run one fake sampling session using `policy`.

    Stops when every competitor in every arm is stable, or when
    `max_draws` is reached (safety cap)."""
    # Two independent streams: one for the fake draws, one for the bootstrap.
    draw_seed, boot_seed = np.random.SeedSequence(seed).spawn(2)
    rng = np.random.default_rng(draw_seed)
    boot_rng = np.random.default_rng(boot_seed)
    for arm in arms:
        arm.history = []

    ctx = SimContext(
        arms=arms,
        active=[True] * len(arms),
        target_pp=target_pp,
        stability_window=stability_window,
        n_resamples=n_resamples,
        boot_rng=boot_rng,
    )
    ctx.arm_scores = [_compute_arm_score(arm, ctx) for arm in arms]

    draws_per_arm = [0] * len(arms)
    total_draws = 0

    while any(ctx.active) and total_draws < max_draws:
        idx = policy(ctx)
        arm = arms[idx]

        row = draw(arm, rng)
        arm.history.append(row)
        draws_per_arm[idx] += 1
        total_draws += 1

        all_stable = True
        for entity in arm.entities:
            key = (arm.subject_brand, arm.engine, entity)
            hist = _entity_history(arm, entity)
            if len(hist) < 2:
                ctx.stable_streak[key] = 0
                all_stable = False
                continue
            _, lower, upper = bootstrap_ci(hist, n_resamples=n_resamples, seed=_next_seed(boot_rng))
            width_pp = (upper - lower) / 2 * 100
            stable = _update_stability(ctx.stable_streak, key, width_pp, target_pp, stability_window)
            all_stable = all_stable and stable

        ctx.active[idx] = not all_stable
        ctx.arm_scores[idx] = _compute_arm_score(arm, ctx) if ctx.active[idx] else -math.inf

    return SimResult(total_draws=total_draws, draws_per_arm=draws_per_arm, hit_cap=total_draws >= max_draws)


def run_fixed_budget(
    arms: list[BanditArm],
    policy: Policy,
    budget: int,
    n_resamples: int = 150,
    seed: int | None = None,
) -> None:
    """Spend exactly `budget` fake calls, no early stop.

    Used to compare policies at the same cost. Fills `arms[i].history`;
    read the result with `final_entity_widths()`."""
    simulate(
        arms,
        policy,
        target_pp=5.0,
        stability_window=budget + 1,  # unreachable within `budget` draws -> never stops early
        max_draws=budget,
        n_resamples=n_resamples,
        seed=seed,
    )


def final_entity_widths(
    arms: list[BanditArm], n_resamples: int = BOOTSTRAP_RESAMPLES, seed: int | None = None
) -> dict[tuple[str, str, str], float]:
    """CI half-width (in percentage points) for every competitor.

    Smaller = more precise. NaN if a competitor has fewer than 2 draws."""
    boot_rng = np.random.default_rng(seed)
    widths: dict[tuple[str, str, str], float] = {}
    for arm in arms:
        for entity in arm.entities:
            key = (arm.subject_brand, arm.engine, entity)
            hist = _entity_history(arm, entity)
            if len(hist) < 2:
                widths[key] = float("nan")
                continue
            _, lower, upper = bootstrap_ci(hist, n_resamples=n_resamples, seed=_next_seed(boot_rng))
            widths[key] = (upper - lower) / 2 * 100
    return widths
