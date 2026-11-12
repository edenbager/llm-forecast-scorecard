"""The LLM: one small reply box, and the adapter that asks Claude through the official SDK.

Goal: cheap and smart. Cost design: the small Haiku model, effort "low" (least hidden
thinking), a ~2000 token cap for a ~100 token answer, and a strict schema so the answer is rarely
invalid (an invalid answer means a paid retry).
"""
import functools
from dataclasses import dataclass
from typing import Callable

import anthropic

MAX_TOKENS = 2000
CLIENT_RETRIES = 4


@dataclass(frozen=True)
class LLMReply:
    text: str
    stop_reason: str
    response_id: str
    model: str


def reply_schema(tickers: list[str]) -> dict:
    """{"AAPL": number, ...}: every ticker required, none extra. So 'missing', 'unknown' and
    'duplicate' tickers cannot happen, and the answer has no repeated keys (fewer output tokens).
    The 0-to-1 range is not allowed in a schema; validate.py checks it."""
    return {"type": "object",
            "properties": {t: {"type": "number"} for t in tickers},
            "required": list(tickers),
            "additionalProperties": False}


def make_llm(model: str, client=None, max_tokens: int = MAX_TOKENS) -> Callable[[str, list[str]], LLMReply]:
    """Returns llm(prompt, tickers) -> LLMReply. The key comes from the ANTHROPIC_API_KEY environment
    variable (an Actions secret), never from the code. No temperature: newer models reject it."""
    # Built once, on the first call, so a weekend gate-exit needs no key. Extra SDK retries (the
    # default is 2) cover short overloads, because the job runs only once a day.
    get_client = (lambda: client) if client is not None else functools.cache(
        lambda: anthropic.Anthropic(max_retries=CLIENT_RETRIES))

    def llm(prompt: str, tickers: list[str]) -> LLMReply:
        response = get_client().messages.create(
            model=model,
            max_tokens=max_tokens,
            output_config={"effort": "low",
                           "format": {"type": "json_schema", "schema": reply_schema(tickers)}},
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMReply(text=text, stop_reason=response.stop_reason,
                        response_id=response.id, model=response.model)

    return llm
