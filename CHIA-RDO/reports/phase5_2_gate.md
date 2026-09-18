# Phase 5.2 Full-RDO PE Gate

#### Verdict: PASS for the explicitly supported reference model

Phase 5.2 implements a complete serialized candidate loop for the supported four-mode 4x4 luma subset. Every candidate stage, fixed-point RD cost, and event winner matches the software reference exactly. This verdict does not claim hardware CABAC, syntax coding, larger transforms, all HEVC intra modes, or completed FPGA physical implementation.

## Scope expansion

The Phase-5.1 DC-only candidate is expanded to the largest subset defensible without replacing the validated combinational transform architecture:

| Dimension | Phase 5.2 support |
|---|---|
| Block size | 4x4 only |
| Modes | 0 planar, 1 DC, 10 horizontal, 26 vertical |
| QP | 22, 27, 32, 37 |
| Candidate group | All four modes in HM evaluation order |
| Component/precision | 8-bit luma |

The input representation now carries top-left, eight top, and eight left references. Modes 0/10/26 use the same downstream DST, quantization, inverse, reconstruction, distortion, and existing RD-cost PE proven in Phase 5.1.

Larger blocks are not implemented. The Phase-5.1 4x4 kernel already measured 1,026 DSPs after KV260 routing; direct 8x8 replication would be an unjustified resource expansion. The RTL explicitly rejects block sizes 8 and 16 in regression. A larger-block phase requires a separately validated folded transform architecture.

## Full-RDO definition

Within this project gate, Full-RDO means evaluating every supplied candidate in the fixed supported set through:

```
prediction -> residual -> DST -> scalar quantization
-> inverse quantization/DST -> reconstruction -> SSE
-> externally supplied HM bits -> Q16.16 RD cost -> stable minimum
```

The exact cost is `(distortion << 16) + rate_bits * lambda_q16`, where `lambda_q16 = round(HM_lambda * 65536)`. `rate_bits` is the exact integer HM `xGetIntraBitsQT` candidate count supplied to RTL. No CABAC estimator or context-state machine exists in this PE.

The comparator updates only on a strictly lower cost. Exact ties retain the earliest supplied candidate rank; mode number is not a secondary key. `docs/full_rdo_pe_spec.md` defines all arithmetic, interfaces, timing, and exclusions.

## Golden coverage

Pinned HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909` generated 10,000 candidate vectors grouped into 2,500 events:

| Coverage axis | Candidate evaluations |
|---|---:|
| Mode 0 | 2,500 |
| Mode 1 | 2,500 |
| Mode 10 | 2,500 |
| Mode 26 | 2,500 |
| QP 22 | 2,500 |
| QP 27 | 2,500 |
| QP 32 | 2,500 |
| QP 37 | 2,500 |
| Smooth | 2,064 |
| Edge-heavy | 2,048 |
| Texture-heavy | 2,048 |
| Random | 2,048 |
| Worst-case signed | 1,792 |

Observed transform coefficients span -18,260 through 21,654; quantized coefficients span -71 through 84. The corpus contains 205 events with at least one cost tie, including 19 events where the minimum is tied. The emitted candidate JSONL SHA-256 is `ec92c7fe959a125f08c8aeba4ef25c01598c5b40048e3eedfee6dcd04a222b89`; grouped-event SHA-256 is `d470e0378c945a6d8f9519020e3f99526bab16009a6466563d20a490ab6c1dde`.

## Exact hardware results

Verilator checks every retired candidate independently:

| Compared result | Pass | Fail |
|---|---:|---:|
| Prediction | 10,000 | 0 |
| Residual | 10,000 | 0 |
| Forward transform | 10,000 | 0 |
| Quantized coefficients | 10,000 | 0 |
| Dequantized coefficients | 10,000 | 0 |
| Inverse residual | 10,000 | 0 |
| Reconstruction | 10,000 | 0 |
| Distortion | 10,000 | 0 |
| HM bit-count transport | 10,000 | 0 |
| Q16.16 RD cost | 10,000 | 0 |
| Winning rank/mode/cost | 2,500 | 0 |

Software Q16.16 and RTL costs agree exactly for all 10,000 candidates. Software and RTL winners agree exactly for all 2,500 groups. The independently recorded HM floating-point winner over the same four candidates also agrees with the Q16.16 winner for all 2,500 groups; no fixed-point winner limitation was observed in this corpus.

## Exact cycle measurements

The testbench measures counters and externally observed handshakes rather than relying only on a formula:

| Metric | No backpressure |
|---|---:|
| Candidate result-valid latency after acceptance | 2 cycles |
| Candidate retirement interval | 4 cycles |
| Four-candidate event | 16 cycles |
| Winner reduction | 1 registering edge, no additional event cycle |
| Pipeline/output stalls | 0 |
| Whole-PE occupied cycles | 16/16, 100% |

An injected two-cycle candidate-output stall produces exactly two reported stall cycles and increases event latency from 16 to 18 cycles. The held candidate cost remains stable and the selected winner is unchanged.

## Analytical estimates

These values are deterministic schedule calculations, not separately measured physical utilization:

- Codec capture activity is 4 of 16 event cycles, or 25%.
- The two-cycle RD pipeline occupies 8 of 16 event cycles, or 50%.
- Ideal serialized event throughput is one four-mode event per 16 clocks when the candidate output is always ready.

No Phase-5.2 LUT/FF/DSP, power, Fmax, or post-route timing result is claimed. A local KV260 implementation attempt exceeded the 600-second limit before producing reports. Phase-5.1 physical numbers are used only to justify the conservative block-size boundary, not presented as Phase-5.2 measurements.

## Reproducibility and regression

- `software/patches/hm-16.20-phase5.2-full-rdo-pe.patch` applies after the Phase-5.1 patch stack.
- A clean detached HM worktree plus the complete patch stack produced a byte-identical instrumented `TEncSearch.cpp` SHA-256 of `e5b3efaec6b8117d7a0960e83319c62ff0f197c4d48765a014ad9fcf13dfeafa`.
- `scripts/setup_hm.sh` recognizes the latest patch state idempotently and rebuilds HM successfully.
- Repository unit tests: 24/24 PASS.
- Phase-5.1 candidate regression remains 256/256 per stage PASS.
- Existing RD-cost PE regression remains 7,002/7,002 PASS.
- Existing P-way RD array remains 24/24 scenarios PASS.
- Existing scheduler regression remains 2,000/2,000 PASS.
- Verilator lint, Python compilation, shell syntax, and whitespace checks PASS.

## Frozen-state integrity

No Phase-4 policy or protected artifact was changed. `adaptive-threshold.v1`, thresholds `0.04/0.20`, and K `{4,16,35}` remain unchanged. The six protected artifact hashes are rechecked during the final gate and remain equal to their Phase-4 lock values.

## Unsupported functionality

Unsupported functionality includes block sizes other than 4x4, intra modes other than 0/1/10/26, chroma, inter prediction, rectangular transforms, DCT paths, transform skip, RDOQ/RDOQTS, sign-data hiding, scaling lists, transquant bypass, hardware CABAC/context estimation, syntax coding, transform-tree decisions, and parallel candidate datapaths. Unsupported dimensions are rejection cases, not golden candidate evaluations.

GCP DSE was not started. It remains prohibited until this local gate is accepted and separately authorized under the fail-closed budget policy.
