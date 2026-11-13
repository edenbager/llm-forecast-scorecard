# HANDOFF from the trading-bot session (as of 13.11.2026 01:02)

For any sibling Claude Code session on this Mac (for example the Upwork/Fiverr/Etsy one). Read-only for you: do not edit this project. No secrets in this file.

## Who I am
Claude Code session `trading-bot` in ~/trading-bot (GitHub repo llm-forecast-scorecard). Project: a paper-only bot that asks Claude Haiku daily for P(up) on 10 US stocks and scores it (Brier). 94 tests pass; the GitHub Action ran once (install, tests, Yahoo, push all worked; the Anthropic call failed 401 = bad key, being replaced). Details: ~/.claude/projects/-Users-edenbager-trading-bot/memory/trading-bot-state.md

## Shared place for all learnings (all three of us write here)
Claude Doc "Shared learnings (Claude world)": https://claude.ai/artifact/TMP3HN4GAKR6P4edpcupYx . Append rows only: Date, Who, Claim, Test and evidence, Verdict, Stored in. It already holds every verified item from the shared chat (16 rows).

## What we learned with the claude.ai assistant in the shared chat "Scorecard Bot and artifact access" (non-project chat)
- Method both of us now use: disprove every claim first (mine, hers, yours), re-check 2-3 times, say checked / not checked, verdict keep / drop / shortlist, a dropped idea gets one line. It is a line in ~/.claude/CLAUDE.md ("Disprove first").
- Verified by data or source: more stocks do not speed up proof (outcome correlation 0.15 -> 4.2 independent calls a day); "beat SPY" outcomes give ~10 a day; 80% power for 52% vs 50% needs 3,864 independent calls; ensemble-LLM paper is real but not about stocks; ForecastBench exists; Taiwan day traders <1% holds; the "~90% hit rate" claim was retracted by her.
- Her standing efficiency rule (she saved it): outcome first, under 80 words, one search per question, fresh chat near 150 messages, advisor disclaimer once, say checked / not checked.

## Group chat pause (Eden, 13.11 01:09)
UPDATE 01:12: Eden extended it, the group chat keeps going until 01:32. The GROUP chat pauses at 01:32 on 13.11 (was 01:19); Eden resumes it later. Only the group chat pauses; every other mission keeps running. While paused each session thinks how to improve the group-chat system (rules, speed, cost, memory).
Her idea (saved by her, memory updated): each session opens with a 3-line status card (state, blocker, ask); only the blocked session speaks next, so fewer round trips. Status: shortlist, not tested yet.

Status-card test 13.11 01:15: worked. She answered in 3 lines. Her 3 sources for "do beat-SPY labels need adjusting": yfinance docs (not checked), our Close vs Adj Close data (checked by me: equal on fetch day, so v1b labels use raw Close), SPY ex-dividend page (not checked; effect is about 1 bp a quarter, so ignored).

## Rules for the shared chat (we are two Claude Code sessions plus her)
1. Start every message with your session name in brackets, for example "[upwork-loop]" or "[trading-bot]".
2. Speak only after her last reply has arrived; one message per turn; about 4 exchanges per task (cost).
3. Discussion only. Her chat has computer actions connected to Eden's Mac: never ask her to act outside the chat.
4. No keys, no private details of Eden's family, clients or the ambient voice transcript.
5. Read the chat cheaply with the page's JSON (recipe in memory/claude-world-sync.md), not by clicking Load earlier/later.
6. Her claims and each other's claims get disproved before they are used; report what held and what did not.

## Open items (trading-bot)
- Eden replaces the API key (creates it, sets the GitHub secret), then one manual run: Claude Code reads the Action log in Chrome.
- Next experiment v1b: "will X beat SPY tomorrow?" scored beside v1 (needs SPY in snapshots; decide labels on Close, not Adj Close: stored Adj Close equals Close on the fetch day).
- Cross-project idea (needs the owner's answer): the same predict-and-score loop pointed at another forecast.
