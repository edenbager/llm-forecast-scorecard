"""Price fetching. Only the Bar box exists so far; fetch_bars comes with tests 16-18."""
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Bar:
    close: float
    adj_close: float
    fetch_time: datetime
    split: float = 0.0
