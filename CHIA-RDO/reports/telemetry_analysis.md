# Exhaustive Telemetry Analysis

Analysis date: 2026-09-08

`K_hit = 1 + index(best_mode in ranked_modes)`. The ranking includes SATD and mode-bit cost; it is not raw SATD order.

## Winner Coverage

| Trace | Records | Mean K_hit | P(K_hit<=2) | <=4 | <=8 | <=16 | <=35 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `tiny64-all-intra-full-rdo-qp32-faed5f414b11` | 1,364 | 7.007 | 42.229% | 53.152% | 71.334% | 87.317% | 100.000% |
| `synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5` | 10,912 | 7.455 | 39.397% | 51.705% | 68.484% | 85.970% | 100.000% |

## Confidence

The tested confidence is `(rough_cost_2 - rough_cost_1) / rough_cost_1`.

- `tiny64-all-intra-full-rdo-qp32-faed5f414b11`: Spearman versus K_hit `-0.258`, top-1 AUC `0.667`.
- `synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5`: Spearman versus K_hit `-0.269`, top-1 AUC `0.677`.

High confidence improves top-1 probability but does not guarantee a shallow winner. Adaptive-K v0 must therefore report misses and coding loss rather than treating this feature as an oracle.

## Limitations

- Both unique traces are deterministic synthetic All-Intra QP32 workloads.
- Rows are searched CU/PU alternatives and are not independent final-bitstream blocks.
- QP correlation is unavailable because QP is constant.
- Approximately three quarters of rows are 4x4 PUs, so aggregate results are size-skewed.
- Single-QP analysis cannot produce BD-rate.
