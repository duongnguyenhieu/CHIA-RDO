# Adaptive Hardware Feature Mapping

This mapping separates algorithm features computed from HM's rough intra search from hardware-state features supplied by a future scheduler. It does not change the frozen Phase-3 selected Adaptive-threshold policy.

## Algorithm Features

| Feature | Software source | Definition or role | Frozen Adaptive-threshold v1 |
|---|---|---|---|
| SATD | `TEncSearch::estIntraPredLumaQT` telemetry | Per-mode prediction distortion used in rough cost | Indirectly, through rough-cost ranking |
| Mode bits | HM `xModeBitsIntra` | Estimated signaling bits in first-pass ranking | Indirectly, through rough cost |
| Rough cost | HM telemetry | `SATD + mode_bits * sqrt_lambda_for_first_pass` | Uses minimum value |
| Confidence | HM candidate ranking | `(top2_rough_cost-top1_rough_cost)/max(top1_rough_cost, epsilon)` | Not used |
| Activity | HM telemetry/calculation | Mean absolute luma deviation, normalized by sample range | Not used |
| QP | Encoder/CU state | Current luma QP | Not used |
| CU/PU size | CU metadata | CU and PU width/height; PU area normalizes rough cost | Uses PU area only |
| Relative-SATD count | Telemetry/calculation | Number of modes below the configured relative-SATD bound | Not used |

## Hardware-State Features

| Feature | Software model source | Future RTL source | Frozen Adaptive-threshold v1 |
|---|---|---|---|
| P | `HardwareState.parallelism` | Elaboration/runtime scheduler configuration | Does not change K |
| Batch position | `current_batch_position` | Scheduler occupancy state | Not used |
| Remaining batch capacity | `P-current_batch_position` | Candidate buffer/scheduler state | Not used |
| Pending batches | `pending_batches` | Scheduler queue state | Not used |
| Estimated cycle cost | `estimate_cycles` | Calibrated scheduler timing model | Reporting only |
| Lane utilization | `K/(batches*P)` | Dispatch/retirement counters | Reporting only |

## Extension Boundary

The frozen controller produces K before scheduler dispatch. A hardware-aware successor may combine confidence, activity, QP, block size, P, batch position, and estimated cycle cost, but it must use a new policy name/version and a new train/test split. Adaptive-HW batch-fill baseline and Adaptive-HW v1 are existing experimental comparators; neither is silently merged into Adaptive-threshold v1.

For an empty scheduler, the existing analytical interface is:

```text
batches = ceil(K/P)
estimated_cycles = fill + batches*(RDO_service + overhead) + drain
```

The locked constants are fill `3`, drain `2`, service `8`, and overhead `1`. These are estimated hardware cycles until calibrated against RTL simulation or FPGA measurements.
