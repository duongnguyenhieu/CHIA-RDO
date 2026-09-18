# Phase 5.3 P-Way Full-RDO Gate

#### Verdict: PASS for local functional integration

Phase 5.3 integrates the validated 4x4 luma Full-RDO candidate datapath into one parameterized scheduler for `P = 1/2/4/8`. All 35 HEVC luma intra modes are supported. Across 56,336 RTL candidate evaluations, every candidate was retired exactly once with the expected rank, mode, and Q16.16 RD cost; every event winner and measured cycle count matched the reference.

This gate is a local functional result. It does not claim FPGA timing, area, power, or encoder throughput for the P-way design.

## Supported profile

| Dimension | Phase 5.3 support |
|---|---|
| Block/component | 4x4, 8-bit luma |
| Intra modes | 0 through 34 |
| QP | 22, 27, 32, 37 |
| Candidate counts | Frozen K = 4, 16, 35 |
| Parallelism | P = 1, 2, 4, 8 |
| Candidate order | HM evaluation order; K uses the first K supplied candidates |
| Rate input | Exact integer HM `xGetIntraBitsQT` count supplied externally |
| Winner rule | Lowest 56-bit Q16.16 cost; exact ties retain earliest candidate rank |

Each candidate follows the validated path:

```
prediction -> residual -> DST -> scalar quantization
-> inverse quantization/DST -> reconstruction -> SSE
-> externally supplied HM bits -> Q16.16 RD cost
```

The exact cost remains `(distortion << 16) + rate_bits * lambda_q16`, where `lambda_q16 = round(HM_lambda * 65536)`. No hardware CABAC or context-state estimator is present.

## Architecture

`rtl/full_rdo_pway.sv` is a single generate-based implementation parameterized by P. It instantiates P copies of `full_rdo_mvp_4x4`, launches at most one candidate per lane in each batch, handles a partial final batch, preserves the supplied candidate rank, and performs a stable reduction over retired candidates.

The implementation exposes independently checked counters for model batches, launched RTL batches, event cycles, stalls, and aggregate lane-active cycles. With an always-ready retirement interface, the current serialized lane wrapper requires four cycles per batch:

```
batches = ceil(K/P)
event_cycles = 4 * batches
lane_active_cycles = 4 * K
```

These formulas are checked against RTL counters for every event rather than used as substitutes for simulation measurements.

## Golden corpus

