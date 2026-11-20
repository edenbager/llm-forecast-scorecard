# Prediction-scoring report

4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year.

Log counts (all versions): ok 5, invalid 0, no data 0, no run 0, late 0, split 0, budget 0
Versions tried: v1, v2
API spend this month (estimate from token counts): $0.0011 of $0.25 budget

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

- n_days: 3, calls scored: 30
- Hit rate (each on its own calls that picked a side): LLM 0.556 (n=18); base_rate 0.517 (n=29); coin flip 0.500
- Brier: LLM 0.249, base_rate 0.248, always 0.5: 0.250
- Main result: mean per-day (LLM Brier - base_rate Brier) +0.000; interval needs 20+ days

Calibration (p_up buckets):

| bucket | n | mean p_up | share up |
|---|---|---|---|
| <0.45 | 2 | hidden (n < 30) | hidden (n < 30) |
| 0.45-0.55 | 28 | hidden (n < 30) | hidden (n < 30) |
| >0.55 | 0 | hidden (n < 30) | hidden (n < 30) |
