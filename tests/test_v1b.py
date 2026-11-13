"""v1b (docs/v1b-plan.md, option A): the question becomes 'will X beat SPY tomorrow?'.
A benchmark is an extra ticker in the bars and in the history. It is never asked about."""
import unittest
from datetime import date

from bot.fetch import Bar
from bot.history import base_rate
from bot.prompt import build_prompt
from bot.score import score_day
from tests.helpers import d, utc


def _bar(close, split=0.0):
    return Bar(close=close, adj_close=close, fetch_time=utc("2026-11-10T22:30:00"), split=split)


class BenchmarkScore(unittest.TestCase):
    def _rows(self, stock_d1, spy_d1, spy_split=0.0):
        bars_d = {"AAPL": _bar(100.0), "SPY": _bar(100.0)}
        bars_d1 = {"AAPL": _bar(stock_d1), "SPY": _bar(spy_d1, spy_split)}
        return score_day({"AAPL": 0.6}, bars_d, bars_d1, benchmark="SPY")

    def test_stock_beats_spy_is_up_even_when_both_fall(self):
        self.assertEqual([(r.ticker, r.outcome) for r in self._rows(99.0, 98.0)], [("AAPL", "up")])

    def test_stock_lags_spy_is_down_even_when_both_rise(self):
        self.assertEqual([(r.ticker, r.outcome) for r in self._rows(101.0, 102.0)], [("AAPL", "down")])

    def test_equal_return_is_flat_and_left_out(self):
        self.assertEqual(self._rows(101.0, 101.0), [])

    def test_missing_benchmark_bar_leaves_every_ticker_out(self):
        bars_d = {"AAPL": _bar(100.0), "SPY": _bar(100.0)}
        self.assertEqual(score_day({"AAPL": 0.6}, bars_d, {"AAPL": _bar(101.0), "SPY": None}, benchmark="SPY"), [])

    def test_benchmark_split_leaves_every_ticker_out(self):
        self.assertEqual(self._rows(101.0, 100.0, spy_split=2.0), [])

    def test_no_benchmark_keeps_the_old_up_down_rule(self):
        rows = score_day({"AAPL": 0.6}, {"AAPL": _bar(100.0)}, {"AAPL": _bar(99.0)})
        self.assertEqual([r.outcome for r in rows], ["down"])


class BenchmarkBaseRate(unittest.TestCase):
    def test_share_of_days_the_stock_beat_spy_up_to_day_d(self):
        days = [date(2026, 11, n) for n in (2, 3, 4, 5, 6)]
        stock = list(zip(days, [100, 102, 101, 103, 200]))      # last close is after D: must be ignored
        spy = list(zip(days, [100, 101, 102, 102, 100]))
        # moves up to Nov 5: stock +2% vs spy +1% (beat), -0.98% vs +0.99% (lag), +1.98% vs 0% (beat) -> 2/3
        self.assertAlmostEqual(base_rate(stock, date(2026, 11, 5), benchmark_closes=spy), 2 / 3)

    def test_without_benchmark_it_is_the_old_up_rate(self):
        stock = [(date(2026, 11, n), c) for n, c in ((2, 10), (3, 11), (4, 10), (5, 12))]
        self.assertAlmostEqual(base_rate(stock, date(2026, 11, 5)), 2 / 3)


class BenchmarkPrompt(unittest.TestCase):
    def _prompt(self):
        days = [d("2026-11-05"), d("2026-11-06"), d("2026-11-09"), d("2026-11-10")]
        history = {"AAPL": list(zip(days, [10.0, 11.0, 12.0, 13.0])),
                   "SPY": list(zip(days, [500.0, 501.0, 502.0, 503.0]))}
        return build_prompt(history, ["AAPL"], d("2026-11-09"), "v2", benchmark="SPY")

    def test_spy_closes_are_listed_and_the_question_is_about_beating_spy(self):
        text = self._prompt()
        self.assertIn("SPY: 500.00, 501.00, 502.00", text)
        self.assertIn("SPY", text.split("For each stock")[1])
        self.assertIn("AAPL: 10.00, 11.00, 12.00", text)

    def test_nothing_after_day_d_leaks_for_either_series(self):
        text = self._prompt()
        self.assertNotIn("13.00", text)
        self.assertNotIn("503.00", text)


# ---------- runner wiring ----------
import csv
import json
import tempfile
from pathlib import Path

from bot.runner import Deps, run
from tests.helpers import (TICKERS, FakeFetch, FakeGit, FakeLLM, make_project, read_log, read_scores,
                           seed_call)


