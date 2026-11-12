"""Shared test helpers. They also state the CONTRACT the code must follow.

Contract (the tests are the spec; the code is written to make them pass):
  bot.market   is_trading_day(d), next_trading_day(d), next_open_utc(d), session_close_utc(d)
  bot.fetch    Bar(close, adj_close, fetch_time, split=0.0); PartialBarError;
               fetch_bars(tickers, day, now, download, sleep, attempts=3) -> {ticker: Bar | None}
  bot.llm      LLMReply(text, stop_reason, response_id, model)
  bot.validate parse_and_validate(text, tickers) -> {ticker: float}; raises InvalidCall
  bot.caller   make_call(prompt, llm, tickers) -> CallOutcome(status "ok"|"invalid", p_up, replies)
  bot.history  base_rate(closes: [(date, close)], day) -> float
  bot.prompt   build_prompt(history: {ticker: [(date, close)]}, tickers, day, version) -> str
  bot.score    label(close_d, close_d1) -> "up"|"down"|"flat"
               score_day(p_up, bars_d, bars_d1) -> [ScoredRow(ticker, p_up, outcome)], flat/missing left out
  bot.stats    Row(p_up, outcome, prompt_version="v1"); brier(rows); hit_rate(rows) -> (rate, n);
               bootstrap_interval(values, n_boot, seed) -> (lo, hi);
               calibration(rows) -> [Bucket(label, n, mean_p, freq_up)], freq_up None when n < 30
  bot.report   summarize_by_version(rows) -> {version: {"n": int, "brier": float}}
  bot.gitsync  push_with_rebase(run) with run(cmd_list) -> exit code; raises PushFailed
  bot.runner   Deps(fetch, llm, git); run(now, root, deps, day=None) -> exit code
               deps.fetch(tickers, day, now) -> {ticker: Bar | None}
               deps.llm(prompt, tickers) -> LLMReply (tickers = the ones asked about today, for the output schema);  deps.git.commit_push(message)  (pull --rebase on conflict is gitsync's job)

Files under root: config.json, data/history.csv (date,ticker,close), data/snapshots/<D>.csv
  (ticker,close,adj_close,fetch_time,split; fetch_time = datetime.isoformat()), calls/<D>.json,
  log.csv (day,ticker,status; ticker blank for day-level rows), scores.csv.
Backfill range = first day in log.csv up to the day before the current day.
"""
import csv
import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from bot.fetch import Bar
from bot.llm import LLMReply

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "BRK-B", "JPM"]


def d(s):
    return date.fromisoformat(s)


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def good_reply(tickers=TICKERS, p=0.6):
    return json.dumps([{"ticker": t, "p_up": p} for t in tickers])


def close_for(ticker, add=0.0):
    return 100.0 + TICKERS.index(ticker) + add


# ---------- fakes ----------
class FakeLLM:
    def __init__(self, replies=None, stop_reason="end_turn", usage=(0, 0)):
        self.replies = list(replies or [])
        self.stop_reason = stop_reason
        self.usage = usage                      # (input_tokens, output_tokens) of every reply
        self.prompts = []

    def __call__(self, prompt, tickers=None):
        self.prompts.append(prompt)
        text = self.replies.pop(0) if self.replies else good_reply()
        return LLMReply(text=text, stop_reason=self.stop_reason,
                        response_id=f"msg_{len(self.prompts)}", model="claude-haiku-5-5",
                        input_tokens=self.usage[0], output_tokens=self.usage[1])


class FakeFetch:
    """Returns the same base closes as seed_call, plus `add`. `missing` tickers come back None."""

    def __init__(self, add=0.0, missing=(), splits=None):
        self.add, self.missing, self.splits, self.calls = add, set(missing), splits or {}, []

    def __call__(self, tickers, day, now):
        self.calls.append((tuple(tickers), day))
        out = {}
        for t in tickers:
            if t in self.missing:
                out[t] = None
            else:
                c = close_for(t, self.add)
                out[t] = Bar(close=c, adj_close=c, fetch_time=now, split=self.splits.get(t, 0.0))
        return out


@dataclass
class FakeGit:
    events: list = field(default_factory=list)

    def commit_push(self, message):
        self.events.append(("commit_push", message))


# ---------- project on disk ----------
def make_project(root, last_history_day="2026-11-06", n_days=30):
    root = Path(root)
    (root / "data" / "snapshots").mkdir(parents=True)
    (root / "calls").mkdir()
    (root / "config.json").write_text(json.dumps(
        {"tickers": TICKERS, "prompt_version": "v1", "model": "claude-haiku-5-5"}))
    rows, day, made = [], d(last_history_day), 0
    while made < n_days:
        if day.weekday() < 5:
            for t in TICKERS:
                rows.append((day.isoformat(), t, close_for(t, -0.1 * made)))
            made += 1
        day -= timedelta(days=1)
    with open(root / "data" / "history.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "ticker", "close"])
        w.writerows(sorted(rows))
    return root


def seed_call(root, day, fetch_time, p=0.6, prompt_version="v1"):
    """Write a finished day: snapshot, calls/<day>.json and an 'ok' log row."""
    root = Path(root)
    with open(root / "data" / "snapshots" / f"{day}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "close", "adj_close", "fetch_time", "split"])
        for t in TICKERS:
            w.writerow([t, close_for(t), close_for(t), fetch_time.isoformat(), 0.0])
    (root / "calls" / f"{day}.json").write_text(json.dumps({
        "day": day, "prompt": "seeded", "prompt_version": prompt_version,
        "model": "claude-haiku-5-5", "response_id": "msg_seed", "raw_output": good_reply(p=p),
        "called_at": fetch_time.isoformat(),
        "p_up": {t: p for t in TICKERS}, "base_rate": {t: 0.5 for t in TICKERS}}))
    log = root / "log.csv"
    new = not log.exists()
    with open(log, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["day", "ticker", "status"])
        w.writerow([day, "", "ok"])


def read_log(root):
    p = Path(root) / "log.csv"
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def read_scores(root):
    p = Path(root) / "scores.csv"
    if not p.exists():
        return []
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def tree_hash(root):
    """{relative path: sha256} of every file under root, to prove 'no file changed'."""
    root = Path(root)
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}
