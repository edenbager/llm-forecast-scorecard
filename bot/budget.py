"""A spending guard: the bot never calls the API if that call could push the month over its budget.

usage.csv is the ledger: one row per API reply (tokens as the API reported them, cost computed here).
The budget comes from the BOT_MONTHLY_BUDGET_USD environment variable (default below); 0 pauses the
LLM completely, and any unusable value also means 0 (fail closed). This guard is a second line of
defence: the real hard stop is prepaid credits with auto-reload off and a monthly spend limit in the
Anthropic Console.
"""
import csv
import math
import os
import sys
from datetime import date
from pathlib import Path

from bot.caller import MAX_TRIES
from bot.llm import CLIENT_RETRIES, MAX_TOKENS

DEFAULT_BUDGET_USD = 0.25
USAGE_FIELDS = ["day", "prompt_version", "model", "input_tokens", "output_tokens", "cost_usd"]
CHARS_PER_TOKEN = 2          # number-heavy text tokenizes at about 2 characters per token, so this is safe
OVERHEAD_TOKENS = 500        # the output schema and request framing: billed, but not in the prompt text

# (input, output) US dollars per million tokens, for prompts up to 100K tokens. Source: the claude-api
# skill's price table, cached 2026-11-03. Check it against the live pricing page.
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}


def monthly_budget() -> float:
    raw = os.environ.get("BOT_MONTHLY_BUDGET_USD", "")
    if not raw.strip():
        return DEFAULT_BUDGET_USD                       # an empty repo variable counts as unset
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value < 0:
        print(f"WARNING: BOT_MONTHLY_BUDGET_USD={raw!r} is not a usable number: budget treated as 0, "
              f"the LLM is paused", file=sys.stderr)
        return 0.0
    return value


def cost_usd(model: str, input_tokens: float, output_tokens: float) -> float:
    if model not in PRICES:
        raise ValueError(f"no price known for {model}: add it to budget.PRICES before using it")
    price_in, price_out = PRICES[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def _rows(root: Path) -> list[dict]:
    path = Path(root) / "usage.csv"
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def month_spent(root: Path, day: date) -> float:
    """Dollars logged in day's month. A damaged row stops the run: skipping it would under-count spend."""
    month = day.strftime("%Y-%m")
    total = 0.0
    for line_number, row in enumerate(_rows(root), start=2):
        try:
            if row["day"].startswith(month):
                total += float(row["cost_usd"])
        except (ValueError, TypeError, AttributeError) as err:
            raise ValueError(f"usage.csv line {line_number} is damaged ({row}): repair it by hand") from err
    return total


def worst_case_cost(model: str, prompt: str) -> float:
    """Most the next call can cost: every try, every SDK retry of it, the whole output cap each time."""
    input_tokens = len(prompt) / CHARS_PER_TOKEN + OVERHEAD_TOKENS
    return MAX_TRIES * (CLIENT_RETRIES + 1) * cost_usd(model, input_tokens, MAX_TOKENS)


def allows_call(root: Path, day: date, model: str, prompt: str) -> bool:
    return month_spent(root, day) + worst_case_cost(model, prompt) <= monthly_budget()


def record(root: Path, day: date, version: str, model: str, replies: list) -> None:
    """Append one row per reply. All rows are built first, so an error cannot leave a half-written batch."""
    rows = [[day.isoformat(), version, model, reply.input_tokens, reply.output_tokens,
             f"{cost_usd(model, reply.input_tokens, reply.output_tokens):.6f}"] for reply in replies]
    path = Path(root) / "usage.csv"
    is_new = not path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(USAGE_FIELDS)
        writer.writerows(rows)
