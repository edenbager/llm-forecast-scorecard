"""Scores over many calls. Rows hold p_up and what happened ("up" or "down")."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Row:
    p_up: float
    outcome: str
    prompt_version: str = "v1"


def brier(rows: list[Row]) -> float:
    """Mean of (p_up - outcome)^2, outcome 1 = up, 0 = down. 0 is perfect; always 0.5 gives 0.25."""
    if not rows:
        raise ValueError("no rows to score")
    return sum((r.p_up - (r.outcome == "up")) ** 2 for r in rows) / len(rows)


def bootstrap_interval(values: list[float], n_boot: int = 10_000, seed: int | None = None,
                       confidence: float = 0.95) -> tuple[float, float]:
    """Resample the values (one per day) with replacement n_boot times and take the middle
    `confidence` share of the resampled means. Shows how much the average wobbles."""
    if not values:
        raise ValueError("no values to resample")
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n_boot))
    tail = (1 - confidence) / 2
    return means[int(tail * (n_boot - 1))], means[int((1 - tail) * (n_boot - 1))]


MIN_BUCKET_N = 30          # a bucket with fewer calls is too noisy to show


@dataclass(frozen=True)
class Bucket:
    label: str
    n: int
    mean_p: float | None     # None = hidden (n < MIN_BUCKET_N)
    freq_up: float | None    # share of calls that went up; None = hidden


def calibration(rows: list[Row]) -> list[Bucket]:
    """3 buckets: p_up < 0.45, 0.45 to 0.55, > 0.55. Says if the stated chance matches how often stocks rose."""
    groups = {"<0.45": [], "0.45-0.55": [], ">0.55": []}
    for r in rows:
        key = "<0.45" if r.p_up < 0.45 else ">0.55" if r.p_up > 0.55 else "0.45-0.55"
        groups[key].append(r)
    buckets = []
    for label, group in groups.items():
        shown = len(group) >= MIN_BUCKET_N
        buckets.append(Bucket(
            label, len(group),
            sum(r.p_up for r in group) / len(group) if shown else None,
            sum(r.outcome == "up" for r in group) / len(group) if shown else None))
    return buckets


def hit_rate(rows: list[Row]) -> tuple[float | None, int]:
    """(share of right-side calls, number of calls counted). p_up = 0.5 picks no side, so it is skipped."""
    sided = [r for r in rows if r.p_up != 0.5]
    if not sided:
        return None, 0
    hits = sum((r.p_up > 0.5) == (r.outcome == "up") for r in sided)
    return hits / len(sided), len(sided)