class SpyFetch(FakeFetch):
    """FakeFetch plus a SPY bar (None when spy_close is None)."""

    def __init__(self, spy_close=1000.0, **kw):
        super().__init__(**kw)
        self.spy_close = spy_close

    def __call__(self, tickers, day, now):
        stocks = [t for t in tickers if t != "SPY"]
        out = super().__call__(stocks, day, now)
        if "SPY" in tickers:
            out["SPY"] = None if self.spy_close is None else Bar(
                close=self.spy_close, adj_close=self.spy_close, fetch_time=now)
        return out


def _stamp_benchmark(root, day, benchmark):
    path = Path(root) / "calls" / f"{day}.json"
    record = json.loads(path.read_text())
    record["benchmark"] = benchmark
    path.write_text(json.dumps(record))


def _spy_project(tmp):
    root = make_project(Path(tmp) / "p")
    config = json.loads((root / "config.json").read_text())
    config.update(benchmark="SPY", prompt_version="v2")
    (root / "config.json").write_text(json.dumps(config))
    with open(root / "data" / "history.csv", newline="") as f:
        dates = sorted({row["date"] for row in csv.DictReader(f)})
    with open(root / "data" / "history.csv", "a", newline="") as f:
        csv.writer(f).writerows((day, "SPY", 1000.0 + i) for i, day in enumerate(dates))
    seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"), prompt_version="v2")
    _stamp_benchmark(root, "2026-11-09", "SPY")        # a v2 call records the benchmark it was made under
    with open(root / "data" / "snapshots" / "2026-11-09.csv", "a", newline="") as f:
        csv.writer(f).writerow(["SPY", 1000.0, 1000.0, utc("2026-11-09T22:30:00").isoformat(), 0.0])
    return root


class BenchmarkRun(unittest.TestCase):
    def _run(self, spy_close):
        with tempfile.TemporaryDirectory() as tmp:
            root = _spy_project(tmp)
            llm = FakeLLM()
            run(utc("2026-11-10T22:30:00"), root, Deps(
                fetch=SpyFetch(spy_close=spy_close, add=1.0), llm=llm, git=FakeGit()))
            return {"llm": llm, "snapshot": (root / "data" / "snapshots" / "2026-11-10.csv").read_text(),
                    "call": (root / "calls" / "2026-11-10.json").exists() and json.loads(
                        (root / "calls" / "2026-11-10.json").read_text()),
                    "scores": read_scores(root), "log": read_log(root)}

    def test_spy_is_fetched_and_in_the_prompt_but_never_asked_about(self):
        got = self._run(1000.0)
        self.assertIn("SPY,", got["snapshot"])
        self.assertIn("SPY: ", got["llm"].prompts[0])
        self.assertEqual(sorted(got["call"]["p_up"]), sorted(TICKERS))
        self.assertEqual(sorted(got["call"]["base_rate"]), sorted(TICKERS))

    def test_yesterdays_call_is_scored_against_spy(self):
        got = self._run(1500.0)                      # SPY +50% overnight, every stock about +1%
        self.assertEqual(len(got["scores"]), len(TICKERS))
        self.assertTrue(all(r["outcome"] == "down" and r["prompt_version"] == "v2" for r in got["scores"]))

    def test_no_spy_bar_means_no_call_and_a_log_row(self):
        got = self._run(None)
        self.assertFalse(got["call"])
        self.assertEqual(got["llm"].prompts, [])
        self.assertIn(("2026-11-10", "SPY", "no data"),
                      [(r["day"], r["ticker"], r["status"]) for r in got["log"]])

    def test_a_call_made_without_a_benchmark_is_scored_up_down_after_the_config_flips(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _spy_project(tmp)
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"), prompt_version="v1")   # no benchmark field
            with open(root / "data" / "snapshots" / "2026-11-09.csv", "a", newline="") as f:
                csv.writer(f).writerow(["SPY", 1000.0, 1000.0, utc("2026-11-09T22:30:00").isoformat(), 0.0])
            run(utc("2026-11-10T22:30:00"), root, Deps(
                fetch=SpyFetch(spy_close=1500.0, add=1.0), llm=FakeLLM(), git=FakeGit()))
            rows = read_scores(root)
        self.assertEqual(len(rows), len(TICKERS))
        self.assertTrue(all(r["outcome"] == "up" and r["prompt_version"] == "v1" for r in rows))


if __name__ == "__main__":
    unittest.main()
