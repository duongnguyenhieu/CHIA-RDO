# Full-RDO Processing Element Specification

## Project definition

"Full-RDO" in CHIA-RDO Phase 5.2 means complete evaluation and stable selection across every candidate in the explicitly supported candidate set. For each candidate, hardware computes prediction, residual, transform, scalar quantization, inverse quantization and transform, reconstruction, SSE distortion, fixed-point RD cost, and winner reduction. It does not mean complete HEVC syntax generation or hardware CABAC.

The exact Phase-5.2 reference model is:

```
candidate_cost_q16 = (distortion << 16) + rate_bits * lambda_q16
winner = stable_argmin(candidate_cost_q16 in supplied candidate order)
```

`rate_bits` is an exact integer candidate bit count obtained from HM's `xGetIntraBitsQT` path and supplied at the event interface. The PE neither derives that count nor updates CABAC contexts.

## Supported profile

| Property | Supported value |
|---|---|
| Component | Luma |
| Block/TU size | 4x4 only |
| Internal bit depth | 8 bits |
| Intra modes | 0 planar, 1 DC, 10 horizontal, 26 vertical |
| Candidate count | 1 through 4; golden events contain all four modes |
| QP | 22, 27, 32, 37 |
| Transform | HEVC/HM 4x4 integer DST for luma intra |
| Quantization | HM scalar quantization, flat scaling list |
| Distortion | 8-bit luma SSE over 16 reconstructed samples |
| Lambda | Unsigned 32-bit Q16.16 supplied once per event |
| RD cost | Unsigned 56-bit Q16.16 with existing saturating `rdo_pe` |

Block sizes 8x8, 16x16, and 32x32 are unsupported and rejected. The Phase-5.1 4x4 combinational kernel already consumed 1,026 DSPs in KV260 post-route characterization; extrapolating that architecture to larger transforms would not be a defensible reuse-oriented extension. Supporting larger blocks requires a separately gated iterative or folded transform architecture.

## Event interface

An event supplies:

- `block_size`; only 4 is accepted.
- `candidate_count`; 1 through 4 is accepted.
- `candidate_modes[rank]`; each descriptor carries the mode at its stable input rank.
- `candidate_rate_bits[rank]`; exact HM integer bit count corresponding to that candidate.
- Shared QP, Q16.16 lambda, 4x4 original block, and reference samples.
- `start/start_ready` transaction control.

References are 17 row-major-independent bytes in this order: top-left, eight top samples, and eight left samples. The extra top/left extension samples make the representation compatible with the selected directional predictors even though the pure horizontal and vertical modes consume only the first four on each side.

Each retired candidate exposes its rank, mode, QP, support flag, every intermediate block, distortion, input bit count, and RD cost through `candidate_valid/candidate_ready`. `done` marks event completion and accompanies the registered winning rank, mode, cost, cycle counters, and support status.

## Prediction

- Planar mode 0 performs HM bilinear interpolation using the first four top/left samples plus top-right and bottom-left extension samples.
- DC mode 1 averages four top and four left samples with HM rounding, then applies the 4x4 luma DC top/left edge filter.
- Horizontal mode 10 copies the left reference across each row and applies HM's luma edge filter to the top row.
- Vertical mode 26 copies the top reference down each column and applies HM's luma edge filter to the left column.

All prediction outputs are unsigned 8-bit values and edge-filter results clip to 0 through 255.

## Transform and quantization

Residuals are signed 9-bit differences. All supported candidates use the HM 4x4 luma integer DST, with first-pass shift 1 and second-pass shift 8. Forward coefficients retain signed 32-bit storage.

Scalar quantization uses HM's quantization scale table, `qBits = 14 + floor(QP/6) + 5`, I-slice rounding `171 << (qBits-9)`, and signed clipping to -32768 through 32767. RDOQ, RDOQTS, sign-data hiding, transform skip, non-flat scaling lists, and transquant bypass are disabled.

Inverse quantization uses HM's inverse scale table and `rightShift = 6 - (5 + floor(QP/6))`. Inverse DST shifts are 7 and 12 with HM signed clipping. Reconstruction clips prediction plus inverse residual to unsigned 8-bit range.

## Rate, distortion, and lambda

Distortion is exact HM 8-bit luma SSE. The candidate's integer HM bit estimate is not recomputed in RTL. `lambda_q16` is produced by `round(HM_lambda * 65536)` in the vector/reference path. The existing `rdo_pe` computes and saturates the 56-bit result; its independent 7,002-vector regression remains mandatory.

The fixed-point equation is exact between software and RTL. It is not mathematically identical to HM's floating-point `D + lambda*R` for every possible input. The Phase-5.2 corpus records both winner definitions; all 2,500 tested events select the same mode.

## Stable tie behavior

Candidates are compared in supplied rank order. The accumulator changes only for a strictly lower cost. Therefore the earliest supplied rank wins an exact Q16.16 cost tie. Mode number is not a secondary key. This matches the frozen project's stable-prefix winner rule.

## Cycle contract

With an always-ready candidate consumer:

- Candidate result-valid latency: 2 elapsed cycles after candidate acceptance.
- Candidate retirement interval: 4 cycles in the serialized wrapper.
- Four-candidate event latency: 16 cycles from event acceptance through final retirement.
- Comparator/reduction latency: one registering edge, with no extra event cycle beyond retirement.
- Candidate-output stalls: one additional event cycle per backpressured cycle.
- Whole-PE occupied utilization during a four-candidate event: 16/16 cycles.
- Codec capture utilization: 4/16 cycles, or 25%.
- Two-cycle RD pipeline occupancy: 8/16 cycles, or 50%.

The whole-PE utilization metric denotes ownership by an active event, not simultaneous arithmetic utilization. The exact counters are emitted by RTL; the stage percentages are deterministic calculations from those measured schedules.

## Unsupported functionality

Unsupported functionality includes all intra modes other than 0/1/10/26, block sizes other than 4x4, chroma, inter prediction, rectangular TUs, transform skip, DCT transform paths, RDOQ, sign hiding, scaling lists, transquant bypass, hardware bit estimation, CABAC context evolution, syntax coding, recursive transform-tree decisions, multi-PU aggregation, and parallel candidate lanes. An unsupported block size, QP, or candidate count completes immediately with `winner_supported=0`. An unsupported mode is marked unsupported when retired and is excluded from winner comparison; a group with no supported candidate returns `winner_supported=0`. No result is represented as HEVC-conformant coding output.
