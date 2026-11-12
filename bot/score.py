"""Scores a stored call against what really happened. Uses Close, never Adj Close."""
from dataclasses import dataclass

from bot.fetch import Bar


@dataclass(frozen=True)
class ScoredRow:
    ticker: str
    p_up: float
    outcome: str      # "up" or "down" (flat rows are never created)


def label(close_d: float, close_d1: float) -> str:
    if close_d1 > close_d:
        return "up"
    if close_d1 < close_d:
        return "down"
    return "flat"


def score_day(p_up: dict[str, float], bars_d: dict[str, Bar | None],
              bars_d1: dict[str, Bar | None]) -> list[ScoredRow]:
    """One row per ticker with both bars and a non-flat move. Others are left out, not guessed.
    A split on D+1 also leaves the ticker out: our saved Close(D) and the new Close(D+1) are on
    different scales (4-for-1: 400 then ~100 would score a rise as 'down')."""
    rows = []
    for ticker, p in p_up.items():
        bar_d, bar_d1 = bars_d.get(ticker), bars_d1.get(ticker)
        if bar_d is None or bar_d1 is None or bar_d1.split:
            continue
        outcome = label(bar_d.close, bar_d1.close)
        if outcome != "flat":
            rows.append(ScoredRow(ticker, p, outcome))
    return rows
