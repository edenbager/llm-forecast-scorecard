"""Builds the text sent to the LLM. Only closes up to day D go in (no leak)."""
from datetime import date

N_CLOSES = 20


def build_prompt(history: dict[str, list[tuple[date, float]]], tickers: list[str],
                 day: date, version: str) -> str:
    lines = [
        f"prompt_version: {version}",
        f"Day D is {day.isoformat()}. For each stock below you get its last {N_CLOSES} daily closes, "
        "oldest first, as date:close.",
        f"For each stock give p_up: the chance, from 0 to 1, that it closes higher on the next trading "
        f"day than on day D.",
        "Answer with only a JSON list, exactly these tickers, once each: "
        '[{"ticker": "AAPL", "p_up": 0.55}, ...]',
        "",
    ]
    for ticker in tickers:
        recent = sorted((when, close) for when, close in history[ticker] if when <= day)[-N_CLOSES:]
        lines.append(f"{ticker}: " + ", ".join(f"{when.isoformat()}:{close:.2f}" for when, close in recent))
    return "\n".join(lines)
