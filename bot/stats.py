"""Scores over many calls. Rows hold p_up and what happened ("up" or "down")."""
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


def hit_rate(rows: list[Row]) -> tuple[float | None, int]:
    """(share of right-side calls, number of calls counted). p_up = 0.5 picks no side, so it is skipped."""
    sided = [r for r in rows if r.p_up != 0.5]
    if not sided:
        return None, 0
    hits = sum((r.p_up > 0.5) == (r.outcome == "up") for r in sided)
    return hits / len(sided), len(sided)
