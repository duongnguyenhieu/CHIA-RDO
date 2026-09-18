# Full-RDO RTL Interface Specification

Status: prepared after `ALGORITHM_GATE = PASS`; no Full-RDO datapath RTL is implemented by this document.

## Scope

The next phase will implement a candidate-level HEVC intra luma RDO prototype corresponding to the software-selected adaptive-threshold controller. Existing `rtl/rdo_scheduler.sv` remains a scheduling artifact, not the final implementation. Prediction, transform, quantization, inverse reconstruction, distortion, rate estimation, and RD-cost arithmetic require independent golden-vector validation against HM before integration.

## Candidate Interface

Inputs use ready/valid flow control and carry an immutable event ID, mode ID 0..34, QP, PU geometry, prediction references, original samples, and the stable rough-cost rank. `candidate_last` marks the selected-K boundary. Outputs preserve event and mode IDs so responses may be reduced deterministically. Backpressure must not drop, duplicate, or reorder an accepted candidate within an event.

## Policy-Control Interface

The selected controller consumes:

```text
best_rough_cost
PU width
PU height
bit depth
easy_threshold = 0.04
hard_threshold = 0.20
K levels = 4, 16, 35
```

It computes `normalized_best_rough_cost = best_rough_cost / (PU_width*PU_height*((1<<bit_depth)-1))`, returns K=4 at or below 0.04, K=16 at or below 0.20, otherwise K=35. Fixed-point width, rounding, and threshold constants must be selected by a separate HM-vector quantization study. The ranker supplies the 35 mode IDs in stable rough-cost order; equal costs preserve lower insertion order.

The common software feature vector also contains SATD, mode bits, top-two gap, activity, QP, CU/PU size, P, and analytical hardware state. Those fields remain available for experiments but are not required by the selected v1 RTL controller.

## Scheduler Interface

The scheduler accepts `event_start`, selected K, P, buffer availability, PE readiness, and candidate descriptors. It emits lane-valid descriptors and a stable result stream. P is elaboration-time selectable in 1/2/4/8. The scheduler must support partial final batches, bubbles, downstream backpressure, reset during idle, and deterministic tie behavior.

## P-Way Replication

P identical RDO PE interfaces operate in parallel. Candidate assignment is contiguous by stable rank. For batch `b` and lane `l`, candidate index is `b*P+l`; lanes beyond K in the final batch are invalid and must not change state. Architectural comparisons must keep PE functionality and arithmetic widths constant while changing P.

## RDO PE Interface And Pipeline

Each PE accepts one mode candidate and produces distortion, estimated rate, and RD cost with event/mode tags. Proposed stage boundaries are prediction, residual/transform, quantization and inverse reconstruction, distortion/rate estimation, then RD-cost formation. These are specification boundaries only; actual latency and stage placement require golden-vector and timing studies.

## RD-Cost Calculation

The target operation is HM-equivalent Lagrangian cost:

```text
J = distortion + lambda * rate
```

The next phase must define distortion width, rate fractional width, lambda representation, multiplication rounding, saturation, and final comparison width from measured HM ranges. No 48-bit scheduler prototype assumption is accepted without that range analysis.

## Best-Mode Reduction

Reduction compares valid `(RD cost, stable rank)` pairs lexicographically. Lower RD cost wins; exact ties select lower stable rank. The result contains event ID, mode ID, RD cost, distortion, and rate. Completion is asserted only after all K accepted candidates for the event have retired.

## Buffering

Candidate buffer depth is parameterized up to 35 and must expose occupancy/ready state. Result buffering must absorb pipeline skew and downstream backpressure. Illegal K, overflow, underflow, cross-event mixing, and reset behavior require assertions.

## Cycle-Model Correspondence

For the initial empty-state model:

```text
batches = ceil(K/P)
estimated_cycles = pipeline_fill + batches*(RDO_cycles_per_batch + batch_overhead) + pipeline_drain
```

RTL tests must report accepted candidates, actual batches, first-accept to done latency, bubbles, and lane utilization. Model calibration may change fill, drain, service, and overhead parameters but must not retroactively label estimates as measured RTL cycles.

## Required Verification Before Synthesis

- HM-derived golden vectors for every arithmetic stage and integrated RD cost.
- K=4/16/35 across P=1/2/4/8, including partial final batches.
- Stable ties, reset, bubbles, buffer limits, and backpressure.
- Bit-exact policy decisions after fixed-point quantization.
- Analytical-versus-RTL batch and cycle comparison with discrepancies documented.
- Only after these pass may area/Fmax results be generated and labeled as implementation measurements.
