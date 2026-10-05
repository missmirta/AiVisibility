from aivisibility.analysis.adaptive_sampling import (
    BanditArm,
    final_entity_widths,
    run_fixed_budget,
    uniform_policy,
    variance_policy,
)


def _arms():
    pool = [{"A": i % 3 == 0, "B": i % 5 == 0} for i in range(30)]
    return [
        BanditArm("Brand1", "claude", ["A", "B"], pool),
        BanditArm("Brand2", "openai", ["A", "B"], pool),
    ]


def _run(policy, seed):
    arms = _arms()
    run_fixed_budget(arms, policy, budget=40, n_resamples=100, seed=seed)
    return final_entity_widths(arms, n_resamples=100, seed=seed), [len(a.history) for a in arms]


def test_same_seed_gives_identical_results():
    for policy in (uniform_policy, variance_policy):
        assert _run(policy, seed=5) == _run(policy, seed=5)


def test_different_seed_changes_results():
    assert _run(variance_policy, seed=1) != _run(variance_policy, seed=2)
