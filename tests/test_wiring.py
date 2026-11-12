"""Extra tests (not in the design's 28): the real git adapter and the wiring of `python -m bot`. No network."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot.app import build_deps
from bot.fetch import PartialBarError
from bot.gitops import Git
from bot.llm import make_llm
from tests.helpers import TICKERS, d, utc

DIFF = ["git", "diff", "--cached", "--quiet"]


def _fake_run(codes=None, push_codes=()):
    """Records every command. `codes` maps a command (tuple) to its exit code; default 0."""
    cmds, pushes = [], iter(push_codes)
    codes = codes or {}

    def run(cmd):
        cmds.append(cmd)
        if cmd == ["git", "push"]:
            return next(pushes, 0)
        return codes.get(tuple(cmd), 0)
    return run, cmds


class GitAdapter(unittest.TestCase):
    def test_changes_are_added_committed_and_pushed(self):
        run, cmds = _fake_run({tuple(DIFF): 1})                  # exit 1 = there are staged changes
        Git(run).commit_push("bot run 2026-11-10")
        self.assertEqual(cmds, [["git", "add", "-A"], DIFF,
                                ["git", "commit", "-m", "bot run 2026-11-10"], ["git", "push"]])

    def test_nothing_to_commit_stops_quietly(self):
        run, cmds = _fake_run({tuple(DIFF): 0})                  # exit 0 = nothing staged
        Git(run).commit_push("bot run 2026-11-10")
        self.assertEqual(cmds, [["git", "add", "-A"], DIFF])

    def test_push_conflict_pulls_with_rebase_once_then_pushes(self):
        run, cmds = _fake_run({tuple(DIFF): 1}, push_codes=[1, 0])
        Git(run).commit_push("m")
        self.assertEqual(cmds[-3:], [["git", "push"], ["git", "pull", "--rebase"], ["git", "push"]])

    def test_a_failed_add_or_commit_fails_loud(self):
        for broken in (["git", "add", "-A"], ["git", "commit", "-m", "m"]):
            with self.subTest(broken[1]):
                run, _ = _fake_run({tuple(DIFF): 1, tuple(broken): 128})
                with self.assertRaises(RuntimeError):
                    Git(run).commit_push("m")


class Wiring(unittest.TestCase):
    def test_deps_are_built_from_config_without_network_and_fetch_refuses_a_live_bar(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy"}):
            (Path(tmp) / "config.json").write_text(json.dumps(
                {"tickers": TICKERS, "prompt_version": "v1", "model": "claude-haiku-5-5"}))
            deps = build_deps(Path(tmp))
            self.assertTrue(callable(deps.fetch) and callable(deps.llm))
            self.assertIsInstance(deps.git, Git)
            with self.assertRaises(PartialBarError):              # 13:00 New York: market still open
                deps.fetch(TICKERS, d("2026-11-13"), utc("2026-11-13T18:00:00"))

    def test_building_the_llm_needs_no_api_key_until_it_is_called(self):
        with mock.patch.dict(os.environ, {}, clear=True):          # a Saturday gate-exit has no key need
            self.assertTrue(callable(make_llm("claude-haiku-5-5")))


if __name__ == "__main__":
    unittest.main()
