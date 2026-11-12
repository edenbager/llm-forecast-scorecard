"""Tests 24-27: statistics and report. Test 28: git push conflicts."""
import unittest

from bot.gitsync import PushFailed, push_with_rebase
from bot.report import summarize_by_version
from bot.stats import Row, bootstrap_interval, brier, calibration


class Stats(unittest.TestCase):
    def test_24_brier_of_0_7_up_and_0_2_down_is_0_065(self):
        self.assertAlmostEqual(brier([Row(0.7, "up"), Row(0.2, "down")]), 0.065, places=9)

    def test_25_bootstrap_with_all_days_equal_has_zero_width(self):
        lo, hi = bootstrap_interval([0.01] * 20, n_boot=500, seed=1)
        self.assertAlmostEqual(hi - lo, 0.0, places=12)

    def test_26_calibration_bucket_with_29_is_hidden_30_is_shown(self):
        rows = [Row(0.8, "up" if i % 2 else "down") for i in range(29)]        # high bucket, n=29
        rows += [Row(0.2, "up" if i % 2 else "down") for i in range(30)]       # low bucket, n=30
        by_label = {b.label: b for b in calibration(rows)}
        self.assertEqual(by_label[">0.55"].n, 29)
        self.assertIsNone(by_label[">0.55"].freq_up)                            # hidden
        self.assertEqual(by_label["<0.45"].n, 30)
        self.assertIsNotNone(by_label["<0.45"].freq_up)                         # shown
        self.assertEqual(by_label["0.45-0.55"].n, 0)

    def test_27_two_prompt_versions_are_scored_in_separate_tables(self):
        rows = [Row(0.7, "up", "v1"), Row(0.7, "up", "v1"), Row(0.3, "down", "v1"),
                Row(0.9, "down", "v2"), Row(0.9, "down", "v2")]
        out = summarize_by_version(rows)
        self.assertEqual(set(out), {"v1", "v2"})
        self.assertEqual((out["v1"]["n"], out["v2"]["n"]), (3, 2))
        self.assertAlmostEqual(out["v1"]["brier"], 0.09)
        self.assertAlmostEqual(out["v2"]["brier"], 0.81)


class Git(unittest.TestCase):
    @staticmethod
    def _fake_run(push_codes):
        cmds, pushes = [], iter(push_codes)

        def run(cmd):
            cmds.append(cmd)
            return next(pushes) if cmd == ["git", "push"] else 0
        return run, cmds

    def test_28_one_conflict_recovers_second_conflict_fails_loud(self):
        run, cmds = self._fake_run([1, 0])                     # push fails, then works
        push_with_rebase(run)
        self.assertEqual(cmds, [["git", "push"], ["git", "pull", "--rebase"], ["git", "push"]])

        run, cmds = self._fake_run([1, 1])                     # push fails twice
        with self.assertRaises(PushFailed):
            push_with_rebase(run)
        self.assertEqual(cmds, [["git", "push"], ["git", "pull", "--rebase"], ["git", "push"]])


if __name__ == "__main__":
    unittest.main()
