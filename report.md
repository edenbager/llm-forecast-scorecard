# Prediction-scoring report

4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year.

Log counts (all versions): ok 7, invalid 0, no data 0, no run 2, late 0, split 0, budget 0
Versions tried: v1, v2
API spend this month (estimate from token counts): $0.0016 of $0.25 budget

## Prompt version v1

- n_days: 1, calls scored: 10
- Hit rate (each on its own calls that picked a side): LLM 0.333 (n=6); base_rate 0.625 (n=8); coin flip 0.500
- Brier: LLM 0.251, base_rate 0.252, always 0.5: 0.250
- Main result: mean per-day (LLM Brier - base_rate Brier) -0.001; interval needs 20+ days

Calibration (p_up buckets):

| bucket | n | mean p_up | share up |
|---|---|---|---|
| <0.45 | 0 | hidden (n < 30) | hidden (n < 30) |
| 0.45-0.55 | 10 | hidden (n < 30) | hidden (n < 30) |
| >0.55 | 0 | hidden (n < 30) | hidden (n < 30) |

## Prompt version v2

- n_days: 5, calls scored: 50
- Hit rate (each on its own calls that picked a side): LLM 0.531 (n=32); base_rate 0.571 (n=49); coin flip 0.500
- Brier: LLM 0.254, base_rate 0.247, always 0.5: 0.250
- Main result: mean per-day (LLM Brier - base_rate Brier) +0.007; interval needs 20+ days

Calibration (p_up buckets):

| bucket | n | mean p_up | share up |
|---|---|---|---|
| <0.45 | 7 | hidden (n < 30) | hidden (n < 30) |
| 0.45-0.55 | 42 | 0.489 | 0.429 |
| >0.55 | 1 | hidden (n < 30) | hidden (n < 30) |
