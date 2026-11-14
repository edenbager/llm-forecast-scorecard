"""Watchdog: did the previous day's run leave a good call? Run by .github/workflows/watchdog.yml.

The daily run starts at 22:37 UTC on trading day D. This check runs the next morning (UTC date D+1), so the
call for D must exist, hold probabilities, and match config.json. A non-trading D is skipped.
"""
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from bot import market, store


def check(root: Path, today: date) -> str | None:
    """Return a one-line problem, or None when yesterday's call is fine (or none was due)."""
    day = today - timedelta(days=1)
    if not market.is_trading_day(day):
        return None
    path = store.call_path(root, day)
    if not path.exists():
        return f"no call file for {day}"
    config = json.loads((Path(root) / "config.json").read_text())
    record = json.loads(path.read_text())
    if not record.get("p_up"):
        return f"call for {day} has no probabilities (status {record.get('status')})"
    if record.get("prompt_version") != config["prompt_version"]:
        return f"call for {day} has prompt_version {record.get('prompt_version')}, config says {config['prompt_version']}"
    if record.get("benchmark") != config.get("benchmark"):
        return f"call for {day} has benchmark {record.get('benchmark')}, config says {config.get('benchmark')}"
    return None


def main() -> int:
    problem = check(Path.cwd(), datetime.now(timezone.utc).date())
    if problem:
        print(f"WATCHDOG PROBLEM: {problem}", file=sys.stderr)
        return 1
    print("watchdog: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
