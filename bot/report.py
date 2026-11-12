"""report.md: the numbers. Each prompt_version is scored on its own, never mixed with another."""
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from bot import runlog, store
from bot.stats import Row, bootstrap_interval, brier, calibration, hit_rate

FIXED_LINE = "4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year."
LOG_STATUSES = ["ok", "invalid", "no data", "no run", "late", "split"]   # every status runlog writes
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


def load_calls(root: Path) -> dict[str, dict]:
    """Every stored call record by day, read once."""
    folder = Path(root) / "calls"
    calls = {}
    for path in sorted(folder.glob("*.json")) if folder.exists() else []:
        record = json.loads(path.read_text())
        if not isinstance(record, dict):
            raise ValueError(f"{path.name} is not a call record")
        calls[path.stem] = record
    return calls


def load_rows(root: Path, calls: dict[str, dict] | None = None) -> list[ReportRow]:
    calls = load_calls(root) if calls is None else calls
    rows = []
    for r in store.read_scores(root):
        record = calls.get(r["day"])
        if record is None:
            raise ValueError(f"scores.csv has {r['day']} but calls/{r['day']}.json is missing")
        if r["ticker"] not in record.get("base_rate", {}):
            raise ValueError(f"calls/{r['day']}.json has no base_rate for {r['ticker']}")
        rows.append(ReportRow(r["day"], r["prompt_version"], r["ticker"], float(r["p_up"]),
                              record["base_rate"][r["ticker"]], r["outcome"]))
    return rows


def build_report(root: Path) -> str:
    calls = load_calls(root)
    rows = load_rows(root, calls)
    counts = Counter(r["status"] for r in runlog.read(root))
    called = sorted({record.get("prompt_version", "?") for record in calls.values()})
    lines = ["# Prediction-scoring report", "", FIXED_LINE, "",
             "Log counts (all versions): " + ", ".join(f"{s} {counts[s]}" for s in LOG_STATUSES),
             "Versions tried: " + (", ".join(called) or "none")]
    if not rows:
        return "\n".join(lines + ["", "No scored days yet."]) + "\n"
    summary = summarize_by_version([Row(r.p_up, r.outcome, r.prompt_version) for r in rows])
    by_version: dict[str, list[ReportRow]] = defaultdict(list)
    for row in rows:
        by_version[row.prompt_version].append(row)
    for version in sorted(by_version):
        lines += _section(version, by_version[version], summary[version])
    return "\n".join(lines) + "\n"


def write_report(root: Path) -> None:
    store.write_atomic(Path(root) / "report.md", build_report(root))


def _section(version: str, group: list[ReportRow], summary: dict) -> list[str]:
    llm = [Row(r.p_up, r.outcome, version) for r in group]
    base = [Row(r.base_p, r.outcome, version) for r in group]
    llm_by_day, base_by_day = defaultdict(list), defaultdict(list)
    for r in group:
        llm_by_day[r.day].append(Row(r.p_up, r.outcome, version))
        base_by_day[r.day].append(Row(r.base_p, r.outcome, version))
    out = ["", f"## Prompt version {version}", "",
           f"- n_days: {len(llm_by_day)}, calls scored: {summary['n']}",
           f"- Hit rate (each on its own calls that picked a side): LLM {_rate(hit_rate(llm))}; "
           f"base_rate {_rate(hit_rate(base))}; coin flip 0.500",
           f"- Brier: LLM {summary['brier']:.3f}, base_rate {brier(base):.3f}, always 0.5: 0.250",
           f"- Main result: {_main_result(llm_by_day, base_by_day)}", "", "Calibration (p_up buckets):", "",
           "| bucket | n | mean p_up | share up |", "|---|---|---|---|"]
    for b in calibration(llm):
        shown = b.freq_up is not None
        out.append(f"| {b.label} | {b.n} | {b.mean_p:.3f} | {b.freq_up:.3f} |" if shown
                   else f"| {b.label} | {b.n} | hidden (n < 30) | hidden (n < 30) |")
    return out


def _main_result(llm_by_day: dict[str, list[Row]], base_by_day: dict[str, list[Row]]) -> str:
    """Mean per-day (LLM Brier - base_rate Brier); below 0 the LLM beats the baseline."""
    days = sorted(llm_by_day)
    diffs = [brier(llm_by_day[day]) - brier(base_by_day[day]) for day in days]
    mean = sum(diffs) / len(diffs)
    if len(days) < 2:
        return f"mean per-day (LLM Brier - base_rate Brier) {mean:+.3f}; interval needs 2+ days"
    low, high = bootstrap_interval(diffs, n_boot=N_BOOT, seed=BOOT_SEED)
    return (f"mean per-day (LLM Brier - base_rate Brier) {mean:+.3f}, 95% bootstrap interval "
            f"[{low:+.3f}, {high:+.3f}] over {len(days)} days")


def _rate(result: tuple[float | None, int]) -> str:
    rate, n = result
    return f"{rate:.3f} (n={n})" if rate is not None else f"n/a (n={n})"
