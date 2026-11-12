"""Builds the text sent to the LLM. Only closes up to day D go in (no leak), and as few tokens as possible."""
from datetime import date

from bot import market

N_CLOSES = 20


def build_prompt(history: dict[str, list[tuple[date, float]]], tickers: list[str],
                 day: date, version: str) -> str:
    """Day D is named once; each ticker gets only its closes, oldest first, the last one being day D.
    (Repeating a date next to every close would cost about 2,000 more tokens a day.) A '|' marks the
    one thing the dates used to show: a trading day missing between two closes."""
    ticker_lines = []
    gap_seen = False
    for ticker in tickers:
        recent = sorted((when, close) for when, close in history[ticker] if when <= day)[-N_CLOSES:]
        text, gap = _closes_text(recent)
        gap_seen = gap_seen or gap
        ticker_lines.append(f"{ticker}: {text}")
    lines = [
        f"prompt_version: {version}",
        f"Day D is {day.isoformat()}. Below, each stock lists its most recent daily closes "
        f"(up to {N_CLOSES}), oldest first; the last one is day D.",
    ]
    if gap_seen:
        lines.append("A '|' between two closes means at least one trading day is missing there.")
    lines += [
        "For each stock give p_up: the chance, from 0 to 1, that it closes higher on the next trading "
        "day than on day D.",
        "Answer with only a JSON object mapping every ticker above to its p_up.",
        "",
    ]
    return "\n".join(lines + ticker_lines)


def _closes_text(recent: list[tuple[date, float]]) -> tuple[str, bool]:
    """'1.00, 2.00 | 4.00': closes in order, ' | ' where a trading day is missing between two of them."""
    if not recent:
        return "", False
    trading = market.trading_days(recent[0][0], recent[-1][0])
    text, gap = f"{recent[0][1]:.2f}", False
    for (before, _), (after, close) in zip(recent, recent[1:]):
        missing = any(before < day < after for day in trading)
        gap = gap or missing
        text += (" | " if missing else ", ") + f"{close:.2f}"
    return text, gap
