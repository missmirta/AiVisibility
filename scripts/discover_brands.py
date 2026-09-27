"""Run the Discovery Agent for the pilot brands with human-in-the-loop
confirmation. Run: python scripts/discover_brands.py
"""

import asyncio
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from aivisibility.common.config import BRANDS_DIR, PILOT_BRANDS
from aivisibility.common.schemas import BrandProfile
from aivisibility.discovery.agent import research_brand


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace(".", "")


def _print_summary(profile: BrandProfile) -> None:
    print(f"\n--- {profile.brand} ---")
    print(f"  niche: {profile.niche}")
    print(f"  competitors: {', '.join(profile.competitors)}")
    print(f"  target_audience: {profile.target_audience}")
    print(f"  key_use_cases: {', '.join(profile.key_use_cases)}")


def _confirm_loop(path: Path, profile: BrandProfile) -> BrandProfile:
    while True:
        _print_summary(profile)
        choice = input("Accept this profile? [y] yes / [e] edit / [r] regenerate: ").strip().lower()
        if choice == "y":
            return profile
        if choice == "e":
            editor = None
            for candidate in ("notepad", "nano", "vi"):
                if subprocess.run(["where" if sys.platform == "win32" else "which", candidate],
                                   capture_output=True).returncode == 0:
                    editor = candidate
                    break
            if editor:
                subprocess.run([editor, str(path)])
            else:
                input(f"Edit the file {path} by hand and press Enter...")
            try:
                profile = BrandProfile.model_validate_json(path.read_text(encoding="utf-8"))
            except ValidationError as exc:
                print(f"  File does not match the schema: {exc}\n  Try again.")
            continue
        if choice == "r":
            return None
        print("  Didn't understand that, enter y / e / r.")


async def main() -> None:
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)
    for brand in PILOT_BRANDS:
        name, url = brand["name"], brand.get("url")
        path = BRANDS_DIR / f"{_slug(name)}.json"

        profile = None
        while profile is None:
            print(f"\n=== Discovery: {name} ===")
            draft = await research_brand(name, url)
            path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
            profile = _confirm_loop(path, draft)

        path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
        print(f"Saved confirmed profile: {path}")

    print("\nDone. All pilot brand profiles are confirmed.")


if __name__ == "__main__":
    asyncio.run(main())
