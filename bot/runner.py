"""The daily run: gate, backfill, score yesterday's call, fetch, call, store, commit."""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bot import market, runlog, store
from bot.caller import make_call
from bot.history import base_rate
from bot.prompt import build_prompt
from bot.score import score_day


NEW_YORK = ZoneInfo("America/New_York")


@dataclass
class Deps:
    fetch: Callable      # (tickers, day, now) -> {ticker: Bar | None}
    llm: Callable        # (prompt) -> LLMReply
    git: Any             # .commit_push(message)


def run(now: datetime, root: Path, deps: Deps, day=None) -> int:
    root = Path(root)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware (UTC)")
    # D is the New York calendar date: a run delayed past 00:00 UTC still belongs to the same trading day.
    day = day or now.astimezone(NEW_YORK).date()
    if not market.is_trading_day(day):
        return 0                                   # step 1, gate: write nothing
    _process_day(now, root, deps, day)
    deps.git.commit_push(f"bot run {day.isoformat()}")   # step 6 (conflict retry lives in gitsync)
    return 0


def _score_previous_day(root: Path, day, bars_today: dict) -> None:
    """Score the call made on the previous trading day: its D is that day, today is D+1."""
    prev = market.previous_trading_day(day)
    path = store.call_path(root, prev)
    if not path.exists():
        return
    record = json.loads(path.read_text())
    if not record.get("p_up"):                     # an invalid call has nothing to score
        return
    rows = score_day(record["p_up"], store.load_snapshot(root, prev), bars_today)
    store.add_scores(root, prev, record["prompt_version"], rows)


def _process_day(now: datetime, root: Path, deps: Deps, day) -> None:
    config = json.loads((root / "config.json").read_text())
    runlog.backfill(root, day)                     # step 2

    if store.call_path(root, day).exists():
        return                                     # write-once: touch nothing, make no call
    if now > market.next_open_utc(day):
        runlog.add(root, day, "late")              # D+1 already opened: a call would be a leak
        return

    bars = deps.fetch(config["tickers"], day, now)           # step 4
    store.write_snapshot(root, day, bars)
    for ticker, bar in bars.items():
        if bar is None:
            runlog.add(root, day, "no data", ticker)
        elif bar.split:
            runlog.add(root, day, "split", ticker)   # noted only; history is never rewritten
    _score_previous_day(root, day, bars)                     # step 3
    tickers = [t for t in config["tickers"] if bars.get(t) is not None]
    if not tickers:
        return                                     # nothing to ask the LLM about

    history = store.load_history(root)                       # step 5
    # Baselines first: if one cannot be computed the run fails loud BEFORE the paid LLM call.
    base_rates = {t: base_rate(history[t], day) for t in tickers}
    prompt = build_prompt(history, tickers, day, config["prompt_version"])
    outcome = make_call(prompt, deps.llm, tickers)
    last = outcome.replies[-1]
    runlog.add(root, day, outcome.status)
    store.write_call(root, day, {
        "day": day.isoformat(), "status": outcome.status, "prompt": prompt,
        "prompt_version": config["prompt_version"], "model": last.model,
        "response_id": last.response_id, "raw_output": last.text,
        "called_at": now.isoformat(), "p_up": outcome.p_up,
        "base_rate": base_rates,
    })
