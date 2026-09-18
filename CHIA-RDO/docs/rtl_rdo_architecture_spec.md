# Full-RDO RTL Architecture Specification

Status: specification only after `ALGORITHM_FREEZE = PASS`; no Full-RDO datapath RTL is implemented in Phase 4.

## Top-Level Flow

```text
Adaptive-K controller
        |
        v
Candidate buffer
        |
        v
P-way RDO scheduler
        |
        v
RDO PE x P
        |
        v
Best-cost reduction
```

The Adaptive-K controller implements `adaptive-threshold.v1` exactly as frozen in `docs/final_algorithm_spec.md`. The ranker supplies all 35 mode IDs and rough costs in stable order. The controller returns K=4/16/35 and the buffer accepts exactly that prefix.

## Controller And Candidate Buffer

The controller input carries event ID, minimum rough cost, PU width/height, and luma bit depth. Fixed-point normalization must be qualified against HM vectors before implementation; threshold comparisons must preserve inclusive software boundaries.

The candidate buffer stores up to 35 descriptors containing event ID, stable rank, mode ID, QP, PU geometry, original block and reference samples. Ready/valid flow control must prevent loss, duplication, cross-event mixing, and reordering. Illegal K and overflow require assertions.

## P-Way Scheduler

P is selectable from 1/2/4/8. Batch `b`, lane `l` receives candidate index `b*P+l`; lanes at indices greater than or equal to K are invalid. The scheduler reports accepted/retired candidates, `ceil(K/P)` batches, bubbles, backpressure, and first-accept-to-done latency.

The existing `rtl/rdo_scheduler.sv` validates buffering, batch accounting, and stable minimum reduction only. It is not the final datapath and remains unchanged in Phase 4.

## RDO Processing Element

The complete future RDO PE contains:

```text
prediction -> residual -> transform -> quantization
             -> inverse reconstruction -> distortion
             -> bit-cost estimate -> RD-cost
```

RD cost is `distortion + lambda * rate`. Arithmetic widths, lambda representation, rounding, saturation, transform scaling, scan order, quantizer behavior, reconstruction clipping, distortion metric, and bit-estimator state must be derived from HM rather than assumed.

### First RTL Milestone

- Required: ready/valid candidate shell, event/mode/rank tags, abstract prediction/residual inputs, parameterized latency, externally supplied distortion/bit-cost/RD-cost, P-way scheduling, partial batches, and stable best-cost reduction.
- Initially abstracted: sample prediction, residual formation, transform, quantization/inverse quantization, inverse transform, reconstruction, distortion arithmetic, and CABAC-context-derived bit estimation.
- Later bit-exact milestones replace one abstraction at a time using HM golden vectors.

## Best-Cost Reduction

Compare valid `(RD cost, stable rank)` lexicographically. Lower RD cost wins; exact ties select lower stable rank. Completion occurs only after all K accepted candidates retire. Output includes event ID, mode ID, stable rank, distortion, bit estimate, and RD cost.

## Golden-Reference Interface

Each HM-derived vector represents one candidate decision and contains:

```text
event ID and candidate mode
input luma block and dimensions
top/left reference samples and availability
QP, bit depth, lambda representation
prediction samples
residual samples
forward-transform coefficients
quantized levels
inverse-quantized/inverse-transform values
reconstructed samples
distortion
bit estimate
RD cost
```

The RTL result supplies the corresponding prediction, residual, transform, quantization, reconstruction, distortion, bit estimate, and RD-cost values plus tags. Integer stages compare bit-exactly. Fractional lambda/rate/RD stages compare after a documented fixed-point conversion with exact rounding and saturation; no unspecified tolerance is allowed. Integrated winner comparison must match HM's candidate mode and stable tie rule.

Current HM telemetry is sufficient for scheduler vectors but does not yet expose every sample-level stage above. Phase 5 must first add a bounded golden-vector extractor; datapath RTL must not begin from guessed intermediate values.

## Verification And Implementation Gate

- Exercise K=4/16/35 and P=1/2/4/8, including partial final batches.
- Cover all PU sizes used by HM, all intra modes, threshold boundaries, stable ties, reset, bubbles, and backpressure.
- Compare analytical batches with RTL exactly; label timing as measured RTL cycles only after simulation.
- Do not begin a large synthesis campaign until controller quantization and PE stage vectors pass.
