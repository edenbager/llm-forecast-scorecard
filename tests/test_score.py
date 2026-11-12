"""Tests 19-23: turning a call plus what really happened into a score."""
import tempfile
import unittest
from pathlib import Path

from bot.fetch import Bar
from bot.runner import Deps, run
from bot.score import label, score_day
from bot.stats import Row, brier, hit_rate
from tests.helpers import (TICKERS, FakeFetch, FakeGit, FakeLLM, make_project, read_log,
                           seed_call, utc)


def _bar(close, adj=None):
    return Bar(close=close, adj_close=close if adj is None else adj, fetch_time=utc("2026-11-10T22:30:00"))


class Score(unittest.TestCase):
    def test_19_up_down_flat_and_flat_is_excluded(self):
        self.assertEqual(label(100.0, 101.0), "up")
        self.assertEqual(label(100.0, 99.0), "down")
        self.assertEqual(label(100.0, 100.0), "flat")
        rows = score_day({"AAPL": 0.6}, {"AAPL": _bar(100.0)}, {"AAPL": _bar(100.0)})
        self.assertEqual(rows, [])                             # flat close is not scored

    def test_20_p_up_half_is_out_of_hit_rate_but_in_brier(self):
        rows = [Row(0.5, "up"), Row(0.7, "up"), Row(0.3, "down")]
        rate, n = hit_rate(rows)
        self.assertEqual((rate, n), (1.0, 2))                  # the 0.5 call is skipped
        self.assertAlmostEqual(brier(rows), (0.25 + 0.09 + 0.09) / 3)

    def test_21_ex_dividend_day_is_scored_on_close_not_adjusted_close(self):
        # Close fell 100.00 -> 99.60 (a 0.50 dividend was paid). Adjusted closes rose 99.50 -> 99.60.
        bar_d, bar_d1 = _bar(100.00, adj=99.50), _bar(99.60, adj=99.60)
        rows = score_day({"AAPL": 0.6}, {"AAPL": bar_d}, {"AAPL": bar_d1})
        self.assertEqual([(r.ticker, r.outcome) for r in rows], [("AAPL", "down")])

    def test_22_one_ticker_missing_at_next_day_is_unscored_others_scored(self):
        p_up = {t: 0.6 for t in TICKERS}
        bars_d = {t: _bar(100.0) for t in TICKERS}
        bars_d1 = {t: _bar(101.0) for t in TICKERS}
        bars_d1["NVDA"] = None
        rows = score_day(p_up, bars_d, bars_d1)
        self.assertEqual(len(rows), 9)
        self.assertNotIn("NVDA", [r.ticker for r in rows])
        self.assertTrue(all(r.outcome == "up" for r in rows))

    def test_23_split_day_history_untouched_and_split_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))
            history_before = (root / "data" / "history.csv").read_bytes()
            deps = Deps(fetch=FakeFetch(add=1.0, splits={"AAPL": 4.0}), llm=FakeLLM(), git=FakeGit())
            self.assertEqual(run(utc("2026-11-10T22:30:00"), root, deps), 0)
            self.assertEqual((root / "data" / "history.csv").read_bytes(), history_before)
            noted = [r for r in read_log(root) if r["status"] == "split"]
            self.assertEqual([r["ticker"] for r in noted], ["AAPL"])


if __name__ == "__main__":
    unittest.main()
