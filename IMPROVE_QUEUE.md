# IMPROVE_QUEUE (local, TEST-safe work only; top item first)

Rules: each item needs a failing test or a checkable read first (CLAUDE.md rule 3). A change to the live bot goes in a PR for Eden to merge. An empty tick ends in one line.

1. Read the first v2 run after Mon 16.11 22:37 UTC (runs can start hours late): status, `calls/2026-11-16.json` has `prompt_version` v2 and `benchmark` SPY, `usage.csv` row, `log.csv` rows. Blocked until that run exists. AUTOMATED 14.11: `watchdog.yml` (PR #10) runs Tue-Sat 09:17 UTC and opens a "Bot check failed" issue if the previous day's call is missing or does not match config. No issue by Tue 17.11 = fine; still read the numbers once.
2. DONE 14.11: `report.py` scores each prompt_version on its own (`summarize_by_version`, docstring line 1). Still look at the real `report.md` after the first scored v2 day (one trading day after its call).
3. DROPPED 14.11: `--dry-run` flag. Prompt building is already tested offline (`tests/test_leak.py` and others), the manual smoke test covers the key, the watchdog covers the stored call. Nothing left for it to test.
4. Deleted by Eden's click only: old key `trading-bot-daily` (after item 1 passes); federation setup (see HANDOFF.md).

Dropped (one line each): review findings 4, 5, 6, 7 of PR #4 (checked against the code, 14.11). Debug key-check step (removed in PR #6).
