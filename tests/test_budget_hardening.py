"""Extra tests (not in the design's 28): money-safety fixes from the code review of the spending guard."""
import contextlib
import csv
import io
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bot import budget
from bot.llm import CLIENT_RETRIES, MAX_TOKENS, LLMReply
from bot.caller import MAX_TRIES
from bot.report import build_report
from bot.runner import Deps, run
from tests.helpers import FakeFetch, FakeGit, FakeLLM, make_project, read_log, utc

MODEL = "claude-haiku-5-5"


def _usage_rows(root):
    path = Path(root) / "usage.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


class RaisesOnSecondCall:
    """First call: an invalid but billed reply. Second call: the API fails (timeout, 5xx, ...)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, prompt, tickers=None):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("API timeout")
        return LLMReply(text='{"AAPL": 0.5}', stop_reason="end_turn", response_id="m", model=MODEL,
                        input_tokens=500, output_tokens=100)


class PaidCallsAreNeverLost(unittest.TestCase):
    def _run(self, llm, patch=None):
        git = FakeGit()
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            with contextlib.ExitStack() as stack:
                if patch:
                    stack.enter_context(patch)
                with self.assertRaises((RuntimeError, OSError)):
                    run(utc("2026-11-10T22:30:00"), root, Deps(fetch=FakeFetch(), llm=llm, git=git))
            return _usage_rows(root), git.events

    def test_a_billed_reply_is_ledgered_even_when_the_next_call_fails_and_the_run_still_commits(self):
        rows, git_events = self._run(RaisesOnSecondCall())
        self.assertEqual(len(rows), 1)                                   # the first reply was billed
        self.assertEqual((rows[0]["input_tokens"], rows[0]["output_tokens"]), ("500", "100"))
        self.assertTrue(any(e[0] == "commit_push" for e in git_events))  # so the ledger reaches the repo

    def test_a_failure_after_the_call_still_leaves_the_spend_in_the_ledger_and_commits(self):
        rows, git_events = self._run(FakeLLM(usage=(500, 100)),
                                     patch=mock.patch("bot.runner.store.write_call", side_effect=OSError("disk")))
        self.assertEqual(len(rows), 1)
        self.assertTrue(any(e[0] == "commit_push" for e in git_events))


class Estimates(unittest.TestCase):
    def test_worst_case_counts_every_try_every_sdk_retry_the_output_cap_and_a_safe_input_estimate(self):
        expected = MAX_TRIES * (CLIENT_RETRIES + 1) * budget.cost_usd(
            MODEL, 1000 / budget.CHARS_PER_TOKEN + budget.OVERHEAD_TOKENS, MAX_TOKENS)
        self.assertAlmostEqual(budget.worst_case_cost(MODEL, "x" * 1000), expected)
        self.assertLessEqual(budget.CHARS_PER_TOKEN, 2)                  # number-heavy text: ~2 chars/token

    def test_a_bad_budget_value_means_zero_not_a_crash_and_not_unlimited(self):
        for raw in ["$5", "5 USD", "inf", "nan", "-1", "abc"]:
            with self.subTest(raw), mock.patch.dict(os.environ, {"BOT_MONTHLY_BUDGET_USD": raw}), \
                    contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(budget.monthly_budget(), 0.0)
                self.assertIn("BOT_MONTHLY_BUDGET_USD", err.getvalue())

    def test_a_damaged_ledger_row_is_a_clear_error_that_names_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(Path(tmp) / "usage.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(budget.USAGE_FIELDS)
                w.writerow(["2026-11-02", "v1", MODEL, 1, 1, ""])
            with self.assertRaisesRegex(ValueError, "usage.csv"):
                budget.month_spent(Path(tmp), date(2026, 11, 12))


class LogAndReport(unittest.TestCase):
    def _log(self, root, rows):
        with open(Path(root) / "log.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["day", "ticker", "status"])
            w.writerows(rows)

    def test_a_day_blocked_by_the_budget_and_called_later_counts_once_as_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            self._log(root, [["2026-11-10", "", "budget"], ["2026-11-10", "", "ok"],
                             ["2026-11-10", "MSFT", "no data"]])
            text = build_report(root)
        self.assertIn("ok 1", text)
        self.assertIn("budget 0", text)
        self.assertIn("no data 1", text)                                 # ticker-level rows still count

    def test_a_blocked_day_refreshes_the_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            with mock.patch.dict(os.environ, {"BOT_MONTHLY_BUDGET_USD": "0"}):
                run(utc("2026-11-10T22:30:00"), root, Deps(fetch=FakeFetch(), llm=FakeLLM(), git=FakeGit()))
            self.assertIn("budget 1", (root / "report.md").read_text())


if __name__ == "__main__":
    unittest.main()
