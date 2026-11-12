"""The daily run. Only the gate (step 1) exists so far; the rest comes with tests 5-8, 17, 23."""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from bot import market


@dataclass
class Deps:
    fetch: Callable
    llm: Callable
    git: Any


def run(now: datetime, root: Path, deps: Deps, day=None) -> int:
    day = day or now.date()
    if not market.is_trading_day(day):
        return 0                       # step 1, gate: not a trading day, write nothing
    raise NotImplementedError("steps 2-6 are not written yet")
