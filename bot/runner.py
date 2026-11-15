"""The daily run: gate, backfill, score yesterday's call, fetch, call, store, commit."""
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from bot import budget, market, report, runlog, store
from bot.caller import make_call
from bot.history import base_rate
from bot.prompt import build_prompt
from bot.score import score_day


NEW_YORK = ZoneInfo("America/New_York")


@dataclass
class Deps:
    fetch: Callable      # (tickers, day, now) -> {ticker: Bar | None}
    llm: Callable        # (prompt, tickers) -> LLMReply
    git: Any             # .commit_push(message)


def run(now: datetime, root: Path, deps: Deps, day=None) -> int:
    root = Path(root)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware (UTC)")
    # D is the New York calendar date: a run delayed past 00:00 UTC still belongs to the same trading day.
    day = day or now.astimezone(NEW_YORK).date()
    if not market.is_trading_day(day):
        return 0                                   # step 1, gate: write nothing
    try:
        _process_day(now, root, deps, day)
    finally:
        # Step 6 runs even when the day failed: a paid call must reach the ledger in the repo, because
        # the CI machine is thrown away. (Conflict retry lives in gitsync; no change means no commit.)
        deps.git.commit_push(f"bot run {day.isoformat()}")
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
    # The benchmark the call was made under, not today's config: a v1 call stays an up/down call.
    rows = score_day(record["p_up"], store.load_snapshot(root, prev), bars_today, record.get("benchmark"))
    store.add_scores(root, prev, record["prompt_version"], rows)


CATCH_UP_DAYS = 5      # how many older trading days are checked for a call that never got its D+1 run


def _score_missed(root: Path, day, deps: Deps, now: datetime) -> None:
    """Grade older calls with no score rows: their D+1 run never happened, so fetch that D+1 now.
    Any failure only prints a warning to the job log; it must never stop today's call. (It is not written
    to log.csv: a day-level row there would replace that day's 'ok' in the report counts.)
    Known costs, accepted: a call that scores zero rows is fetched again on each run of the window, and a
    call older than the window is never graded."""
    older = market.previous_trading_day(day)                 # yesterday's call is graded by its own step
    for _ in range(CATCH_UP_DAYS):
        older = market.previous_trading_day(older)
        try:
            path = store.call_path(root, older)
            if older.isoformat() in {row["day"] for row in store.read_scores(root)} or not path.exists():
                continue
            record = json.loads(path.read_text())
            snapshot = store.load_snapshot(root, older)
            if not record.get("p_up") or not snapshot:
                continue
            benchmark = record.get("benchmark")
            bars = deps.fetch(list(record["p_up"]) + ([benchmark] if benchmark else []),
                              market.next_trading_day(older), now)
            store.add_scores(root, older, record["prompt_version"],
                             score_day(record["p_up"], snapshot, bars, benchmark))
        except Exception as err:
            print(f"WARNING: catch-up scoring of {older} failed: {err!r}", file=sys.stderr)


def _process_day(now: datetime, root: Path, deps: Deps, day) -> None:
    config = json.loads((root / "config.json").read_text())
    runlog.backfill(root, day)                     # step 2

    if store.call_path(root, day).exists():
        return                                     # write-once: touch nothing, make no call

    # Fetch and score first, even on a late day: day D's final close is still there, and yesterday's
    # call can be graded at any time. Only the NEW call is forbidden once D+1 has opened.
    benchmark = config.get("benchmark")                      # v1b: a reference ticker, never asked about
    bars = deps.fetch(config["tickers"] + ([benchmark] if benchmark else []), day, now)   # step 4
    store.write_snapshot(root, day, bars)
    for ticker, bar in bars.items():
        if bar is None:
            runlog.add(root, day, "no data", ticker)
        elif bar.split:
            runlog.add(root, day, "split", ticker)   # noted; the ticker is left out of scoring
    _score_previous_day(root, day, bars)                      # step 3
    _score_missed(root, day, deps, now)                       # step 3b: calls whose D+1 run was missed
    if now > market.next_open_utc(day):
        runlog.add(root, day, "late")              # D+1 already opened: a call would be a leak
        _write_report_safely(root)
        return
    tickers = [t for t in config["tickers"] if bars.get(t) is not None]
    if not tickers:
        return                                     # nothing to ask the LLM about
    if benchmark and bars.get(benchmark) is None:
        _write_report_safely(root)
        return                                     # no benchmark close to compare with: no call today

    history = store.load_history(root)                       # step 5
    # Baselines first: if one cannot be computed the run fails loud BEFORE the paid LLM call.
    bench_closes = history[benchmark] if benchmark else None
    base_rates = {t: base_rate(history[t], day, bench_closes) for t in tickers}
    prompt = build_prompt(history, tickers, day, config["prompt_version"], benchmark)
    if not budget.allows_call(root, day, config["model"], prompt):
        runlog.add(root, day, "budget")            # no call, no call file: a re-run may still call later
        _write_report_safely(root)
        return
    outcome = make_call(prompt, deps.llm, tickers, on_reply=lambda reply: budget.record(
        root, day, config["prompt_version"], config["model"], [reply]))
    last = outcome.replies[-1]
    runlog.add(root, day, outcome.status)
    store.write_call(root, day, {
        "day": day.isoformat(), "status": outcome.status, "prompt": prompt,
        "prompt_version": config["prompt_version"], "model": last.model,
        "response_id": last.response_id, "raw_output": last.text,
        "called_at": now.isoformat(), "p_up": outcome.p_up,
        "base_rate": base_rates, "benchmark": benchmark,
        "run_sha": os.environ.get("GITHUB_SHA"),             # the commit this run read config.json from
    })
    _write_report_safely(root)                               # last: it shows today's log row and call


def _write_report_safely(root: Path) -> None:
    """report.md is a side-output: if it breaks, say so in the job log, but never stop the day's call."""
    try:
        report.write_report(root)
    except Exception as err:
        print(f"WARNING: report.md not updated: {err!r}", file=sys.stderr)
