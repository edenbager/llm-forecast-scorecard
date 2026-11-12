"""The real price source: yfinance (Yahoo Finance). Needs the network; the parsing part does not."""
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf

from bot.fetch import Bar


def bars_from_frame(frame: pd.DataFrame, tickers: list[str], day: date,
                    fetch_time: datetime) -> dict[str, Bar | None]:
    """Pick each ticker's row for `day` out of a yfinance table (columns = (ticker, field)).
    A missing ticker, a missing day or an empty Close all mean None ("no data")."""
    bars: dict[str, Bar | None] = {}
    for ticker in tickers:
        bars[ticker] = _one_bar(frame, ticker, day, fetch_time)
    return bars


def _one_bar(frame, ticker, day, fetch_time):
    if frame.empty or ticker not in frame.columns.get_level_values(0):
        return None
    rows = frame[ticker]
    rows = rows[[stamp.date() == day for stamp in rows.index]]
    if rows.empty or pd.isna(rows["Close"].iloc[0]):
        return None
    row = rows.iloc[0]
    split = row.get("Stock Splits", 0.0)
    return Bar(close=float(row["Close"]), adj_close=float(row["Adj Close"]), fetch_time=fetch_time,
               split=0.0 if pd.isna(split) else float(split))


def closes_from_frame(frame: pd.DataFrame, tickers: list[str]) -> dict[str, list[tuple[date, float]]]:
    """Every (date, Close) per ticker from a yfinance table, empty days dropped. [] for an unknown ticker."""
    out: dict[str, list[tuple[date, float]]] = {}
    for ticker in tickers:
        if frame.empty or ticker not in frame.columns.get_level_values(0):
            out[ticker] = []
            continue
        closes = frame[ticker]["Close"].dropna()
        out[ticker] = [(stamp.date(), float(close)) for stamp, close in closes.items()]
    return out


def download_year(tickers: list[str], last_day: date) -> dict[str, list[tuple[date, float]]]:
    """About one year of raw closes up to and including last_day (day 0 setup only)."""
    frame = yf.download(tickers, start=last_day - timedelta(days=366), end=last_day + timedelta(days=1),
                        auto_adjust=False, progress=False, group_by="ticker", threads=False)
    return closes_from_frame(frame, tickers)


def make_download(day: date, fetch_time: datetime):
    """The `download(tickers)` function that fetch_bars expects. Raw Close, not auto-adjusted."""
    def download(tickers: list[str]) -> dict[str, Bar | None]:
        frame = yf.download(tickers, start=day, end=day + timedelta(days=1), auto_adjust=False,
                            actions=True, progress=False, group_by="ticker", threads=False)
        return bars_from_frame(frame, tickers, day, fetch_time)
    return download
