"""Extra tests (not in the design's 28): the bootstrap interval resamples runs of days (stationary bootstrap,
Politis & Romano 1994), so dependent days do not make the interval look falsely narrow."""
import unittest

from bot.stats import bootstrap_interval


def _width(values, **kw):
    lo, hi = bootstrap_interval(values, n_boot=3000, seed=7, **kw)
    return hi - lo


class StationaryBootstrap(unittest.TestCase):
    def test_runs_of_similar_days_give_a_wider_interval_than_treating_days_as_independent(self):
        runs = ([0.1] * 8 + [-0.1] * 8) * 6                      # strong dependence: long runs of the same sign
        independent = _width(runs, mean_block=1)                  # block length 1 = the old behaviour
        dependent = _width(runs, mean_block=5)
        self.assertGreater(dependent, independent * 1.2)          # measured: about 1.3x (0.054 vs 0.042)

    def test_same_seed_gives_the_same_interval(self):
        values = [0.01, -0.02, 0.03, 0.0, -0.01, 0.02, 0.01, -0.03]
        self.assertEqual(bootstrap_interval(values, n_boot=500, seed=3), bootstrap_interval(values, n_boot=500, seed=3))

    def test_one_value_or_equal_values_have_no_width(self):
        self.assertEqual(bootstrap_interval([0.05], n_boot=200, seed=1), (0.05, 0.05))
        lo, hi = bootstrap_interval([0.02] * 10, n_boot=200, seed=1)
        self.assertAlmostEqual(hi - lo, 0.0, places=12)

    def test_a_block_length_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            bootstrap_interval([0.1, 0.2], n_boot=10, mean_block=0.5)


if __name__ == "__main__":
    unittest.main()
