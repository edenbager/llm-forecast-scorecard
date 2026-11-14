"""Baseline from past closes. Only closes up to and including day D are ever used (no leak)."""
from datetime import date


def base_rate(closes: list[tuple[date, float]], day: date,
              benchmark_closes: list[tuple[date, float]] | None = None) -> float:
    """Share of up-moves between consecutive closes up to day D. Flat moves are left out.
    With benchmark_closes (v1b): share of days the stock's return beat the benchmark's (same dates only).

    Example: closes 10, 11, 10, 12 -> moves up, down, up -> 2/3.
    """
    until_d = sorted((when, close) for when, close in closes if when <= day)
    if benchmark_closes is not None:
        bench = {when: close for when, close in benchmark_closes if when <= day}
        pairs = [after / before - bench[later] / bench[earlier]
                 for (earlier, before), (later, after) in zip(until_d, until_d[1:])
                 if earlier in bench and later in bench]
        moves = [m for m in pairs if m != 0]
        if not moves:
            raise ValueError(f"no price moves up to {day}: cannot compute a base rate")
        return sum(move > 0 for move in moves) / len(moves)
    moves = [after - before for (_, before), (_, after) in zip(until_d, until_d[1:]) if after != before]
    if not moves:
        raise ValueError(f"no price moves up to {day}: cannot compute a base rate")
    return sum(move > 0 for move in moves) / len(moves)
