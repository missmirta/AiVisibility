"""Export everything the dashboard shows to data/reports/dashboard.json.

Run: uv run python scripts/export_dashboard_data.py [--seed 42] [--perception-run-id 3 4]

Reads the DB and stored labels only; makes no Claude/OpenAI calls. See docs/sections/section8.md.
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aivisibility.common import config, db
from aivisibility.reporting.dashboard_data import build_dashboard_data

OUT_FILE = config.REPORTS_DIR / "dashboard.json"


def main(seed: int, n_resamples: int, n_boot: int, run_ids: list[int] | None, permutations: int) -> None:
    db.init_db()
    data = build_dashboard_data(seed, n_resamples, n_boot, run_ids, permutations)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"visibility rows: {len(data['visibility'])}, engines (convergence): {list(data['convergence'])}, "
          f"perception cells: {len(data['perception'].get('cells', []))}")
    print(f"adaptive sampling: {data['adaptive_sampling'].get('available')}, "
          f"stance groups: {len(data['stance'].get('items', []))}")
    if data["meta"]["not_exported"]:
        print(f"Not exported yet: {', '.join(data['meta']['not_exported'])}")
    print(f"Saved: {OUT_FILE}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-resamples", type=int, default=1000)
    p.add_argument("--n-boot", type=int, default=1000)
    p.add_argument("--permutations", type=int, default=200, help="permutation test size (two-sample test)")
    p.add_argument("--perception-run-id", type=int, nargs="+", default=[3, 4],
                   help="pairwise runs to use (default 3 4: the full week-7 runs; 1-2 were pilots)")
    a = p.parse_args()
    main(a.seed, a.n_resamples, a.n_boot, a.perception_run_id, a.permutations)
