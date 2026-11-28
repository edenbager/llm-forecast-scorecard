# Prediction-scoring report

4 weeks = pipeline check, not proof. A 5-point edge likely needs 1+ year.

Log counts (all versions): ok 8, invalid 0, no data 0, no run 2, late 0, split 0, budget 0
Versions tried: v1, v2
API spend this month (estimate from token counts): $0.0018 of $0.25 budget

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

- n_days: 6, calls scored: 60
- Hit rate (each on its own calls that picked a side): LLM 0.514 (n=37); base_rate 0.525 (n=59); coin flip 0.500
- Brier: LLM 0.254, base_rate 0.249, always 0.5: 0.250
- Main result: mean per-day (LLM Brier - base_rate Brier) +0.005; interval needs 20+ days

Calibration (p_up buckets):

| bucket | n | mean p_up | share up |
|---|---|---|---|
| <0.45 | 7 | hidden (n < 30) | hidden (n < 30) |
| 0.45-0.55 | 52 | 0.493 | 0.423 |
| >0.55 | 1 | hidden (n < 30) | hidden (n < 30) |
