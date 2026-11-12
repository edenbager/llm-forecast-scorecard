"""A spending guard: the bot never calls the API if that call could push the month over its budget.

usage.csv is the ledger: one row per API reply (tokens as the API reported them, cost computed here).
The budget comes from the BOT_MONTHLY_BUDGET_USD environment variable (default below); 0 pauses the
LLM completely. This guard is a second line of defence: the real hard stop is prepaid credits with
auto-reload off and a monthly spend limit in the Anthropic Console.
"""
import csv
import os
from datetime import date
from pathlib import Path

from bot.caller import MAX_TRIES
from bot.llm import MAX_TOKENS

DEFAULT_BUDGET_USD = 0.25
USAGE_FIELDS = ["day", "prompt_version", "model", "input_tokens", "output_tokens", "cost_usd"]
CHARS_PER_TOKEN = 3          # conservative: real text averages about 4, so the input is over-estimated

# (input, output) US dollars per million tokens, for prompts up to 100K tokens. Source: the claude-api
# skill's price table, cached 2026-11-03. Check it against the live pricing page.
PRICES = {"claude-haiku-5-5": (0.10, 0.50)}


def monthly_budget() -> float:
    return float(os.environ.get("BOT_MONTHLY_BUDGET_USD") or DEFAULT_BUDGET_USD)   # empty counts as unset


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
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
    month = day.strftime("%Y-%m")
    return sum(float(r["cost_usd"]) for r in _rows(root) if r["day"].startswith(month))


def worst_case_cost(model: str, prompt: str) -> float:
    """Most the next call can cost: every try sends the prompt and uses the whole output cap."""
    input_tokens = len(prompt) / CHARS_PER_TOKEN
    return MAX_TRIES * cost_usd(model, input_tokens, MAX_TOKENS)


def allows_call(root: Path, day: date, model: str, prompt: str) -> bool:
    return month_spent(root, day) + worst_case_cost(model, prompt) <= monthly_budget()


def record(root: Path, day: date, version: str, model: str, replies: list) -> None:
    path = Path(root) / "usage.csv"
    is_new = not path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(USAGE_FIELDS)
        for reply in replies:
            writer.writerow([day.isoformat(), version, model, reply.input_tokens, reply.output_tokens,
                             f"{cost_usd(model, reply.input_tokens, reply.output_tokens):.6f}"])
