# trading-bot: rules for Claude

Adds only what the user's global CLAUDE.md does not already say.
Rules 1-3 come from the community "Karpathy-inspired" guidelines (multica-ai/andrej-karpathy-skills,
`CLAUDE.md`), which are drawn from Andrej Karpathy's public observations on LLM coding mistakes.
Read as a tool summary on 12.11.2026, not verbatim. The "think before coding" rule is left out: the
global rules "Never assume: ask" and plan mode already cover it.

## 1. Simplicity first
- Write the least code that makes the tests pass. No feature, option or setting nobody asked for.
- No abstraction for code used once (global rule: it becomes a function at the second use).
- No error handling for cases that cannot happen. For the ones that can (a bad LLM answer, a missing
  price, a failed push), do exactly what `docs/design-v3.md` says, nothing more.

## 2. Surgical changes
- Touch only the lines the task needs. Match the style around them.
- See unrelated dead code or a bug: say so, and do not fix it in the same change, unless it blocks the task.
- Delete only what your own change orphaned (global rule).

## 3. Goal-driven
- Name the check before writing code: which test shows it is done. A bug starts with a test that fails.
- A task with several steps: list the steps, each with its check, in the plan. In chat the global
  5-line reply limit wins.

## 4. This project (not from the guide)
- Tests are the spec. `tests/helpers.py` holds the contract. Never change a test to make code pass.
  A wrong fixture may be fixed, and a contract change (for example a function signature) is a
  decision: say so in the reply.
- Run all tests: `.venv/bin/python -W ignore -m unittest discover -s tests -t .`
- Packages: `yfinance`, `exchange_calendars`, `anthropic` only. Ask before adding any.
- Research first: before building or changing a part, read the best primary source for it (official docs, the library's own source, a paper) and say what was checked. A summary or snippet counts as partial.
- Design: `docs/design-v3.md`. A change that departs from it is listed as a decision in the reply.
