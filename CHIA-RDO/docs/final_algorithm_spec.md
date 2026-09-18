# Final CHIA-RDO Software Algorithm Specification

Status: frozen after Phase-4 `ALGORITHM_FREEZE = PASS`.

## Identity

- Final policy: Phase-3 selected Adaptive-threshold policy.
- Software identifier: `adaptive_threshold`.
- Version: `adaptive-threshold.v1`.
- HM base: HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909`.
- Scope: luma intra candidate pruning before HM's expensive candidate RDO loop.

## Inputs

The ranker consumes each mode's predicted block through HM's SATD function, its first-pass mode-bit estimate, and first-pass square-root lambda. The controller consumes only the minimum rough cost, luma PU width/height, and SPS luma bit depth.

Confidence, activity, QP, CU size, P, batch position, and other hardware state are telemetry or experimental-policy inputs; they are not used by the frozen controller.

## Candidate Ranking

For modes `m=0..34` in ascending ID order:

```text
rough_cost[m] = SATD[m] + mode_bits[m] * sqrt_lambda_for_first_pass
```

Sort by increasing rough cost. Ties remain in ascending mode-ID order because insertion occurs only for strictly lower cost.

## K Decision

```text
normalized = min(rough_cost[0..34]) /
             (PU_width * PU_height * ((1 << luma_bit_depth) - 1))

normalized <= 0.04  -> K = 4
normalized <= 0.20  -> K = 16
otherwise           -> K = 35
```

Both boundaries are inclusive. The candidate list is exactly the first K stable-ranked mode IDs. HM evaluates that prefix; strict lower-cost winner updates preserve the earliest ranked candidate on exact RD-cost ties.

## Hardware-Aware Rule

Adaptive-threshold v1 has no hardware-state-dependent K modification. For scheduler width P, it emits `batch_count = ceil(K/P)` for the initial empty state and does not fill or trim K to a batch boundary. Adaptive-HW batch-fill baseline and Adaptive-HW v1 remain separate policy versions.

## Outputs

- `selected_k`: one of `4`, `16`, `35`.
- `candidate_list`: stable rough-cost-ranked prefix of length K.
- `batch_count`: `ceil(K/P)` for an empty P-way scheduler.

## Complexity And Measured Tradeoff

On the Phase-4 held-out synthetic matrix, the policy averages K `21.628`, reduces candidate RDO evaluations by `38.21%`, and requires an estimated `3.177` batches or `33.596` estimated hardware cycles per event at P=8. Aggregate winner retention is `97.91%` and aggregate Y-PSNR BD-rate is `-0.026%` relative to Full-RDO.

These are workload aggregates, not architectural constants. Mixed texture and repetitive inputs selected mostly K=16/35 and produced about 13-14% RDO reduction; smooth/edge input selected mostly K=4 and produced 87.36% reduction.

## Quality Constraints

The predeclared Phase-4 acceptance bounds are aggregate BD-rate no greater than `1.5%`, every held-out workload no greater than `3.0%`, aggregate winner retention at least `85%`, every workload at least `75%`, and positive RDO reduction. The frozen policy passed all bounds.

Current evidence supports only limited generalization across three deterministic synthetic held-out content classes. It is not sufficient to claim generalization to a standard HEVC corpus, natural video, inter coding, non-8-bit data, or non-4:2:0 formats.
