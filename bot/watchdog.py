"""Watchdog: did the previous day's run leave a good call? Run by .github/workflows/watchdog.yml.

The daily run starts at 22:37 UTC on trading day D. This check runs the next morning (UTC date D+1), so the
call for D must exist, hold probabilities, and match config.json. A non-trading D is skipped.
"""
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from bot import market, store


def config_at_call(root: Path, path: Path) -> dict:
    """config.json as committed with the call file (its newest add; calls are write-once), so a config
    change after the run is not blamed on the call. Falls back to the current config when git can't tell (no repo, or the call isn't committed yet)."""
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    added = git("log", "--diff-filter=A", "--format=%H", "--", str(path.relative_to(root))).stdout.split()
    if added:
        shown = git("show", f"{added[0]}:config.json")
        if shown.returncode == 0:
            return json.loads(shown.stdout)
    return json.loads((Path(root) / "config.json").read_text())


def check(root: Path, today: date) -> str | None:
    """Return a one-line problem, or None when yesterday's call is fine (or none was due)."""
    day = today - timedelta(days=1)
    if not market.is_trading_day(day):
        return None
    path = store.call_path(root, day)
    if not path.exists():
        return f"no call file for {day}"
    config = config_at_call(Path(root), path)
    record = json.loads(path.read_text())
    if not record.get("p_up"):
        return f"call for {day} has no probabilities (status {record.get('status')})"
    if record.get("prompt_version") != config["prompt_version"]:
        return f"call for {day} has prompt_version {record.get('prompt_version')}, config says {config['prompt_version']}"
    if record.get("benchmark") != config.get("benchmark"):
        return f"call for {day} has benchmark {record.get('benchmark')}, config says {config.get('benchmark')}"
    # The run on day D grades the call of the trading day before: by now it must have score rows.
    earlier = market.previous_trading_day(day)
    earlier_path = store.call_path(root, earlier)
    if (earlier_path.exists() and json.loads(earlier_path.read_text()).get("p_up")
            and earlier.isoformat() not in {row["day"] for row in store.read_scores(root)}):
        return f"call for {earlier} is not scored"
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
