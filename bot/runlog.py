"""log.csv: one row per event (day, ticker, status). Rows are only ever added, never changed."""
import csv
from datetime import date, timedelta
from pathlib import Path

from bot import market

FIELDS = ["day", "ticker", "status"]


def read(root: Path) -> list[dict]:
    path = Path(root) / "log.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def add(root: Path, day: date, status: str, ticker: str = "") -> None:
    """Append a row unless the identical row exists, so a re-run never doubles it."""
    row = {"day": day.isoformat(), "ticker": ticker, "status": status}
    if row in read(root):
        return
    path = Path(root) / "log.csv"
    is_new = not path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def backfill(root: Path, today: date) -> None:
    """Write a 'no run' row for each trading day since the first logged day that has no row.

    Never writes a call. With an empty log there is no first day, so nothing is filled.
    """
    rows = read(root)
    if not rows:
        return
    first = min(date.fromisoformat(r["day"]) for r in rows)
    logged = {r["day"] for r in rows}
    for day in market.trading_days(first, today - timedelta(days=1)):
        if day.isoformat() not in logged:
            add(root, day, "no run")
