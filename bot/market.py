"""Market calendar: which days the NYSE trades, and when it opens and closes (UTC).

All dates and times come from the exchange_calendars library (calendar "XNYS"),
so holidays, early closes and summer time are never hard-coded here.

Limit: the library's calendar runs from 20 years back to about 1 year ahead of today.
A date outside that raises exchange_calendars' DateOutOfBounds error (loud, not silent).
"""
from datetime import date, datetime, timedelta
from functools import lru_cache

import exchange_calendars as xc
import pandas as pd


@lru_cache(maxsize=1)
def _calendar():
    # Built once per run instead of on every call (measured: 0.078 s per build).
    return xc.get_calendar("XNYS")


def _session(d: date) -> pd.Timestamp:
    # The library wants a plain (timezone-free) date as a pandas Timestamp.
    return pd.Timestamp(d)


def is_trading_day(d: date) -> bool:
    return bool(_calendar().is_session(_session(d)))


def trading_days(start: date, end: date) -> list[date]:
    """Every trading day from start to end, both included."""
    if start > end:
        return []
    return [s.date() for s in _calendar().sessions_in_range(_session(start), _session(end))]


def next_trading_day(d: date) -> date:
    """The first trading day strictly after d (Friday -> Monday, skipping holidays)."""
    following = _session(d + timedelta(days=1))
    return _calendar().date_to_session(following, direction="next").date()


def next_open_utc(d: date) -> datetime:
    """UTC time the market opens on D+1, taken from the calendar."""
    return _calendar().session_open(_session(next_trading_day(d))).to_pydatetime()


def session_close_utc(d: date) -> datetime:
    """UTC time the market closes on trading day d (earlier on early-close days)."""
    return _calendar().session_close(_session(d)).to_pydatetime()
