"""Tests 16-18: price fetching."""
import tempfile
import unittest
from pathlib import Path

from bot.fetch import Bar, PartialBarError, fetch_bars
from bot.runner import Deps, run
from tests.helpers import (TICKERS, FakeFetch, FakeGit, FakeLLM, d, make_project,
                           read_log, utc)

DAY = d("2026-11-13")                       # a Friday; close is 21:00 UTC
AFTER_CLOSE = utc("2026-11-13T22:30:00")


def _bars(missing=()):
    return {t: (None if t in missing else
                Bar(close=100.0, adj_close=100.0, fetch_time=AFTER_CLOSE)) for t in TICKERS}


class Fetch(unittest.TestCase):
    def test_16_raises_twice_then_works_data_stored_after_retries(self):
        calls, sleeps = [], []

        def download(tickers):
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("blocked")
            return _bars()

        out = fetch_bars(TICKERS, DAY, AFTER_CLOSE, download, sleep=sleeps.append)
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(sleeps), 2)
        self.assertGreater(sleeps[1], sleeps[0])               # backoff grows
        self.assertTrue(all(out[t] is not None for t in TICKERS))

    def test_17_one_empty_ticker_is_no_data_and_the_other_9_are_still_called(self):
        out = fetch_bars(TICKERS, DAY, AFTER_CLOSE, lambda tk: _bars(missing=["MSFT"]),
                         sleep=lambda s: None)
        self.assertIsNone(out["MSFT"])
        self.assertEqual(sum(v is not None for v in out.values()), 9)

        with tempfile.TemporaryDirectory() as tmp:             # and the full run
            root = make_project(Path(tmp) / "p")
            deps = Deps(fetch=FakeFetch(missing=["MSFT"]), llm=FakeLLM(), git=FakeGit())
            run(utc("2026-11-10T22:30:00"), root, deps)
            self.assertEqual(len(deps.llm.prompts), 1)         # the LLM was still asked
            self.assertNotIn("MSFT", deps.llm.prompts[0])      # but only about the 9 with data
            rows = [r for r in read_log(root) if r["status"] == "no data"]
            self.assertEqual([r["ticker"] for r in rows], ["MSFT"])

    def test_18_partial_live_bar_is_rejected(self):
        before_close = utc("2026-11-13T18:00:00")              # 13:00 New York, market still open
        with self.assertRaises(PartialBarError):
            fetch_bars(TICKERS, DAY, before_close, lambda tk: _bars(), sleep=lambda s: None)
        just_after = utc("2026-11-13T21:05:00")                # 5 minutes after the close: fine
        out = fetch_bars(TICKERS, DAY, just_after, lambda tk: _bars(), sleep=lambda s: None)
        self.assertEqual(len(out), 10)


if __name__ == "__main__":
    unittest.main()
