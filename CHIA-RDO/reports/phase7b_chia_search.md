# Phase-7B CHIA Search

The native CHIA graph screened all 832 configurations from P 1..16, pipeline depth 2/3, and cost width 31..56. Model `serial-balanced-tree-fit.v3` uses least-squares fits to routed width-31 builds and prefers the balanced-tree implementation when multiple routed rows represent the same P/depth/width configuration.

| Field | Value |
|---|---:|
| Candidate count | 832 |
| Canonical v3 evaluations | 832 |
| Reproducibility replay cache hits | 832 |
| Replay new evaluations | 0 |
| Pareto points | 16 |
| Promoted points | 16 |

The model version was changed from `serial-measured-fit.v2` because candidate IDs include the model version but not the calibration-artifact hashes. Reusing v2 after adding the P16 tree measurement would have returned stale cached estimates.

Depth-3 calibration uses seven unique routed P points: 1, 2, 3, 4, 6, 8, and 16. At P16 the v3 estimate is 61,295 LUT, 816 DSP, 67.811 MHz, 2.278 W, and 8.097 M candidates/s. The measured tree result is 61,207 LUT, 816 DSP, 68.120 MHz, 2.288 W, and 8.134 M candidates/s.

All CHIA timing states remain `ESTIMATED_FAIL` against 200 MHz. Analytical feasibility denotes corpus-width and resource-budget feasibility; it does not assert timing closure.

Evidence: `chia/phase7b_graph.py`, `results/phase7b/model_results.json`, `results/phase7b/experiments.jsonl`, and `results/phase7b/experiments/`.
