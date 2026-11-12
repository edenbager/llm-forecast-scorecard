"""Tests 1-8: gate and calendar, write-once and timing."""
import tempfile
import unittest
from pathlib import Path

from bot import market
from bot.runner import Deps, run
from tests.helpers import (FakeFetch, FakeGit, FakeLLM, d, make_project, read_log,
                           read_scores, seed_call, tree_hash, utc)


def _deps(add=0.0):
    return Deps(fetch=FakeFetch(add=add), llm=FakeLLM(), git=FakeGit())


class GateAndCalendar(unittest.TestCase):
    def _gate_exit(self, now):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            before = tree_hash(root)
            deps = _deps()
            self.assertEqual(run(utc(now), root, deps), 0)
            self.assertEqual(tree_hash(root), before)          # nothing written
            self.assertEqual(deps.fetch.calls, [])
            self.assertEqual(deps.llm.prompts, [])

    def test_01_saturday_exits_zero_and_writes_nothing(self):
        self._gate_exit("2026-11-14T22:30:00")

    def test_02_market_holiday_exits_zero(self):
        self._gate_exit("2026-12-25T22:30:00")                 # Christmas, a Friday

    def test_03_next_trading_day_skips_weekend_and_holiday(self):
        self.assertEqual(market.next_trading_day(d("2026-11-13")), d("2026-11-16"))  # Fri -> Mon
        self.assertEqual(market.next_trading_day(d("2026-11-25")), d("2026-11-27"))  # Wed -> Fri (Thu = Thanksgiving)

    def test_04_open_time_comes_from_the_calendar(self):
        # Winter (EST): open 14:30 UTC. Day after Thanksgiving is an early close: 18:00 UTC.
        self.assertEqual(market.next_open_utc(d("2026-11-25")), utc("2026-11-27T14:30:00"))
        self.assertEqual(market.session_close_utc(d("2026-11-27")), utc("2026-11-27T18:00:00"))
        # Summer (EDT): open 13:30 UTC. 3 Jul 2026 is the observed July 4 holiday, so D+1 is Mon 6 Jul.
        self.assertEqual(market.next_open_utc(d("2026-07-02")), utc("2026-07-06T13:30:00"))

    def test_05_missed_tuesday_gets_one_no_run_row_and_no_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))   # Monday ran
            self.assertEqual(run(utc("2026-11-11T22:30:00"), root, _deps(add=1.0)), 0)  # Wednesday
            tue = [r for r in read_log(root) if r["day"] == "2026-11-10"]
            self.assertEqual([r["status"] for r in tue], ["no run"])
            self.assertFalse((root / "calls" / "2026-11-10.json").exists())


class WriteOnceAndTiming(unittest.TestCase):
    def test_06_existing_call_means_no_llm_call_and_no_file_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            now = utc("2026-11-10T22:30:00")
            seed_call(root, "2026-11-10", now)
            before = tree_hash(root)
            deps = _deps(add=0.0)                              # same bars as the seeded snapshot
            self.assertEqual(run(now, root, deps), 0)
            self.assertEqual(deps.llm.prompts, [])
            self.assertEqual(tree_hash(root), before)

    def test_07_run_after_next_open_makes_no_call_and_logs_late(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            deps = _deps()
            # Friday 13 Nov's run starts Monday 16 Nov 15:00 UTC, after Monday's open (14:30 UTC).
            run(utc("2026-11-16T15:00:00"), root, deps, day=d("2026-11-13"))
            self.assertEqual(deps.llm.prompts, [])
            self.assertFalse((root / "calls" / "2026-11-13.json").exists())
            fri = [r for r in read_log(root) if r["day"] == "2026-11-13"]
            self.assertEqual([r["status"] for r in fri], ["late"])

    def test_08_same_day_run_twice_scores_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))   # Monday's call
            now = utc("2026-11-10T22:30:00")                            # Tuesday scores Monday
            run(now, root, _deps(add=1.0))
            run(now, root, _deps(add=1.0))
            monday = [r for r in read_scores(root) if r["day"] == "2026-11-09"]
            self.assertEqual(len(monday), 10)                           # 10 tickers, not 20


if __name__ == "__main__":
    unittest.main()
