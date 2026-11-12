"""The real git step (flow step 6): commit what the run wrote, push, recover once from a conflict."""
import subprocess
from pathlib import Path
from typing import Callable

from bot.gitsync import push_with_rebase


def subprocess_runner(root: Path) -> Callable[[list[str]], int]:
    """run(cmd) -> exit code, executed inside the project folder."""
    return lambda cmd: subprocess.run(cmd, cwd=root).returncode


class Git:
    def __init__(self, run: Callable[[list[str]], int]):
        self.run = run

    def commit_push(self, message: str) -> None:
        self._must(["git", "add", "-A"])
        # `diff --cached --quiet` exits 0 when nothing is staged and 1 when something is.
        staged = self.run(["git", "diff", "--cached", "--quiet"])
        if staged == 0:
            return                          # the run changed nothing: no empty commit
        if staged != 1:
            raise RuntimeError(f"git diff --cached failed with exit code {staged}")
        self._must(["git", "commit", "-m", message])
        push_with_rebase(self.run)          # one pull --rebase on a conflict, then fail loud

    def _must(self, cmd: list[str]) -> None:
        code = self.run(cmd)
        if code != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed with exit code {code}")
