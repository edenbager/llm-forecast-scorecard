"""Wires the real fetch, LLM and git into the runner. This is what `python -m bot` runs."""
import json
from datetime import datetime, timezone
from pathlib import Path

from bot import yahoo
from bot.fetch import fetch_bars
from bot.gitops import Git, subprocess_runner
from bot.llm import make_llm
from bot.runner import Deps, run


def build_deps(root: Path) -> Deps:
    config = json.loads((Path(root) / "config.json").read_text())

    def fetch(tickers, day, now):
        return fetch_bars(tickers, day, now, yahoo.make_download(day, now))

    return Deps(fetch=fetch, llm=make_llm(config["model"]), git=Git(subprocess_runner(Path(root))))


def main() -> int:
    root = Path.cwd()
    return run(datetime.now(timezone.utc), root, build_deps(root))
