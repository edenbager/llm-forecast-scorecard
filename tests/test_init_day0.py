"""Extra tests (not in the design's 28): the one-time day-0 setup (frozen tickers + 1 year of closes)."""
import csv
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from bot import store
from bot.init_day0 import DAY0_TICKERS, build_config, check_day_closed, write_day0
from bot.yahoo import closes_from_frame


def _frame(rows):
    """rows: {ticker: [closes]} on consecutive days from 2026-01-05, as a yfinance-style table."""
    n = max(len(v) for v in rows.values())
    index = pd.DatetimeIndex([date(2026, 1, 5) + timedelta(days=i) for i in range(n)], name="Date")
    data = {(t, "Close"): closes + [float("nan")] * (n - len(closes)) for t, closes in rows.items()}
    return pd.DataFrame(data, index=index)


def _closes(n, last=date(2026, 11, 11)):
    """n consecutive daily closes ending on `last` (day 0 by default)."""
    return [(last - timedelta(days=n - 1 - i), 100.0 + i) for i in range(n)]


class Day0(unittest.TestCase):
    def test_the_frozen_list_is_ten_companies_with_one_alphabet_class(self):
        self.assertEqual(DAY0_TICKERS, ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL",
                                        "AVGO", "META", "LLY", "TSLA", "BRK-B"])
        self.assertNotIn("GOOG", DAY0_TICKERS)

    def test_closes_come_out_per_ticker_without_empty_days(self):
        frame = _frame({"AAPL": [1.0, 2.0, float("nan"), 4.0], "MSFT": [5.0, 6.0]})
        out = closes_from_frame(frame, ["AAPL", "MSFT", "ZZZZ"])
        self.assertEqual([c for _, c in out["AAPL"]], [1.0, 2.0, 4.0])
        self.assertEqual([c for _, c in out["MSFT"]], [5.0, 6.0])
        self.assertEqual(out["ZZZZ"], [])

    def test_config_records_what_was_frozen_and_where_the_weights_came_from(self):
        cfg = build_config(date(2026, 11, 11))
        self.assertEqual(cfg["tickers"], DAY0_TICKERS)
        self.assertEqual((cfg["prompt_version"], cfg["model"], cfg["day0"]),
                         ("v1", "claude-haiku-5-5", "2026-11-11"))
        self.assertIn("2026-11-11", cfg["weights_as_of"])
        self.assertTrue(cfg["weights_source"])

    def test_files_are_written_readable_by_the_bot_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            closes = {t: _closes(30) for t in DAY0_TICKERS}
            write_day0(root, build_config(date(2026, 11, 11)), closes)
            self.assertEqual(json.loads((root / "config.json").read_text())["tickers"], DAY0_TICKERS)
            history = store.load_history(root)
            self.assertEqual(sorted(history), sorted(DAY0_TICKERS))
            self.assertEqual(len(history["AAPL"]), 30)
            before = (root / "config.json").read_bytes(), (root / "data" / "history.csv").read_bytes()
            with self.assertRaises(FileExistsError):                  # day 0 is committed once
                write_day0(root, build_config(date(2026, 11, 11)), closes)
            after = (root / "config.json").read_bytes(), (root / "data" / "history.csv").read_bytes()
            self.assertEqual(before, after)

    def test_a_ticker_with_too_little_history_is_refused_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            closes = {t: _closes(30) for t in DAY0_TICKERS}
            closes["LLY"] = _closes(5)                                # a prompt needs 20 closes + 1
            with self.assertRaises(ValueError):
                write_day0(Path(tmp), build_config(date(2026, 11, 11)), closes)
            self.assertEqual(list(Path(tmp).iterdir()), [])


    def test_history_must_end_on_day0_and_day0_must_be_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = {t: _closes(30, last=date(2026, 11, 10)) for t in DAY0_TICKERS}   # one day short
            with self.assertRaises(ValueError):
                write_day0(Path(tmp), build_config(date(2026, 11, 11)), stale)
            self.assertEqual(list(Path(tmp).iterdir()), [])
        with self.assertRaises(ValueError):                       # 11 Nov closes at 21:00 UTC
            check_day_closed(date(2026, 11, 11), datetime(2026, 11, 11, 18, 0, tzinfo=timezone.utc))
        check_day_closed(date(2026, 11, 11), datetime(2026, 11, 11, 21, 5, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
