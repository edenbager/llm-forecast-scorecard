"""Baseline from past closes. Only closes up to and including day D are ever used (no leak)."""
from datetime import date


def base_rate(closes: list[tuple[date, float]], day: date) -> float:
    """Share of up-moves between consecutive closes up to day D. Flat moves are left out.

    Example: closes 10, 11, 10, 12 -> moves up, down, up -> 2/3.
    """
    until_d = sorted((when, close) for when, close in closes if when <= day)
    moves = [after - before for (_, before), (_, after) in zip(until_d, until_d[1:]) if after != before]
    if not moves:
        raise ValueError(f"no price moves up to {day}: cannot compute a base rate")
    return sum(move > 0 for move in moves) / len(moves)