Pinned HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909` generated 256 complete 35-mode groups, 64 at each supported QP. The corpus contains 8,960 unique candidate traces, with 256 candidates for every mode from 0 through 34.

Before vector emission, the software oracle compared all 8,960 HM candidates exactly at prediction, residual, transform, quantization, dequantization, inverse residual, reconstruction, and distortion. Repository unit tests independently replay the same candidate-stage and K-winner checks.

| Artifact | SHA-256 |
|---|---|
| `tests/full_rdo/vectors/pway_candidates.jsonl` | `54b0dc5975157800875103377c958e11a929bfdcffa016f9577fd2d34625e3f8` |
| `tests/full_rdo/vectors/pway_groups.jsonl` | `41ad8eed65f7ad3988f7c31836ee0e04d084f6768f9c48116f834707960e6115` |
| Generated source YUV | `1ba7c09220b0c0124db023bc5b1549fc8da68f70a8c7f4e51348f7d84a2b6a6a` |

## Exact RTL results

For each P configuration, the regression runs all 256 groups at K = 4, 16, and 35, followed by K = 1 and K = 3 tail/edge events. This produces 770 events and 14,084 candidate evaluations per P, or 3,080 events and 56,336 candidate evaluations overall.

| Check | Pass | Fail |
|---|---:|---:|
| Candidate rank/mode/cost and supported status | 56,336 | 0 |
| Duplicate candidates | 0 observed | 0 |
| Dropped candidates | 0 observed | 0 |
| Event winner rank/mode/cost | 3,080 | 0 |
| Batch, cycle, lane-active, and stall counters | 3,080 | 0 |

All P/K rows report `winner_match = True` and `rd_cost_match = True` in `reports/pway_rtl_results.csv`.

## Measured scheduling results

`cycles_rtl` and utilization below are derived from counters emitted by the RTL simulation. `batches_model` is the independent `ceil(K/P)` reference.

| P | K | Candidates | Batches model | RTL cycles/event | Lane utilization | Events/clock estimate |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 1,024 | 4 | 16 | 100.00% | 0.062500 |
| 1 | 16 | 4,096 | 16 | 64 | 100.00% | 0.015625 |
| 1 | 35 | 8,960 | 35 | 140 | 100.00% | 0.007143 |
| 2 | 4 | 1,024 | 2 | 8 | 100.00% | 0.125000 |
| 2 | 16 | 4,096 | 8 | 32 | 100.00% | 0.031250 |
| 2 | 35 | 8,960 | 18 | 72 | 97.22% | 0.013889 |
| 4 | 4 | 1,024 | 1 | 4 | 100.00% | 0.250000 |
| 4 | 16 | 4,096 | 4 | 16 | 100.00% | 0.062500 |
| 4 | 35 | 8,960 | 9 | 36 | 97.22% | 0.027778 |
| 8 | 4 | 1,024 | 1 | 4 | 50.00% | 0.250000 |
| 8 | 16 | 4,096 | 2 | 8 | 100.00% | 0.125000 |
| 8 | 35 | 8,960 | 5 | 20 | 87.50% | 0.050000 |

The final-batch utilization loss for K = 35 at P = 2/4/8 and K = 4 at P = 8 is the expected `K / (P * ceil(K/P))` tail effect. The events/clock column is `1 / cycles_rtl`; it is a scheduler estimate in clocks and is not FPGA encoder throughput.

## Reproducibility

- `software/patches/hm-16.20-phase5.3-pway-full-rdo.patch` extends Phase 5.2 tracing from four modes to modes 0 through 34.
- Applying the complete patch stack to a clean detached HM worktree produced a `TEncSearch.cpp` SHA-256 of `c2a96744d7298e519ffcc5f78974707241057eb89158eaf6041022d9e5b01eaa`, byte-identical to the active HM tree.
- `scripts/setup_hm.sh` recognizes the Phase-5.3 state idempotently and rebuilds the pinned encoder and decoder successfully.
- `scripts/capture_pway_vectors.py` captures complete HM groups and rejects any candidate whose intermediate stages differ from the software oracle.
- `scripts/run_pway_full_rdo_regression.py` builds all four P configurations and emits `results/phase5_3/rtl_gate.json` plus `reports/pway_rtl_results.csv`.

## Regression evidence

- Repository unit tests: 26/26 PASS, including all 8,960 all-mode candidate-stage comparisons.
- Phase-5.1 exact candidate regression: 256/256 per stage PASS; invalid mode 35 and invalid QP 23 are rejected.
- Phase-5.2 Full-RDO PE regression: 10,000/10,000 candidates and 2,500/2,500 winners PASS.
- Existing RD-cost PE regression: 7,002/7,002 PASS.
- Existing P-way RD array regression: 24/24 scenarios PASS.
- Existing scheduler regression: 2,000/2,000 vectors PASS.
- Verilator `-Wall` builds, Python compilation, shell syntax, and whitespace checks PASS.

## Frozen-state integrity

No frozen policy was retuned. `adaptive-threshold.v1`, thresholds `0.04/0.20`, and K `{4,16,35}` remain unchanged.

| Protected artifact | SHA-256 |
|---|---|
| `reports/phase4_gate.md` | `2cae0420d4a090c23dd815dd044edf3d93ee9169c2b43b04be8e5db7046c88d6` |
| `docs/final_algorithm_spec.md` | `263426135cd3bca61c455fa326573858dd5c5f3113e63f8e45d979890de65b` |
| `docs/rtl_rdo_architecture_spec.md` | `3deff2d728e99db87310f13430a078c5735b609e847fae10f702ee261b42d591` |
| `results/phase4/gate.json` | `400e44c20555e1db054ff5c9ccaeaa1da230a371ae92bb9d9e057ed09793d118` |
| `results/phase4/database.json` | `89191953937bd9fe81bc6fb3bc329818384694406909ad3bcad2b9aa03311516` |
| `results/phase4/analysis.json` | `22d708b1efa3bcc1f5dddddd7699e0c39223347149e6d744df365b0c6d78f846` |

## Unsupported and blocked scope

Unsupported functionality includes block sizes other than 4x4, chroma, inter prediction, rectangular transforms, DCT paths, transform skip, RDOQ/RDOQTS, sign-data hiding, scaling lists, transquant bypass, hardware CABAC/context estimation, syntax coding, and transform-tree decisions.

No Phase-5.3 synthesis, implementation, timing, area, or power result is claimed. The Phase-5.1 physical result cannot be extrapolated to P-way replication. GCP DSE was not started and remains prohibited until separately authorized under the fail-closed budget policy.
