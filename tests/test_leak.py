"""Tests 9-10: nothing from after day D may reach the baseline or the prompt."""
import re
import unittest
from datetime import timedelta

from bot.history import base_rate
from bot.prompt import build_prompt
from tests.helpers import TICKERS, d


class Leak(unittest.TestCase):
    def test_09_base_rate_uses_only_history_up_to_D(self):
        D = d("2026-11-06")
        closes = [(D - timedelta(days=3), 10.0), (D - timedelta(days=2), 11.0),
                  (D - timedelta(days=1), 10.0), (D, 12.0)]
        # moves: 10->11 up, 11->10 down, 10->12 up  => 2 of 3 up (hand-computed)
        self.assertAlmostEqual(base_rate(closes, D), 2 / 3)
        later = closes + [(D + timedelta(days=1), 99.0)]               # a leak bait row
        self.assertAlmostEqual(base_rate(later, D), 2 / 3)

    def test_10_prompt_contains_no_date_after_D(self):
        D = d("2026-11-06")
        history = {}
        for t in TICKERS:
            rows = [(D - timedelta(days=i), 100.0 + i) for i in range(30)]
            rows.append((D + timedelta(days=1), 987.65))               # bait: the future
            rows.append((D + timedelta(days=2), 987.66))
            history[t] = sorted(rows)
        prompt = build_prompt(history, TICKERS, D, "v1")
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", prompt)
        self.assertTrue(all(d_ <= D.isoformat() for d_ in dates), dates)
        self.assertNotIn("987.65", prompt)
        self.assertNotIn("987.66", prompt)


if __name__ == "__main__":
    unittest.main()
