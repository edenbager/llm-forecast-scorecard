# Prediction-scoring report

4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year.

Log counts (all versions): ok 6, invalid 0, no data 0, no run 0, late 0, split 0, budget 0
Versions tried: v1, v2
API spend this month (estimate from token counts): $0.0014 of $0.25 budget

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

- n_days: 4, calls scored: 40
- Hit rate (each on its own calls that picked a side): LLM 0.583 (n=24); base_rate 0.590 (n=39); coin flip 0.500
- Brier: LLM 0.248, base_rate 0.247, always 0.5: 0.250
- Main result: mean per-day (LLM Brier - base_rate Brier) +0.001; interval needs 20+ days

Calibration (p_up buckets):

| bucket | n | mean p_up | share up |
|---|---|---|---|
| <0.45 | 2 | hidden (n < 30) | hidden (n < 30) |
| 0.45-0.55 | 38 | 0.490 | 0.474 |
| >0.55 | 0 | hidden (n < 30) | hidden (n < 30) |
