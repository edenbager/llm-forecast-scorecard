"""One LLM call for one day: ask, validate, retry once, else mark invalid."""
from dataclasses import dataclass
from typing import Callable

from bot.llm import LLMReply
from bot.validate import InvalidCall, parse_and_validate

MAX_TRIES = 2          # the first try plus exactly one retry
NEVER_READ = {"refusal", "max_tokens"}    # content of these replies is not trusted or parsed


@dataclass
class CallOutcome:
    status: str                      # "ok" or "invalid"
    p_up: dict[str, float] | None    # None when invalid
    replies: list[LLMReply]          # every reply received, for the stored record


def make_call(prompt: str, llm: Callable[[str, list[str]], LLMReply], tickers: list[str]) -> CallOutcome:
    replies: list[LLMReply] = []
    for _ in range(MAX_TRIES):
        reply = llm(prompt, tickers)
        replies.append(reply)
        if reply.stop_reason in NEVER_READ:
            return CallOutcome("invalid", None, replies)   # a retry would likely fail the same way
        try:
            return CallOutcome("ok", parse_and_validate(reply.text, tickers), replies)
        except InvalidCall:
            continue
    return CallOutcome("invalid", None, replies)
