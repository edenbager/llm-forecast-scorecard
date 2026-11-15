"""Extra test (not in the design's 28), proposed 15.11.2026: a missed run must not leave a call unscored.
Today only the previous trading day's call is scored. If Tuesday's run never happens, Monday's call
(whose D+1 is Tuesday) is never scored. The run now also grades older calls that have no score rows."""
import tempfile
import unittest
from pathlib import Path

from bot.runner import Deps, run
from tests.helpers import TICKERS, FakeFetch, FakeGit, FakeLLM, make_project, read_log, read_scores, seed_call, utc


class CatchUp(unittest.TestCase):
    def test_a_missed_tuesday_run_does_not_leave_mondays_call_unscored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))          # Monday's call exists
            deps = Deps(fetch=FakeFetch(add=1.0), llm=FakeLLM(), git=FakeGit())
            run(utc("2026-11-11T22:30:00"), root, deps)                        # Tuesday never ran: Wednesday does
            scored = {r["ticker"] for r in read_scores(root) if r["day"] == "2026-11-09"}
            self.assertEqual(scored, set(TICKERS))

    def test_a_call_that_is_already_scored_is_not_fetched_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))
            run(utc("2026-11-10T22:30:00"), root, Deps(fetch=FakeFetch(add=1.0), llm=FakeLLM(), git=FakeGit()))
            fetch = FakeFetch(add=1.0)
            run(utc("2026-11-11T22:30:00"), root, Deps(fetch=fetch, llm=FakeLLM(), git=FakeGit()))
            self.assertEqual([day.isoformat() for _, day in fetch.calls], ["2026-11-11"])

    def test_a_failed_catch_up_fetch_is_logged_and_todays_call_still_happens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp) / "p")
            seed_call(root, "2026-11-09", utc("2026-11-09T22:30:00"))
            good = FakeFetch(add=1.0)

            def fetch(tickers, day, now):
                if day.isoformat() == "2026-11-10":          # the missed D+1 cannot be fetched
                    raise RuntimeError("yahoo down")
                return good(tickers, day, now)

            run(utc("2026-11-11T22:30:00"), root, Deps(fetch=fetch, llm=FakeLLM(), git=FakeGit()))
            self.assertTrue((root / "calls" / "2026-11-11.json").exists())
            self.assertIn(("2026-11-09", "catch-up failed"), [(r["day"], r["status"]) for r in read_log(root)])


if __name__ == "__main__":
    unittest.main()
