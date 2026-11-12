"""Extra tests (not in the design's 28): the report.md the daily run writes. Design: 'Report (weekly report.md)'."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import contextlib
import io

from bot.report import FIXED_LINE, build_report, load_rows, write_report
from bot.runner import Deps, run
from tests.helpers import FakeFetch, FakeGit, FakeLLM, make_project, seed_call, utc


def _project(tmp, scored):
    """scored: [(day, version, ticker, p_up, outcome, base_p)] written as scores.csv + calls/<day>.json."""
    root = make_project(Path(tmp) / "p")
    with open(root / "scores.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["day", "prompt_version", "ticker", "p_up", "outcome"])
        for day, version, ticker, p, outcome, _ in scored:
            w.writerow([day, version, ticker, p, outcome])
    for day in {s[0] for s in scored}:
        (root / "calls" / f"{day}.json").write_text(json.dumps(
            {"day": day, "prompt_version": "x",
             "base_rate": {s[2]: s[5] for s in scored if s[0] == day}}))
    return root


TWO_DAYS = [("2026-11-09", "v1", "AAPL", 0.8, "up", 0.5),     # LLM 0.04 vs base 0.25
            ("2026-11-10", "v1", "AAPL", 0.2, "up", 0.5)]     # LLM 0.64 vs base 0.25


class ReportFile(unittest.TestCase):
    def test_rows_carry_the_baseline_stored_on_the_day_of_the_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = load_rows(_project(tmp, TWO_DAYS))
            self.assertEqual([(r.p_up, r.base_p, r.outcome, r.prompt_version) for r in rows],
                             [(0.8, 0.5, "up", "v1"), (0.2, 0.5, "up", "v1")])

    def test_numbers_match_a_hand_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = build_report(_project(tmp, TWO_DAYS))
        self.assertIn(FIXED_LINE, text)
        self.assertIn("n_days: 2", text)
        self.assertIn("calls scored: 2", text)
        self.assertIn("LLM 0.340", text)                          # (0.04 + 0.64) / 2
        self.assertIn("base_rate 0.250", text)
        self.assertIn("always 0.5: 0.250", text)
        self.assertIn("+0.090", text)                             # mean of (-0.21, +0.39)
        self.assertIn("interval needs 20+ days", text)            # 2 days is too few to show an interval
        self.assertIn("hidden", text)                             # every calibration bucket has n < 30

    def test_two_versions_get_two_sections(self):
        rows = TWO_DAYS + [("2026-11-09", "v2", "MSFT", 0.9, "down", 0.5)]
        with tempfile.TemporaryDirectory() as tmp:
            text = build_report(_project(tmp, rows))
        self.assertIn("## Prompt version v1", text)
        self.assertIn("## Prompt version v2", text)

    def test_no_scores_yet_still_gives_the_log_counts_and_the_fixed_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))
            with open(root / "log.csv", "a", newline="") as f:
                csv.writer(f).writerows([["2026-11-10", "", "no run"], ["2026-11-11", "MSFT", "no data"]])
            text = build_report(root)
        self.assertIn("No scored days yet", text)
        self.assertIn("no run 1", text)
        self.assertIn("no data 1", text)
        self.assertIn("ok 1", text)                               # calls made are counted too
        self.assertIn(FIXED_LINE, text)

    def test_one_scored_day_has_no_interval_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = build_report(_project(tmp, TWO_DAYS[:1]))
        self.assertIn("interval needs 20+ days", text)

    def test_with_20_scored_days_the_interval_is_shown(self):
        rows = [(f"2026-10-{i + 1:02d}", "v1", "AAPL", 0.6 if i % 2 else 0.4, "up" if i % 3 else "down", 0.5)
                for i in range(20)]
        with tempfile.TemporaryDirectory() as tmp:
            text = build_report(_project(tmp, rows))
        self.assertIn("n_days: 20", text)
        self.assertIn("95% stationary-bootstrap interval", text)

    def test_a_scored_day_without_its_call_file_is_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, TWO_DAYS)
            (root / "calls" / "2026-11-10.json").unlink()
            with self.assertRaisesRegex(ValueError, "2026-11-10"):
                build_report(root)

    def test_a_broken_report_cannot_stop_the_days_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = _project(tmp, TWO_DAYS)
            (root / "calls" / "2026-11-10.json").unlink()         # the report will fail on this
            deps = Deps(fetch=FakeFetch(add=1.0), llm=FakeLLM(), git=FakeGit())
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = run(utc("2026-11-11T22:30:00"), root, deps)
            self.assertEqual(code, 0)
            self.assertTrue((root / "calls" / "2026-11-11.json").exists())   # the call was still stored
            self.assertIn("report.md not updated", err.getvalue())

    def test_the_report_written_by_a_run_already_shows_that_runs_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            deps = Deps(fetch=FakeFetch(), llm=FakeLLM(), git=FakeGit())
            run(utc("2026-11-10T22:30:00"), root, deps)
            text = (root / "report.md").read_text()
            self.assertIn("ok 1", text)
            self.assertIn("Versions tried: v1", text)

    def test_a_daily_run_writes_the_same_report_every_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))
            deps = Deps(fetch=FakeFetch(add=1.0), llm=FakeLLM(), git=FakeGit())
            run(utc("2026-11-10T22:30:00"), root, deps)
            first = (root / "report.md").read_text()
            self.assertIn("calls scored: 10", first)              # Monday's 10 calls, scored on Tuesday
            write_report(root)
            self.assertEqual((root / "report.md").read_text(), first)   # same data, same bytes


if __name__ == "__main__":
    unittest.main()
