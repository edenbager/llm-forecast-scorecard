# Prediction-scoring bot: design v3 (DRAFT, not approved, 12.11.2026)

Paper only. No real money, no broker, no trades, no stock picks. A learning and CV project.
Each trading day the LLM gives `p_up` for 10 stocks: the chance (0 to 1) that the stock closes higher
on the next trading day. Code scores those calls against what really happened.

Built from: the v2 draft + Review 2 in `docs/review-2026-11-12.md` (rows cited as R1..R14).
Anything not checked against a real source is marked "likely".

## Words used here
- **Day D**: the trading day the call is made on. **D+1**: the next trading day (Friday's D+1 is Monday).
- **Leak**: data from after the call sneaking into the call or its baseline. Like grading a test with the answer key open.
- **Baseline**: a dumb forecaster to beat. If the LLM can't beat "guess the usual up-day share", it has no skill.
- **Brier score**: the mean of (p_up − outcome)², outcome 1 = up, 0 = down. 0 is perfect; always saying 0.5 gives 0.25.
  Example: p_up 0.7 and the stock went up → (0.7 − 1)² = 0.09.
- **Bootstrap**: resample the days with replacement many times to see how much the result wobbles.
- **Write-once**: a call file, once saved, is never changed. A re-run reads it; it never makes a new one.

## Changes from v2
| v2 | v3 | Why (row) |
|---|---|---|
| Baselines computed at report time | Computed on day D from the day-D snapshot, stored in the call row | R1 leak |
| "Safe to re-run" (unclear) | Write-once calls; no new call after D+1's open (13:30 UTC, 14:30 in winter, likely: use the calendar's open time) | R2 leak |
| Interval over all calls | Day is the unit: per-day difference vs base rate, bootstrap over days | R3 |
| "4 weeks" as a result | 4 weeks only proves the pipeline works; stated in every report | R4 |
| "always-up" vs 50% | Renamed `base_rate`; LLM compared to base_rate and to 50% | R5 |
| Momentum baseline | Cut | R6, R12 |
| Score on adjusted closes | Score on `Close`; tie p_up = 0.5 excluded; flat close excluded | R7 |
| Calibration in many buckets | 3 buckets, n shown, bucket hidden if n < 30 | R8 |
| yfinance, no plan B | Retry with backoff; per-ticker "no data"; D stored as the LLM saw it | R9 |
| "no run" written by the missing run | The next run writes "no run" rows from the calendar; `git pull --rebase` before push | R10 |
| RSS headlines in v1 | v1 is prices only; headlines are v2 (a version ablation) | R11, R12 |
| Daily 1-year snapshot | One day-0 history file, then only the new bar each day | R12 |
| Model name | Pinned exact model ID (current IDs have no date suffix); response ID stored | R13 |

## Flow (v1, prices only)
```
GitHub Actions, cron 22:30 UTC Mon-Fri, one concurrency group
  1. gate: not a trading day (calendar) → exit 0
  2. backfill: compare log.csv dates with the calendar → write "no run" rows for missed days (never fill in calls)
  3. score: for each stored call from day D where D+1 = today: read today's Close for D and D+1 from the stored D
     snapshot (D) and today's fetch (D+1); label up if Close(D+1) > Close(D); equal → "flat", excluded
  4. fetch: yfinance, today's bar for 10 tickers; retry 3x with backoff; a ticker with no data → "no data" row
     → save data/snapshots/<D>.csv (Close + Adj Close, fetch time)
  5. call: if calls/<D>.json exists → stop (write-once). If now > D+1 open → stop, log "late".
     prompt = prompt_version + last 20 closes per ticker from the stored history (truncated at D)
     LLM (pinned exact model ID, effort low, no tools, no temperature: it returns 400 now)
       → structured output (output_config.format JSON schema) [{ticker, p_up}] × 10
     stop_reason = refusal or max_tokens → "invalid" row, never read the content
     validate: exactly the 10 frozen tickers, once each, p_up a number in [0,1]; invalid → 1 retry → "invalid"
     store calls/<D>.json: prompt, prompt_version, model ID, response ID, raw output, call timestamp,
     base_rate per ticker (from history truncated at D)
  6. git pull --rebase, commit, push
weekly: report.md
```

## Config (day 0, frozen, committed)
- 10 tickers = top 10 S&P 500 by weight on day 0; weight source and date written in the file.
- `prompt_version`: any change to the prompt, model or tickers = a new version, scored separately.
- `data/history.csv`: 1 year of closes per ticker up to day 0, committed once.
- API key only in an Actions secret. Never in the repo.

