"""Extra tests (not in the design's 28): the two scoring decisions made on 12.11.2026.
1. A ticker with a stock split on D+1 is left out of that day's scoring (its two prices are on different scales).
2. A late day makes no call, but it still fetches and scores the previous day's call."""
import tempfile
import unittest
from pathlib import Path

from bot.fetch import Bar
from bot.runner import Deps, run
from bot.score import score_day
from tests.helpers import (TICKERS, FakeFetch, FakeGit, FakeLLM, d, make_project, read_log,
                           read_scores, seed_call, utc)


def _bar(close, split=0.0):
    return Bar(close=close, adj_close=close, fetch_time=utc("2026-11-10T22:30:00"), split=split)


class SplitDays(unittest.TestCase):
    def test_a_split_on_the_next_day_leaves_that_ticker_unscored(self):
        p_up = {"AAPL": 0.6, "MSFT": 0.6}
        bars_d = {"AAPL": _bar(400.0), "MSFT": _bar(100.0)}
        bars_d1 = {"AAPL": _bar(101.0, split=4.0), "MSFT": _bar(101.0)}    # AAPL 4-for-1: 400 -> ~100
        rows = score_day(p_up, bars_d, bars_d1)
        self.assertEqual([r.ticker for r in rows], ["MSFT"])

    def test_in_a_daily_run_the_split_ticker_has_no_score_row_and_the_others_do(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))
            deps = Deps(fetch=FakeFetch(add=1.0, splits={"AAPL": 4.0}), llm=FakeLLM(), git=FakeGit())
            run(utc("2026-11-10T22:30:00"), root, deps)
            scored = {r["ticker"] for r in read_scores(root) if r["day"] == "2026-11-09"}
            self.assertEqual(scored, set(TICKERS) - {"AAPL"})
            self.assertIn(("AAPL", "split"), [(r["ticker"], r["status"]) for r in read_log(root)])


class LateDays(unittest.TestCase):
    def test_a_late_day_makes_no_call_but_still_scores_the_previous_days_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))        # Monday's call exists
            deps = Deps(fetch=FakeFetch(add=1.0), llm=FakeLLM(), git=FakeGit())
            # Tuesday's run starts Wednesday 15:00 UTC, after Wednesday's open (14:30 UTC): too late to call.
            run(utc("2026-11-11T15:00:00"), root, deps, day=d("2026-11-10"))
            self.assertEqual(deps.llm.prompts, [])                           # still no call
            self.assertFalse((root / "calls" / "2026-11-10.json").exists())
            self.assertEqual([r["status"] for r in read_log(root) if r["day"] == "2026-11-10"], ["late"])
            self.assertEqual(len([r for r in read_scores(root) if r["day"] == "2026-11-09"]), 10)


class FailureStaysVisible(unittest.TestCase):
    def test_a_commit_error_during_a_failed_day_keeps_the_original_error_in_the_chain(self):
        class BrokenGit:
            def commit_push(self, message):
                raise OSError("push failed")

        def broken_llm(prompt, tickers=None):
            raise RuntimeError("API timeout")

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            with self.assertRaises(OSError) as caught:
                run(utc("2026-11-10T22:30:00"), root, Deps(fetch=FakeFetch(), llm=broken_llm, git=BrokenGit()))
        self.assertIsInstance(caught.exception.__context__, RuntimeError)   # the CI log shows both errors


if __name__ == "__main__":
    unittest.main()
