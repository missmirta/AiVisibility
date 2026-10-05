"""Sanity checks for the adaptive-sampling building blocks, on synthetic
data with a known-in-advance answer — before trusting them on real data:

1. `variance_policy` must send more draws to the higher-variance arm.
2. `_update_stability`'s moving window must not declare an entity stable
   on a single lucky dip below target if it later bounces back up.

Run: python scripts/adaptive_sampling_sanity_check.py
"""

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.analysis.adaptive_sampling import (
    BanditArm,
    SimContext,
    _update_stability,
    simulate,
    uniform_policy,
    variance_policy,
)


def check_variance_policy_prefers_high_variance_arm() -> None:
    rng_pool_size = 2000
    high_variance_pool = [{"X": v} for v in ([True] * (rng_pool_size // 2) + [False] * (rng_pool_size // 2))]
    low_variance_pool = [{"X": v} for v in ([True] * int(rng_pool_size * 0.02) + [False] * int(rng_pool_size * 0.98))]

    arm_high = BanditArm(subject_brand="High", engine="sim", entities=["X"], response_pool=high_variance_pool)
    arm_low = BanditArm(subject_brand="Low", engine="sim", entities=["X"], response_pool=low_variance_pool)

    result = simulate(
        [arm_high, arm_low],
        variance_policy,
        target_pp=5.0,
        stability_window=5,
        max_draws=3000,
        n_resamples=150,
        seed=1,
    )
    draws_high, draws_low = result.draws_per_arm
    print(f"variance_policy: draws high-variance arm (p=0.5)={draws_high}, "
          f"low-variance arm (p=0.02)={draws_low}, hit_cap={result.hit_cap}")
    assert draws_high > draws_low, (
        "expected the high-variance arm (p=0.5) to receive more draws than "
        "the near-certain low-variance arm (p=0.02)"
    )
    print("  OK: variance_policy prioritized the higher-variance arm.\n")


def check_uniform_policy_round_robins_and_skips_inactive() -> None:
    # Mechanical check, independent of bootstrap randomness: uniform_policy
    # must cycle strictly through active arms in order, and skip an arm the
    # moment it is marked inactive.
    arm_a = BanditArm(subject_brand="A", engine="sim", entities=["X"], response_pool=[{"X": False}])
    arm_b = BanditArm(subject_brand="B", engine="sim", entities=["X"], response_pool=[{"X": False}])
    arm_c = BanditArm(subject_brand="C", engine="sim", entities=["X"], response_pool=[{"X": False}])
    ctx = SimContext(
        arms=[arm_a, arm_b, arm_c], active=[True, True, True],
        target_pp=5.0, stability_window=5, n_resamples=150,
    )

    picks = [uniform_policy(ctx) for _ in range(6)]
    print(f"uniform_policy picks with 3 active arms: {picks}")
    assert picks == [0, 1, 2, 0, 1, 2], "expected strict round-robin over active arms"

    ctx.active[1] = False  # arm B done
    picks_after_b_done = [uniform_policy(ctx) for _ in range(4)]
    print(f"uniform_policy picks after arm B goes inactive: {picks_after_b_done}")
    assert 1 not in picks_after_b_done, "uniform_policy must skip an inactive arm"
    print("  OK: uniform_policy round-robins and skips inactive arms.\n")


def check_stability_window_ignores_a_single_lucky_dip() -> None:
    # Simulated width sequence: dips below target once, bounces back up,
    # then genuinely stays low. A naive "first crossing" rule would have
    # declared victory at step 2 (streak=1) — the window must not.
    target_pp, window = 5.0, 3
    widths = [12.0, 4.0, 11.0, 3.0, 3.0, 3.0, 3.0]
    streak: dict = {}
    key = ("Test", "sim", "X")
    stable_at = None
    for step, width in enumerate(widths, start=1):
        if _update_stability(streak, key, width, target_pp, window):
            stable_at = step
            break

    print(f"stability window: widths={widths}, stable declared at step={stable_at}")
    # step 2 has width=4.0 <= target (a single lucky dip) — must NOT trigger.
    assert stable_at is not None and stable_at > 2, (
        "a single dip below target must not be enough to declare stability"
    )
    # Real stability only starts building from step 4 (3.0, 3.0, 3.0, 3.0);
    # 3 in a row is reached at step 6.
    assert stable_at == 6, f"expected stability at step 6, got {stable_at}"
    print("  OK: a single lucky dip did not trigger early stopping.\n")


def main() -> None:
    check_variance_policy_prefers_high_variance_arm()
    check_uniform_policy_round_robins_and_skips_inactive()
    check_stability_window_ignores_a_single_lucky_dip()
    print("All sanity checks passed.")


if __name__ == "__main__":
    main()
