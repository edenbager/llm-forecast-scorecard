# CV bullets for the scorecard bot (DRAFT, 15.11.2026, local only)

Why: `~/upwork-demos/resume.md` (14 lines) lists 3 demo tools and not this bot. For student and junior roles (Eden's standing yes covers LinkedIn Easy Apply for those) a tested, unattended, cost-guarded project is the strongest line he has. Not measured: whether it raises the reply rate (estimate, test with one extra application batch). Nothing here claims results: the first scored day is 17.11.2026 and the first interval appears on 15.12.2026 (market.trading_days, run 15.11).

Every bullet carries its source so Eden can explain every word.

## Bullets (English, paste-ready)
1. Built a paper-only prediction-scoring bot in Python: each trading day Claude Haiku gives P(up) for 10 S&P 500 stocks, and code scores the calls against a base-rate baseline with the Brier score. No money, no trades.
   Source: docs/design-v3.md lines 3-5.
2. Wrote it test-first: 121 unit tests (unittest), including a leak test (the prompt may contain only closes up to day D) and write-once call files that a re-run never changes.
   Source: `.venv/bin/python -W ignore -m unittest discover -s tests -t .` printed "Ran 121 tests ... OK" on 15.11; tests/test_leak.py; design line 17.
3. Runs unattended on GitHub Actions (cron Mon-Fri 22:37 UTC), commits its own results, and has a spending guard (USD 0.25 monthly budget) plus a watchdog that opens a GitHub issue when a call is missing, mismatched or never scored.
   Source: .github/workflows/daily.yml line 5; bot/budget.py line 19; bot/watchdog.py.
4. Disproved its own ideas with data before building: measured outcome correlation of 0.15 across the 10 stocks (about 4 independent calls a day), so "add more stocks" was dropped and the question changed to "beats SPY" (correlation -0.02).
   Source: Shared learnings doc rows 13.11; design-v3 decision 12. The correlation figures are Eden's 13.11 measurement on 253 days of closes.

## Interview answer key (one line each, for the interview-drill skill)
- Why a base rate? A model that says 0.5 always has Brier 0.25; the baseline is the honest bar.
- Why write-once? A paid call must never be silently replaced; re-runs only read.
- What would make it fail? Yahoo down, SPY bar missing, a dropped GitHub run (catch-up scoring, decision 13), a stale key (watchdog).
- What it does not prove: no edge claim before about 390 days (13.11 estimate).

## Rules kept
- A CV line, not a LinkedIn post: Eden's rule is polished work only, and a bot with no scored days yet is not that.
- Eden decides the resume edit (client-facing document); the sibling session owns resume.md.
