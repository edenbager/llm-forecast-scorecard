"""One-time day-0 setup: freeze the 10 tickers and save one year of closes. Run once, then commit.

    python -m bot.init_day0 --day0 2026-11-11

It refuses to overwrite: the frozen list and the history file are written once and never changed.
"""
import argparse
import csv
import io
import json
from datetime import date
from pathlib import Path

from bot import market, store, yahoo

# Top 10 COMPANIES of the S&P 500 by weight on 2026-11-11 (fund top-holdings pages, same figures on
# both). Alphabet is listed twice (GOOGL 2.62%, GOOG 2.10%): GOOG is skipped, being the same company,
# and BRK-B (1.67%, rank 11) takes the tenth place.
DAY0_TICKERS = ["AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "AVGO", "META", "LLY", "TSLA", "BRK-B"]
WEIGHTS_SOURCE = ("SPY top holdings: ssga.com SPY page and stockanalysis.com/etf/spy/holdings "
                  "(same figures on both, so possibly one data feed). GOOG skipped as the second "
                  "Alphabet share class; BRK-B was rank 11 and TSLA 1.68% vs BRK-B 1.67%.")
WEIGHTS_AS_OF = "2026-11-11 (pages say 'Updated Nov 11, 2026')"
MIN_CLOSES = 21        # the prompt shows up to 20 closes, and a baseline needs at least one price move


def build_config(day0: date, model: str = "claude-haiku-5-5", prompt_version: str = "v1") -> dict:
    return {"tickers": DAY0_TICKERS, "prompt_version": prompt_version, "model": model,
            "day0": day0.isoformat(), "weights_source": WEIGHTS_SOURCE, "weights_as_of": WEIGHTS_AS_OF}


def write_day0(root: Path, config: dict, closes: dict[str, list[tuple[date, float]]]) -> None:
    root = Path(root)
    short = [t for t in config["tickers"] if len(closes.get(t, [])) < MIN_CLOSES]
    if short:
        raise ValueError(f"too few closes (need {MIN_CLOSES}) for: {short}")
    config_path, history_path = root / "config.json", root / "data" / "history.csv"
    for path in (config_path, history_path):
        if path.exists():
            raise FileExistsError(f"{path} exists: day 0 is written once")
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(["date", "ticker", "close"])
    for ticker in config["tickers"]:
        for when, close in sorted(closes[ticker]):
            writer.writerow([when.isoformat(), ticker, close])
    store.write_atomic(history_path, out.getvalue())
    store.write_atomic(config_path, json.dumps(config, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write config.json and data/history.csv (once).")
    parser.add_argument("--day0", required=True, type=date.fromisoformat, help="last full trading day, YYYY-MM-DD")
    args = parser.parse_args()
    if not market.is_trading_day(args.day0):
        parser.error(f"{args.day0} is not a trading day")
    write_day0(Path.cwd(), build_config(args.day0), yahoo.download_year(DAY0_TICKERS, args.day0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
