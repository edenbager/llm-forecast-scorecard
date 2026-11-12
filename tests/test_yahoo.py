"""Extra tests (not in the design's 28): turning a yfinance table into Bars. No network."""
import unittest

import pandas as pd

from bot.fetch import Bar
from bot.yahoo import bars_from_frame
from tests.helpers import d, utc

NOW = utc("2026-11-10T22:30:00")


def _frame(rows):
    """rows: {ticker: {"Close":..., "Adj Close":..., "Stock Splits":...}} for the single date 2026-11-10."""
    columns = pd.MultiIndex.from_tuples([(t, f) for t, fields in rows.items() for f in fields])
    values = [[v for fields in rows.values() for v in fields.values()]]
    return pd.DataFrame(values, index=pd.DatetimeIndex(["2026-11-10"], name="Date"), columns=columns)


class Yahoo(unittest.TestCase):
    def test_row_for_the_day_becomes_a_bar_with_close_adj_close_and_split(self):
        frame = _frame({"AAPL": {"Close": 100.0, "Adj Close": 99.5, "Stock Splits": 4.0}})
        bars = bars_from_frame(frame, ["AAPL"], d("2026-11-10"), NOW)
        self.assertEqual(bars["AAPL"], Bar(close=100.0, adj_close=99.5, fetch_time=NOW, split=4.0))

    def test_empty_close_unknown_ticker_and_other_day_are_no_data(self):
        frame = _frame({"AAPL": {"Close": float("nan"), "Adj Close": float("nan"), "Stock Splits": 0.0},
                        "MSFT": {"Close": 50.0, "Adj Close": 50.0, "Stock Splits": float("nan")}})
        bars = bars_from_frame(frame, ["AAPL", "MSFT", "ZZZZ"], d("2026-11-10"), NOW)
        self.assertIsNone(bars["AAPL"])                  # NaN close
        self.assertIsNone(bars["ZZZZ"])                  # not in the table
        self.assertEqual(bars["MSFT"].split, 0.0)        # NaN split means no split
        other = bars_from_frame(frame, ["MSFT"], d("2026-11-09"), NOW)
        self.assertIsNone(other["MSFT"])                 # the table has no row for that day

    def test_empty_table_gives_no_data_for_everyone(self):
        bars = bars_from_frame(pd.DataFrame(), ["AAPL"], d("2026-11-10"), NOW)
        self.assertEqual(bars, {"AAPL": None})


if __name__ == "__main__":
    unittest.main()
