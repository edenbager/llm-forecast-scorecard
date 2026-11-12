"""Extra tests (not in the design's 28): the Anthropic adapter, cheap and strict by design. No network."""
import json
import re
import unittest
from datetime import timedelta
from types import SimpleNamespace

from bot.caller import make_call
from bot.llm import make_llm, reply_schema
from bot.prompt import build_prompt
from bot.validate import InvalidCall, parse_and_validate
from tests.helpers import TICKERS, FakeLLM, d, good_reply


class FakeClient:
    """Stands in for anthropic.Anthropic(): records the request, returns a canned response."""

    def __init__(self, text='{"AAPL": 0.6}', stop_reason="end_turn"):
        self.calls, self.messages = [], self
        self._text, self._stop = text, stop_reason

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)],
                               stop_reason=self._stop, id="msg_42", model="claude-haiku-5-5",
                               usage=SimpleNamespace(input_tokens=500, output_tokens=120))


class LlmAdapter(unittest.TestCase):
    def test_request_is_small_strict_and_has_no_forbidden_options(self):
        client = FakeClient()
        reply = make_llm("claude-haiku-5-5", client=client)("the prompt", ["AAPL", "BRK-B"])
        (call,) = client.calls
        self.assertEqual(call["model"], "claude-haiku-5-5")
        self.assertEqual(call["output_config"]["effort"], "low")          # least hidden thinking
        self.assertLessEqual(call["max_tokens"], 2000)                    # the answer is ~100 tokens
        for banned in ("temperature", "top_p", "top_k", "thinking", "tools", "tool_choice"):
            self.assertNotIn(banned, call)
        self.assertEqual(call["messages"], [{"role": "user", "content": "the prompt"}])
        self.assertEqual((reply.text, reply.stop_reason, reply.response_id, reply.model),
                         ('{"AAPL": 0.6}', "end_turn", "msg_42", "claude-haiku-5-5"))
        self.assertEqual((reply.input_tokens, reply.output_tokens), (500, 120))   # what the API billed

    def test_schema_demands_exactly_the_days_tickers_once_each(self):
        schema = reply_schema(["AAPL", "BRK-B"])
        self.assertEqual(schema, {"type": "object",
                                  "properties": {"AAPL": {"type": "number"}, "BRK-B": {"type": "number"}},
                                  "required": ["AAPL", "BRK-B"], "additionalProperties": False})
        client = FakeClient()
        make_llm("claude-haiku-5-5", client=client)("p", ["AAPL", "BRK-B"])
        sent = client.calls[0]["output_config"]["format"]
        self.assertEqual((sent["type"], sent["schema"]), ("json_schema", schema))


class ObjectAnswers(unittest.TestCase):
    def test_object_form_is_accepted_and_checked_like_the_list_form(self):
        self.assertEqual(parse_and_validate(json.dumps({t: 0.4 for t in TICKERS}), TICKERS),
                         {t: 0.4 for t in TICKERS})
        too_few = {t: 0.4 for t in TICKERS[:-1]}
        out_of_range = {**{t: 0.4 for t in TICKERS}, "AAPL": 1.2}
        as_text = {**{t: 0.4 for t in TICKERS}, "AAPL": "0.4"}
        for name, bad in [("missing", too_few), ("range", out_of_range), ("string", as_text)]:
            with self.subTest(name), self.assertRaises(InvalidCall):
                parse_and_validate(json.dumps(bad), TICKERS)


class RefusalAndLength(unittest.TestCase):
    def test_refusal_or_max_tokens_is_invalid_at_once_and_never_parsed(self):
        for stop in ("refusal", "max_tokens"):
            with self.subTest(stop):
                llm = FakeLLM([good_reply()], stop_reason=stop)    # content would be valid: must be ignored
                out = make_call("p", llm, TICKERS)
                self.assertEqual((out.status, out.p_up), ("invalid", None))
                self.assertEqual(len(llm.prompts), 1)              # no paid retry


class CompactPrompt(unittest.TestCase):
    def test_prompt_states_day_d_once_and_sends_only_closes(self):
        D = d("2026-11-06")
        history = {t: [(D - timedelta(days=i), 100.0 + i) for i in range(30)] for t in TICKERS}
        prompt = build_prompt(history, TICKERS, D, "v1")
        self.assertEqual(re.findall(r"\d{4}-\d{2}-\d{2}", prompt), ["2026-11-06"])
        line = next(l for l in prompt.splitlines() if l.startswith("AAPL:"))
        self.assertEqual(len(line.split(":", 1)[1].split(",")), 20)        # 20 closes, nothing else
        self.assertLess(len(prompt), 2500)                                 # measured: was 4,206, now ~1,976


if __name__ == "__main__":
    unittest.main()