## Report (weekly `report.md`)
- n_days, n calls scored, n invalid, n "no data", n "no run", n "late", versions tried.
- Hit rate: LLM vs base_rate vs 50%.
- Brier: LLM vs base_rate vs 0.25 (always 0.5).
- Main result: mean per-day (LLM Brier − base_rate Brier), 95% bootstrap interval over days.
- Calibration: 3 buckets (p_up < 0.45, 0.45-0.55, > 0.55, cut points likely to change), n each, hidden if n < 30.
- Fixed line: "4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year."

## Tests (written before code)
Each test: input → expected output. Grouped by step.

**Gate and calendar**
1. Saturday → exit 0, nothing written.
2. Market holiday (e.g. 25 Dec) → exit 0.
3. Friday call → D+1 is Monday; Wednesday before a holiday Thursday → D+1 is Friday.
4. Early-close day → D+1 open time comes from the calendar.
5. A missed Tuesday → Wednesday's run writes one "no run" row for Tuesday, no call.

**Write-once and timing**
6. calls/<D>.json exists → a re-run makes no LLM call and changes no file.
7. Run after D+1's open → no call, "late" logged.
8. The same day run twice → scored once.

**Leak**
9. base_rate from history truncated at D equals a hand-computed value; adding a later row doesn't change it.
10. The prompt contains no date after D.

**Validation**
11. Valid JSON → 10 rows stored.
12. Markdown-fenced JSON (```json ... ```) → parsed.
13. Missing ticker / unknown ticker / duplicate ticker → invalid → one retry.
14. p_up = 1.2, −0.1, "0.6" (string), NaN → invalid.
15. Retry succeeds → stored; retry fails → "invalid" row.

**Fetch**
16. yfinance raises twice then works → data stored after retries.
17. One ticker empty → "no data" for that ticker only; the other 9 still called.
18. A partial live bar (fetch time before the close) → rejected.

**Score**
19. Close(D+1) > Close(D) → up; less → down; equal → flat, excluded.
20. p_up = 0.5 → excluded from hit rate (still in Brier).
21. Ex-dividend day: Close drops less than the dividend → scored down on `Close` (not adjusted).
22. One ticker missing at D+1 → that ticker unscored, others scored.
23. Split day: history file not rewritten; the split is noted (likely rare in 4 weeks).

**Stats**
24. Brier for [0.7 up, 0.2 down] = (0.09 + 0.04) / 2 = 0.065.
25. Bootstrap with all days equal → interval width 0.
26. Calibration bucket with n = 29 → hidden.
27. Two prompt_versions → scored in separate tables.

**Git**
28. Push conflict → pull --rebase → push succeeds; second conflict → run fails loud (failure email).

## Out of scope for v1
- Headlines (RSS): v2, as a new prompt_version, with: only items published before fetch time, max 20 newest,
  max 200 characters, no-timestamp items dropped, headline count logged, passed as a labelled untrusted data block.
- The paper simulator (fake 10,000, fees): v3 or later.
- A fallback data source (likely needed if yfinance is blocked on Actions IPs): add only after it fails.

## Decided (Eden, 12.11.2026)
Facts from the claude-api skill (cached 3.11.2026). Costs are likely, at ~3K input tokens a day:
1. Model: `claude-haiku-5-5` (~$0.02/month), chosen by Eden. Upgrade path: `claude-opus-5-5` at effort low
   (~$1/month), run as a new prompt_version.
2. Repo: private (Claude's recommendation, no objection). Secrets are safe either way; private hides the API bill
   history. The daily commit keeps the schedule alive.
3. Packages: `yfinance`, `exchange_calendars`, `anthropic`. Eden approved the install, in a project venv, once coding starts.

Decided later on 12.11.2026 (Eden chose, or Claude built and listed it in the reply):
4. Tickers: top 10 companies, not 10 holdings. GOOG skipped (second Alphabet class), BRK-B takes rank 10. Day 0 = 2026-11-11.
5. Split on D+1: that ticker is left out of that day's scoring (its two Close prices are on different scales). The split is logged.
6. Late day: no new call, but the day is still fetched and yesterday's call is still scored.
7. Spending guard (`bot/budget.py`): `usage.csv` ledger, monthly budget from `BOT_MONTHLY_BUDGET_USD` (default 0.25, 0 = pause the LLM). The hard stop is prepaid credits with auto-reload off in the Anthropic Console.
8. LLM answer format: an object `{ticker: p_up}` (strict schema) instead of a list; prompt shows closes only, with `|` where a trading day is missing.
9. `report.md` is rewritten on every run that does real work, not only weekly.
