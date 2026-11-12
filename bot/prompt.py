"""Builds the text sent to the LLM. Only closes up to day D go in (no leak), and as few tokens as possible."""
from datetime import date

N_CLOSES = 20


def build_prompt(history: dict[str, list[tuple[date, float]]], tickers: list[str],
                 day: date, version: str) -> str:
    """Day D is named once; each ticker gets only its closes, oldest first, the last one being day D.
    (Repeating a date next to every close would cost about 2,000 more tokens a day.)"""
    lines = [
        f"prompt_version: {version}",
        f"Day D is {day.isoformat()}. Below, each stock lists its most recent daily closes "
        f"(up to {N_CLOSES}), oldest first; the last one is day D.",
        "For each stock give p_up: the chance, from 0 to 1, that it closes higher on the next trading "
        "day than on day D.",
        "Answer with only a JSON object mapping every ticker above to its p_up.",
        "",
    ]
    for ticker in tickers:
        recent = sorted((when, close) for when, close in history[ticker] if when <= day)[-N_CLOSES:]
        lines.append(f"{ticker}: " + ", ".join(f"{close:.2f}" for _, close in recent))
    return "\n".join(lines)
