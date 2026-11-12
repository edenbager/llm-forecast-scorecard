"""Extra tests (not in the design's 28): bugs found by the second code review, 12.11.2026."""
import json
import re
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from bot.fetch import Bar, fetch_bars
from bot.llm import make_llm
from bot.prompt import build_prompt
from bot.validate import InvalidCall, parse_and_validate
from bot.yahoo import NoDataError, ensure_some_data
from tests.helpers import TICKERS, d, utc

ROOT = Path(__file__).resolve().parent.parent


class EmptyYahooReply(unittest.TestCase):
    def test_a_reply_with_no_data_for_any_ticker_is_an_error_not_a_quiet_empty_day(self):
        bar = Bar(close=1.0, adj_close=1.0, fetch_time=utc("2026-11-10T22:30:00"))
        with self.assertRaises(NoDataError):
            ensure_some_data({"AAPL": None, "MSFT": None})
        self.assertEqual(ensure_some_data({"AAPL": bar, "MSFT": None})["AAPL"], bar)

    def test_it_is_retried_and_then_fails_loud(self):
        calls = []

        def download(tickers):
            calls.append(1)
            return ensure_some_data({t: None for t in tickers})
        with self.assertRaises(NoDataError):
            fetch_bars(["AAPL"], d("2026-11-13"), utc("2026-11-13T22:30:00"), download, sleep=lambda s: None)
        self.assertEqual(len(calls), 3)


class GapsInThePrompt(unittest.TestCase):
    DAYS = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06",
            "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12"]       # all trading days

    def _prompt(self, skip=None):
        full = [(d(s), 100.0 + i) for i, s in enumerate(self.DAYS)]
        gappy = [row for row in full if row[0] != skip]
        return build_prompt({"AAPL": gappy, "MSFT": full}, ["AAPL", "MSFT"], d("2026-11-12"), "v1")

    def test_a_missing_trading_day_is_marked_where_it_is_and_nowhere_else(self):
        lines = dict(line.split(":", 1) for line in self._prompt(skip=d("2026-11-09")).splitlines()
                     if line.startswith(("AAPL:", "MSFT:")))
        self.assertEqual(lines["AAPL"].count("|"), 1)
        self.assertRegex(lines["AAPL"], r"104\.00 \| 106\.00")               # between 6 Nov and 10 Nov
        self.assertEqual(lines["MSFT"].count("|"), 0)

    def test_with_no_gap_there_is_no_marker(self):
        body = "\n".join(l for l in self._prompt().splitlines() if l.startswith(("AAPL:", "MSFT:")))
        self.assertNotIn("|", body)


class DuplicateKeys(unittest.TestCase):
    def test_an_object_reply_with_a_repeated_ticker_is_invalid(self):
        text = '{"AAPL": 0.5, "AAPL": 0.6, ' + ", ".join(f'"{t}": 0.5' for t in TICKERS[1:]) + "}"
        with self.assertRaises(InvalidCall):
            parse_and_validate(text, TICKERS)


class ApiClient(unittest.TestCase):
    def test_client_is_built_once_with_extra_retries(self):
        reply = SimpleNamespace(content=[SimpleNamespace(type="text", text="{}")],
                                stop_reason="end_turn", id="m", model="x",
                                usage=SimpleNamespace(input_tokens=1, output_tokens=1))
        with mock.patch("bot.llm.anthropic.Anthropic") as anthropic_cls:
            anthropic_cls.return_value.messages.create.return_value = reply
            llm = make_llm("claude-haiku-5-5")
            llm("p", ["AAPL"])
            llm("p", ["AAPL"])
        anthropic_cls.assert_called_once_with(max_retries=4)      # the SDK default is 2


class RepoHygiene(unittest.TestCase):
    def test_temp_files_are_ignored_by_git(self):
        self.assertIn("*.tmp", (ROOT / ".gitignore").read_text().splitlines())

    def test_workflow_runs_the_tests_before_the_bot(self):
        text = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
        self.assertLess(text.index("unittest discover"), text.index("python -m bot"))


if __name__ == "__main__":
    unittest.main()
