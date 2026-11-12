"""Tests 11-15: the LLM's answer must be valid, or it is marked invalid."""
import json
import unittest

from bot.caller import make_call
from bot.validate import InvalidCall, parse_and_validate
from tests.helpers import TICKERS, FakeLLM, good_reply


def _reply_with(mutate):
    rows = [{"ticker": t, "p_up": 0.6} for t in TICKERS]
    mutate(rows)
    return json.dumps(rows)          # json.dumps writes float('nan') as NaN


class Validation(unittest.TestCase):
    def test_11_valid_json_gives_10_rows(self):
        out = parse_and_validate(good_reply(p=0.6), TICKERS)
        self.assertEqual(out, {t: 0.6 for t in TICKERS})
        self.assertEqual(len(out), 10)

    def test_12_markdown_fenced_json_is_parsed(self):
        fenced = "```json\n" + good_reply(p=0.4) + "\n```"
        self.assertEqual(parse_and_validate(fenced, TICKERS), {t: 0.4 for t in TICKERS})

    def test_13_missing_unknown_duplicate_ticker_are_invalid_and_retried_once(self):
        missing = _reply_with(lambda r: r.pop())
        unknown = _reply_with(lambda r: r[0].update(ticker="ZZZZ"))
        duplicate = _reply_with(lambda r: r[1].update(ticker="AAPL"))
        for name, text in [("missing", missing), ("unknown", unknown), ("duplicate", duplicate)]:
            with self.subTest(name):
                with self.assertRaises(InvalidCall):
                    parse_and_validate(text, TICKERS)
                llm = FakeLLM([text, good_reply()])
                out = make_call("prompt", llm, TICKERS)
                self.assertEqual(len(llm.prompts), 2)          # exactly one retry
                self.assertEqual(out.status, "ok")

    def test_14_bad_p_up_values_are_invalid(self):
        for name, value in [("too high", 1.2), ("negative", -0.1),
                            ("string", "0.6"), ("NaN", float("nan"))]:
            with self.subTest(name):
                text = _reply_with(lambda r, v=value: r[0].update(p_up=v))
                with self.assertRaises(InvalidCall):
                    parse_and_validate(text, TICKERS)

    def test_15_retry_succeeds_is_stored_retry_fails_is_invalid(self):
        bad = _reply_with(lambda r: r.pop())
        ok_llm = FakeLLM([bad, good_reply(p=0.7)])
        ok = make_call("prompt", ok_llm, TICKERS)
        self.assertEqual(ok.status, "ok")
        self.assertEqual(ok.p_up, {t: 0.7 for t in TICKERS})

        fail_llm = FakeLLM([bad, bad, good_reply()])
        fail = make_call("prompt", fail_llm, TICKERS)
        self.assertEqual(fail.status, "invalid")
        self.assertIsNone(fail.p_up)
        self.assertEqual(len(fail_llm.prompts), 2)             # never a third try


if __name__ == "__main__":
    unittest.main()
