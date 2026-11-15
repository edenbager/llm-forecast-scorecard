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


def config_at(root: Path, when: str) -> dict:
    """config.json as it stood at `when` (the call's called_at) on the main line, so a config change merged
    after the run is not blamed on the call. --first-parent: a PR counts from its merge, not its branch
    commits. Falls back to the current config, with a note, when git can't tell (no repo, no git, or
    history too shallow)."""
    try:
        sha = subprocess.run(["git", "-C", str(root), "rev-list", "-1", "--first-parent", f"--before={when}", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        shown = subprocess.run(["git", "-C", str(root), "show", f"{sha}:./config.json"],
                               capture_output=True, text=True) if sha else None
    except OSError:
        shown = None
    if shown is not None and shown.returncode == 0:
        return json.loads(shown.stdout)
    print(f"watchdog: no git config before {when}; using the current config.json", file=sys.stderr)
    return json.loads((Path(root) / "config.json").read_text())


def check(root: Path, today: date) -> str | None:
    """Return a one-line problem, or None when yesterday's call is fine (or none was due)."""
    day = today - timedelta(days=1)
    if not market.is_trading_day(day):
        return None
    path = store.call_path(root, day)
    if not path.exists():
        return f"no call file for {day}"
    record = json.loads(path.read_text())
    config = config_at(Path(root), record.get("called_at") or f"{day}T23:59:59+00:00")
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
