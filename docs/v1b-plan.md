# v1b plan: "will X beat SPY tomorrow?" (built, live since 14.11.2026; decision 12 in design-v3.md)

Written 13.11.2026 while Eden was away. Merge this PR = yes to the plan, close = no. A departure from `docs/design-v3.md`: listed as a decision below.

## Why
- Outcome correlation between our 10 stocks: up/down 0.15 (about 4.2 independent calls a day), "beat SPY" -0.02 (about 10 a day). Computed on 253 days of the stored closes (13.11). More independent calls = proof about 2.4x sooner.
- Labels use raw Close (stored Adj Close equals Close on the fetch day for 10 of 10 tickers).

## What the code does today (read 13.11: runner.py, prompt.py, score.py, validate.py, config.json)
- One call a day, write-once call file, one `prompt_version` in `config.json`, label = Close(D+1) vs Close(D), scores keyed by version.
- Tickers are fetched, snapshotted and scored from `config["tickers"]`; SPY is in none of these.

## Decision to make (Option A recommended)
- **A. Replace** the question from v1 to v2 ("beats SPY") before the first real call. Nothing real has been scored yet (both Actions runs failed at the API key), so no data is lost. Smallest change, cost unchanged.
- **B. Both**, two calls a day. Needs the write-once rule, call files, ledger, report and runlog to become per version. About 3x the code, 2x the API cost. Not recommended until A shows the bot works.

## Option A: steps, each with its check (tests first)
1. `config.json`: add `"benchmark": "SPY"`; `prompt_version` "v2". Check: a test that config loads and has both.
2. Fetch SPY with the tickers, store it in the snapshot and in `history.csv`, but never ask the LLM about it. Check: test that SPY is in the snapshot and absent from the prompt's answer keys.
3. Prompt v2: same layout, SPY's closes added as the first line, question = "chance that it returns more than SPY on the next trading day". Check: a test that no close after day D appears (leak guard) and that the ticker list sent equals the stock list.
4. Label for v2: `outcome = "up"` if stock return > SPY return, `"down"` if less, flat = left out (same rule as today). Split on D+1 leaves the ticker out, and a SPY split cannot happen in practice (not handled, noted). Check: score tests for beat, lag, tie, missing SPY bar (all tickers left out).
5. Baseline for v2: `base_rate` of "beat SPY" over the stored history (about 50% by construction, to be measured). Check: test on a small fixture.
6. Report text: say which question the version asks. Check: report test.

Size estimate (not measured): about 120 changed lines, 10 to 14 new tests, one review pass.

## Open data checks (not done)
- Whether SPY needs dividends: effect about 1 basis point a quarter, ignored (estimate).
- Prompt cost with the extra SPY line: about 20 more tokens a day (estimate).
