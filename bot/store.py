"""Reads and writes the data files: price history, daily snapshots, call records."""
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from bot.fetch import Bar


def load_history(root: Path) -> dict[str, list[tuple[date, float]]]:
    """Closes per ticker: the day-0 history file plus every daily snapshot, oldest first."""
    root = Path(root)
    history: dict[str, list[tuple[date, float]]] = defaultdict(list)
    with open(root / "data" / "history.csv", newline="") as f:
        for row in csv.DictReader(f):
            history[row["ticker"]].append((date.fromisoformat(row["date"]), float(row["close"])))
    for snap in sorted((root / "data" / "snapshots").glob("*.csv")):
        day = date.fromisoformat(snap.stem)
        with open(snap, newline="") as f:
            for row in csv.DictReader(f):
                history[row["ticker"]].append((day, float(row["close"])))
    return {ticker: sorted(rows) for ticker, rows in history.items()}


def write_snapshot(root: Path, day: date, bars: dict[str, Bar | None]) -> None:
    """data/snapshots/<day>.csv: Close, Adj Close, fetch time and split for tickers that have data."""
    with open(Path(root) / "data" / "snapshots" / f"{day.isoformat()}.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ticker", "close", "adj_close", "fetch_time", "split"])
        for ticker, bar in bars.items():
            if bar is not None:
                writer.writerow([ticker, bar.close, bar.adj_close, bar.fetch_time.isoformat(), bar.split])


def call_path(root: Path, day: date) -> Path:
    return Path(root) / "calls" / f"{day.isoformat()}.json"


def write_call(root: Path, day: date, record: dict) -> None:
    call_path(root, day).write_text(json.dumps(record, indent=2))
