"""Price fetching with retries, and a guard against half-finished (live) bars."""
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

from bot import market

ATTEMPTS = 3          # tries in total, with a growing pause between them


@dataclass(frozen=True)
class Bar:
    close: float
    adj_close: float
    fetch_time: datetime
    split: float = 0.0


class PartialBarError(Exception):
    pass


def fetch_bars(tickers: list[str], day: date, now: datetime,
               download: Callable[[list[str]], dict], sleep: Callable[[float], None] = time.sleep,
               attempts: int = ATTEMPTS) -> dict[str, Bar | None]:
    """{ticker: Bar}, or None for a ticker with no data. Raises if the market is still open on `day`,
    because a bar fetched before the close is a live price, not the day's Close."""
    if now < market.session_close_utc(day):
        raise PartialBarError(f"{now.isoformat()} is before the close of {day.isoformat()}")
    pause = 1.0
    for attempt in range(1, attempts + 1):
        try:
            bars = download(tickers)
            break
        except Exception:
            if attempt == attempts:
                raise                      # out of tries: fail loud
            sleep(pause)
            pause *= 2
    return {ticker: bars.get(ticker) for ticker in tickers}
