"""Report numbers. Each prompt_version is scored on its own, never mixed with another."""
from collections import defaultdict

from bot.stats import Row, brier


def summarize_by_version(rows: list[Row]) -> dict[str, dict]:
    by_version: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        by_version[row.prompt_version].append(row)
    return {version: {"n": len(group), "brier": brier(group)} for version, group in by_version.items()}
