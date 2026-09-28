"""Mention rate ± bootstrap CI per (subject_brand, engine, mentioned_entity)
group, for one run."""

from dataclasses import dataclass

from ..common import db
from .bootstrap import bootstrap_ci
from .mentions import build_candidate_dictionary, load_brand_profiles


@dataclass
class MentionRateRow:
    subject_brand: str
    engine: str
    mentioned_entity: str
    n: int
    point: float
    lower: float
    upper: float


def compute_mention_rates(
    run_id: int, n_resamples: int = 2000, seed: int | None = None
) -> list[MentionRateRow]:
    """For every (subject_brand, engine) present in `run_id`, and every
    candidate entity in that subject brand's dictionary (own brand +
    competitors): the boolean "mentioned in this response" vector across
    all responses in the group, reduced to a bootstrap CI."""
    profiles = load_brand_profiles()
    candidates_by_brand = {
        brand: build_candidate_dictionary(profile) for brand, profile in profiles.items()
    }

    responses = db.get_responses_with_brand(run_id=run_id)
    groups: dict[tuple[str, str], list[int]] = {}
    for row in responses:
        if row["error"] or not row["raw_text"]:
            continue
        key = (row["subject_brand"], row["engine"])
        groups.setdefault(key, []).append(row["response_id"])

    all_response_ids = [rid for ids in groups.values() for rid in ids]
    mentions_by_response = db.get_mentions_for_responses(all_response_ids)

    rows: list[MentionRateRow] = []
    for (subject_brand, engine), response_ids in groups.items():
        candidates = candidates_by_brand.get(subject_brand, [])
        for entity in candidates:
            mentioned = [entity in mentions_by_response[rid] for rid in response_ids]
            point, lower, upper = bootstrap_ci(mentioned, n_resamples=n_resamples, seed=seed)
            rows.append(
                MentionRateRow(
                    subject_brand=subject_brand,
                    engine=engine,
                    mentioned_entity=entity,
                    n=len(response_ids),
                    point=point,
                    lower=lower,
                    upper=upper,
                )
            )
    return rows
