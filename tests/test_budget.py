"""Extra tests (not in the design's 28): the bot must never spend more on the API than its monthly budget."""
import csv
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from bot import budget
from bot.llm import LLMReply
from bot.runner import Deps, run
from tests.helpers import FakeFetch, FakeGit, FakeLLM, good_reply, make_project, read_log, utc

MODEL = "claude-haiku-5-5"


def _reply(inp, out):
    return LLMReply(text="{}", stop_reason="end_turn", response_id="m", model=MODEL,
                    input_tokens=inp, output_tokens=out)


def _usage_rows(root):
    path = Path(root) / "usage.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _write_usage(root, rows):
    with open(Path(root) / "usage.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(budget.USAGE_FIELDS)
        w.writerows(rows)


def _run(root, llm=None, env=None):
    deps = Deps(fetch=FakeFetch(), llm=llm or FakeLLM(), git=FakeGit())
    with mock.patch.dict(os.environ, env or {}):
        run(utc("2026-11-10T22:30:00"), root, deps)
    return deps


class Costs(unittest.TestCase):
    def test_haiku_prices_and_unknown_models_are_refused(self):
        self.assertAlmostEqual(budget.cost_usd(MODEL, 1_000_000, 1_000_000), 0.10 + 0.50)
        self.assertAlmostEqual(budget.cost_usd(MODEL, 500, 100), 0.0001)
        with self.assertRaises(ValueError):                       # fail closed: never guess a price
            budget.cost_usd("claude-some-new-model", 1, 1)

    def test_only_the_current_months_rows_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_usage(tmp, [["2026-10-30", "v1", MODEL, 1, 1, 5.0], ["2026-11-02", "v1", MODEL, 1, 1, 0.05],
                               ["2026-11-09", "v1", MODEL, 1, 1, 0.02]])
            self.assertAlmostEqual(budget.month_spent(Path(tmp), date(2026, 11, 12)), 0.07)

    def test_budget_comes_from_the_environment_and_an_empty_value_means_the_default(self):
        with mock.patch.dict(os.environ, {"BOT_MONTHLY_BUDGET_USD": ""}):
            self.assertEqual(budget.monthly_budget(), budget.DEFAULT_BUDGET_USD)
        with mock.patch.dict(os.environ, {"BOT_MONTHLY_BUDGET_USD": "1.5"}):
            self.assertEqual(budget.monthly_budget(), 1.5)


class InTheDailyRun(unittest.TestCase):
    def test_every_reply_is_recorded_with_its_tokens_and_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            bad = '{"AAPL": 0.5}'                                  # invalid: forces the one retry
            _run(root, FakeLLM([bad, good_reply()], usage=(500, 100)))
            rows = _usage_rows(root)
            self.assertEqual(len(rows), 2)                         # both tries were billed
            self.assertEqual((rows[0]["day"], rows[0]["input_tokens"], rows[0]["output_tokens"]),
                             ("2026-11-10", "500", "100"))
            self.assertAlmostEqual(float(rows[0]["cost_usd"]), 0.0001)

    def test_a_zero_budget_pauses_the_llm_and_says_so_in_the_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            deps = _run(root, env={"BOT_MONTHLY_BUDGET_USD": "0"})
            self.assertEqual(deps.llm.prompts, [])
            self.assertFalse((root / "calls" / "2026-11-10.json").exists())   # a later re-run may still call
            self.assertEqual([r["status"] for r in read_log(root) if r["day"] == "2026-11-10"], ["budget"])
            self.assertEqual(_usage_rows(root), [])

    def test_the_report_shows_the_estimated_spend_and_the_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            _run(root, FakeLLM(usage=(500, 100)), env={"BOT_MONTHLY_BUDGET_USD": "0.25"})
            text = (root / "report.md").read_text()
            self.assertIn("API spend this month (estimate from token counts): $0.0001 of $0.25 budget", text)

    def test_a_nearly_used_up_month_blocks_the_call_but_last_months_spend_does_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            _write_usage(root, [["2026-11-02", "v1", MODEL, 1, 1, 0.249]])    # 0.001 left < one worst case
            blocked = _run(root, env={"BOT_MONTHLY_BUDGET_USD": "0.25"})
            self.assertEqual(blocked.llm.prompts, [])
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            _write_usage(root, [["2026-10-02", "v1", MODEL, 1, 1, 5.0]])      # last month, ignored
            allowed = _run(root, env={"BOT_MONTHLY_BUDGET_USD": "0.25"})
            self.assertEqual(len(allowed.llm.prompts), 1)


if __name__ == "__main__":
    unittest.main()
