"""report.md: the numbers. Each prompt_version is scored on its own, never mixed with another."""
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from bot import runlog, store
from bot.stats import Row, bootstrap_interval, brier, calibration, hit_rate

FIXED_LINE = "4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year."
LOG_STATUSES = ["invalid", "no data", "no run", "late", "split"]
N_BOOT = 10_000
BOOT_SEED = 0          # fixed, so the same data always gives the same report bytes


@dataclass(frozen=True)
class ReportRow:
    day: str
    prompt_version: str
    ticker: str
    p_up: float
    base_p: float       # the baseline stored in the call file on day D (no leak)
    outcome: str


def summarize_by_version(rows: list[Row]) -> dict[str, dict]:
    by_version: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        by_version[row.prompt_version].append(row)
    return {version: {"n": len(group), "brier": brier(group)} for version, group in by_version.items()}


def load_rows(root: Path) -> list[ReportRow]:
    rows, base_by_day = [], {}
    for r in store.read_scores(root):
        day = r["day"]
        if day not in base_by_day:
            record = json.loads(store.call_path(root, date.fromisoformat(day)).read_text())
            base_by_day[day] = record["base_rate"]
        rows.append(ReportRow(day, r["prompt_version"], r["ticker"], float(r["p_up"]),
                              base_by_day[day][r["ticker"]], r["outcome"]))
    return rows


def build_report(root: Path) -> str:
    rows = load_rows(root)
    counts = Counter(r["status"] for r in runlog.read(root))
    called = sorted({json.loads(p.read_text()).get("prompt_version", "?")
                     for p in (Path(root) / "calls").glob("*.json")})
    lines = ["# Prediction-scoring report", "", FIXED_LINE, "",
             "Log counts (all versions): " + ", ".join(f"{s} {counts[s]}" for s in LOG_STATUSES),
             "Versions tried: " + (", ".join(called) or "none")]
    if not rows:
        return "\n".join(lines + ["", "No scored days yet."]) + "\n"
    by_version: dict[str, list[ReportRow]] = defaultdict(list)
    for row in rows:
        by_version[row.prompt_version].append(row)
    for version in sorted(by_version):
        lines += _section(version, by_version[version])
    return "\n".join(lines) + "\n"


def write_report(root: Path) -> None:
    store.write_atomic(Path(root) / "report.md", build_report(root))


def _section(version: str, group: list[ReportRow]) -> list[str]:
    llm = [Row(r.p_up, r.outcome, version) for r in group]
    base = [Row(r.base_p, r.outcome, version) for r in group]
    days = sorted({r.day for r in group})
    llm_hits, base_hits = hit_rate(llm), hit_rate(base)
    out = ["", f"## Prompt version {version}", "",
           f"- n_days: {len(days)}, calls scored: {len(group)}",
           f"- Hit rate: LLM {_rate(llm_hits)}; base_rate {_rate(base_hits)}; coin flip 0.500",
           f"- Brier: LLM {summarize_by_version(llm)[version]['brier']:.3f}, base_rate {brier(base):.3f}, "
           f"always 0.5: 0.250",
           f"- Main result: {_main_result(group, days)}", "", "Calibration (p_up buckets):", "",
           "| bucket | n | mean p_up | share up |", "|---|---|---|---|"]
    for b in calibration(llm):
        shown = b.freq_up is not None
        out.append(f"| {b.label} | {b.n} | {b.mean_p:.3f} | {b.freq_up:.3f} |" if shown
                   else f"| {b.label} | {b.n} | hidden (n < 30) | hidden (n < 30) |")
    return out


def _main_result(group: list[ReportRow], days: list[str]) -> str:
    """Mean per-day (LLM Brier - base_rate Brier); below 0 the LLM beats the baseline."""
    diffs = []
    for day in days:
        todays = [r for r in group if r.day == day]
        diffs.append(sum((r.p_up - (r.outcome == "up")) ** 2 - (r.base_p - (r.outcome == "up")) ** 2
                         for r in todays) / len(todays))
    mean = sum(diffs) / len(diffs)
    if len(days) < 2:
        return f"mean per-day (LLM Brier - base_rate Brier) {mean:+.3f}; interval needs 2+ days"
    low, high = bootstrap_interval(diffs, n_boot=N_BOOT, seed=BOOT_SEED)
    return (f"mean per-day (LLM Brier - base_rate Brier) {mean:+.3f}, 95% bootstrap interval "
            f"[{low:+.3f}, {high:+.3f}] over {len(days)} days")


def _rate(result: tuple[float | None, int]) -> str:
    rate, n = result
    return f"{rate:.3f} (n={n})" if rate is not None else f"n/a (n={n})"
