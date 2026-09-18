# Phase 3 Policy Search

Bounded deterministic replay evaluated 171 configurations.

Replay is used only for screening; selected configurations require online HM encoding.

| Policy | P | Avg K | Retention | Avg batches | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| adaptive_threshold | 1 | 18.841 | 91.86% | 18.841 | 174.568 |
| relative_satd | 1 | 26.212 | 96.55% | 26.212 | 240.907 |
| adaptive_hw_v1 | 1 | 33.210 | 98.61% | 33.210 | 303.887 |
| adaptive_hw_v1 | 2 | 33.280 | 98.83% | 17.111 | 158.996 |
| adaptive_hw_v1 | 4 | 33.512 | 99.27% | 8.614 | 82.529 |
| adaptive_hw_v1 | 8 | 16.781 | 87.32% | 2.246 | 25.210 |

## Online Qualification

GCP online HM encoding evaluated the same 12 bounded configurations on `e2-standard-2` and `e2-standard-8`. Coding metrics and bitstream, reconstruction, and trace hashes matched exactly across machine types. These QP32 trials qualify execution determinism; the matched multi-QP matrix remains the evidence used for final policy selection.
