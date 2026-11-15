"""Watchdog: a day after a trading day, the call file must exist and match config.json.
Run by .github/workflows/watchdog.yml; a problem fails the job and opens an issue."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from bot import store
from bot.score import ScoredRow
from bot.watchdog import check
from tests.helpers import make_project, seed_call, utc

MONDAY_CALL = "2026-11-09"          # a trading day; the watchdog looks at it on Tuesday 10.11


def _project(tmp, **config_changes):
    root = make_project(Path(tmp) / "p")
    config = json.loads((root / "config.json").read_text())
    config.update(config_changes)
    (root / "config.json").write_text(json.dumps(config))
    return root


class Watchdog(unittest.TestCase):
    def test_a_good_call_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            seed_call(root, MONDAY_CALL, utc("2026-11-09T22:40:00"))
            self.assertIsNone(check(root, date(2026, 11, 10)))

    def test_a_missing_call_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            self.assertIn("no call", check(root, date(2026, 11, 10)))

    def test_a_non_trading_day_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            self.assertIsNone(check(root, date(2026, 11, 15)))      # Sunday: Saturday had no run

    def test_a_call_with_no_probabilities_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            seed_call(root, MONDAY_CALL, utc("2026-11-09T22:40:00"))
            path = root / "calls" / f"{MONDAY_CALL}.json"
            record = json.loads(path.read_text())
            record["p_up"] = None
            path.write_text(json.dumps(record))
            self.assertIn("no probabilities", check(root, date(2026, 11, 10)))

    def test_a_call_from_another_prompt_version_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, prompt_version="v2")
            seed_call(root, MONDAY_CALL, utc("2026-11-09T22:40:00"), prompt_version="v1")
            self.assertIn("prompt_version", check(root, date(2026, 11, 10)))

    def test_a_call_made_without_the_configured_benchmark_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, benchmark="SPY")
            seed_call(root, MONDAY_CALL, utc("2026-11-09T22:40:00"))     # seed has no benchmark field
            self.assertIn("benchmark", check(root, date(2026, 11, 10)))


class WatchdogScoring(unittest.TestCase):
    """15.11: the run on day D scores the call of the trading day before. Nothing checked that it did."""

    def _two_calls(self, tmp):
        root = _project(tmp)
        seed_call(root, "2026-11-09", utc("2026-11-09T22:40:00"))        # Monday
        seed_call(root, "2026-11-10", utc("2026-11-10T22:40:00"))        # Tuesday
        return root

    def test_an_unscored_earlier_call_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._two_calls(tmp)
            self.assertIn("not scored", check(root, date(2026, 11, 11)))      # Wednesday morning

    def test_a_scored_earlier_call_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._two_calls(tmp)
            store.add_scores(root, date(2026, 11, 9), "v1", [ScoredRow("AAPL", 0.6, "up")])
            self.assertIsNone(check(root, date(2026, 11, 11)))

    def test_no_earlier_call_means_nothing_to_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp)
            seed_call(root, "2026-11-10", utc("2026-11-10T22:40:00"))
            self.assertIsNone(check(root, date(2026, 11, 11)))


if __name__ == "__main__":
    unittest.main()
