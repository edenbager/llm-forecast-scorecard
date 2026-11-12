"""Checks the LLM's answer. Anything unclear is invalid: a bad call is never guessed into a good one."""
import json
import math
import re


class InvalidCall(Exception):
    pass


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_and_validate(text: str, tickers: list[str]) -> dict[str, float]:
    """Return {ticker: p_up} for exactly the given tickers, once each, p_up a number in [0, 1]."""
    fenced = _FENCE.search(text)
    body = fenced.group(1) if fenced else text.strip()
    try:
        items = json.loads(body)
    except json.JSONDecodeError as err:
        raise InvalidCall(f"not JSON: {err}") from err
    if not isinstance(items, list):
        raise InvalidCall("expected a JSON list")

    result: dict[str, float] = {}
    for item in items:
        if not isinstance(item, dict) or "ticker" not in item or "p_up" not in item:
            raise InvalidCall(f"bad item: {item!r}")
        ticker, p_up = item["ticker"], item["p_up"]
        if ticker in result:
            raise InvalidCall(f"duplicate ticker {ticker!r}")
        # bool is a number in Python (True == 1), and "0.6" is a string: both are rejected.
        if isinstance(p_up, bool) or not isinstance(p_up, (int, float)):
            raise InvalidCall(f"p_up for {ticker} is not a number: {p_up!r}")
        if math.isnan(p_up) or not 0 <= p_up <= 1:
            raise InvalidCall(f"p_up for {ticker} not in [0, 1]: {p_up!r}")
        result[ticker] = float(p_up)

    if set(result) != set(tickers):
        raise InvalidCall(f"tickers differ: missing {set(tickers) - set(result)}, "
                          f"unknown {set(result) - set(tickers)}")
    return result
