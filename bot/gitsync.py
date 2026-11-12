"""Push with one recovery step: on a conflict, pull --rebase once, then push once more."""
from typing import Callable


class PushFailed(Exception):
    pass


def push_with_rebase(run: Callable[[list[str]], int]) -> None:
    """`run(cmd)` runs a git command and returns its exit code. Fails loud if the retry also fails,
    so the job turns red and GitHub sends the failure email."""
    if run(["git", "push"]) == 0:
        return
    if run(["git", "pull", "--rebase"]) != 0:
        raise PushFailed("git pull --rebase failed")
    if run(["git", "push"]) != 0:
        raise PushFailed("git push failed again after the rebase")
