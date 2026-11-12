"""Extra tests (not part of the design's 1-28) for bugs found by the code review of 12.11.2026."""
import csv
import shutil
import tempfile
import unittest
from pathlib import Path

from bot import store
from bot.fetch import Bar
from bot.runner import Deps, run
from bot.validate import InvalidCall, parse_and_validate
from tests.helpers import TICKERS, FakeFetch, FakeGit, FakeLLM, d, make_project, utc


def _deps(**fetch_kw):
    return Deps(fetch=FakeFetch(**fetch_kw), llm=FakeLLM(), git=FakeGit())


class ReviewFixes(unittest.TestCase):
    def test_a_default_day_is_the_new_york_date_not_the_utc_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            # 00:30 UTC on 11 Nov is 19:30 on Tue 10 Nov in New York: the run belongs to 10 Nov.
            run(utc("2026-11-11T00:30:00"), root, _deps())
            self.assertTrue((root / "calls" / "2026-11-10.json").exists())
            self.assertFalse((root / "calls" / "2026-11-11.json").exists())

    def test_b_naive_now_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            naive = utc("2026-11-10T22:30:00").replace(tzinfo=None)
            with self.assertRaises(ValueError):
                run(naive, root, _deps())

    def test_c_base_rate_failure_happens_before_the_paid_llm_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            path = root / "data" / "history.csv"
            with open(path, newline="") as f:
                rows = [r for r in csv.reader(f)]
            kept = [r for r in rows if r[1] != "JPM"] + [["2026-11-06", "JPM", "109.0"]]
            with open(path, "w", newline="") as f:
                csv.writer(f).writerows(kept)
            deps = _deps(add=0.0)             # JPM today = 109.0 = its only past close: no price move
            with self.assertRaises(ValueError):
                run(utc("2026-11-10T22:30:00"), root, deps)
            self.assertEqual(deps.llm.prompts, [])

    def test_d_non_string_ticker_is_invalid_not_a_crash(self):
        for bad in ('[{"ticker": ["AAPL"], "p_up": 0.5}]', '[{"ticker": 5, "p_up": 0.5}]'):
            with self.subTest(bad):
                with self.assertRaises(InvalidCall):
                    parse_and_validate(bad, TICKERS)

    def test_e_missing_folders_are_created_and_no_temp_file_is_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            shutil.rmtree(root / "calls")                   # a fresh git checkout has no empty folders
            shutil.rmtree(root / "data" / "snapshots")
            run(utc("2026-11-10T22:30:00"), root, _deps())
            self.assertTrue((root / "calls" / "2026-11-10.json").exists())
            self.assertTrue((root / "data" / "snapshots" / "2026-11-10.csv").exists())
            self.assertEqual(list(root.rglob("*.tmp")), [])

    def test_f_a_date_in_history_and_in_a_snapshot_appears_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            bar = Bar(close=555.0, adj_close=555.0, fetch_time=utc("2026-11-06T22:30:00"))
            store.write_snapshot(root, d("2026-11-06"), {"AAPL": bar})   # history.csv has 6 Nov too
            rows = store.load_history(root)["AAPL"]
            dates = [when for when, _ in rows]
            self.assertEqual(len(dates), len(set(dates)))
            self.assertEqual(dict(rows)[d("2026-11-06")], 555.0)         # the snapshot wins


if __name__ == "__main__":
    unittest.main()
