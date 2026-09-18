# Phase-3 Selected Adaptive-Threshold Policy Specification

## Identity And Scope

The Phase-3 selected `adaptive_threshold` policy has version `adaptive-threshold.v1`. It is a CHIA-RDO controller implemented in HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909`; it is not claimed to reproduce a published paper.

This specification freezes the selected experiment tuple, not the generic command-line defaults. Every conforming invocation must explicitly provide thresholds `0.04/0.20` and K levels `4/16/35`.

## Inputs

The controller uses only:

- Minimum rough cost among all 35 luma intra modes.
- Luma PU width and height.
- SPS luma bit depth.

Confidence, activity, QP, CU size, P, and scheduler state are emitted or available but are not controller inputs in v1.

## Rough-Cost Ranking

For every luma intra mode `m` in ascending mode-ID order `0..34`, HM computes:

```text
rough_cost[m] = SATD[m] + mode_bits[m] * sqrt_lambda_for_first_pass
```

The 35 modes are ordered by increasing rough cost with stable insertion behavior. Because insertion occurs only for strictly lower cost, equal rough costs preserve ascending mode-ID order.

## Normalization And K Decision

```text
area = PU_width * PU_height
sample_max = (1 << bit_depth_luma) - 1
normalized_best_rough_cost = min(rough_cost[0..34]) / (area * sample_max)

if normalized_best_rough_cost <= 0.04:
    K = 4
else if normalized_best_rough_cost <= 0.20:
    K = 16
else:
    K = 35
```

Both threshold comparisons are inclusive. K is always one of `4`, `16`, or `35`.

## Candidate Selection And HM Insertion Point

The selected list is exactly the first K entries of the stable 35-mode rough-cost ranking. HM evaluates this prefix in the expensive luma RDO loop in `TEncSearch::estIntraPredLumaQT`, after rough ranking and before recursive luma candidate RDO. An exact RD-cost tie retains the earliest stable-ranked candidate because the winner update also uses strict less-than comparison.

The policy limits the main candidate-RDO loop. HM's subsequent RQT refinement remains enabled and is counted separately; it is not part of K.

## Configuration Interface And Defaults

The required runner invocation fields are:

```text
--policy adaptive_threshold
--easy-threshold 0.04
--hard-threshold 0.20
--easy-k 4
--medium-k 16
--hard-k 35
```

They map to `CHIA_RDO_POLICY=adaptive_threshold`, `CHIA_RDO_EASY_ROUGH_THRESHOLD`, `CHIA_RDO_HARD_ROUGH_THRESHOLD`, `CHIA_RDO_EASY_K`, `CHIA_RDO_MEDIUM_K`, and `CHIA_RDO_HARD_K`.

Plain `--policy adaptive_threshold` uses generic defaults `0.08/0.20, 4/8/16` and therefore is not the frozen Phase-3 selection. With no CHIA policy environment, normal stock-HM behavior remains the default. `--policy full` selects the separate exhaustive 35-mode reference path.

## Telemetry

Each `chia-rdo.policy-trace.v1` event records event/CTU/CU/PU identity, QP and geometry, the 35-mode ranking, selected K, evaluated prefix, SATD and SATD rank by mode, mode bits, rough costs, top-two costs and gap, confidence, normalized best rough cost, activity and normalized activity, relative-SATD count, per-rank RD costs, RDO and RQT evaluation counts, best mode, distortion, and RD cost.

`software/run_policy.py` checks that the evaluated modes equal the ranked prefix, recomputes the K decision from the recorded normalized cost, verifies result/trace repeatability, decodes the bitstream, and compares structural events with the matched Full-RDO trace.

## Implementation References

- Controller and telemetry: `software/third_party/HM/source/Lib/TLibEncoder/TEncSearch.cpp`.
- Reproducible patch layer: `software/patches/hm-16.20-phase3-algorithms.patch`.
- Python reference: `software/policy_algorithms.py::select_adaptive_threshold_k`.
- Runner and trace validation: `software/run_policy.py`.

The Python runner restricts adaptive K levels to `2/4/8/16/35`; direct C++ environment parsing accepts any K in `1..35`. The frozen interface is the validated Python runner and the exact tuple above.
