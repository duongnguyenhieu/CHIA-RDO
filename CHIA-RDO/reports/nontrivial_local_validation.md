# Nontrivial Local Validation

Execution date: 2026-09-08

Status: **PASS**

## Configuration

| Field | Value |
|---|---:|
| Sequence | `synthetic-128x128-8f-yuv420p8` |
| Resolution | 128x128 |
| Frames | 8 |
| QP | 32 |
| Policy | Exhaustive 35-mode candidate RD |
| Backend | Local |

Configuration: `configs/nontrivial_local.json`

## Measured Results

| Metric | Primary run | Verification replicate |
|---|---:|---:|
| Search calls | 10,912 | 10,912 |
| RDO evaluations | 381,920 | 381,920 |
| RQT refinements | 10,912 | 10,912 |
| Average K | 35.0 | 35.0 |
| Bitstream bytes | 23,121 | 23,121 |
| Bitrate | 693.630 kbps | 693.630 kbps |
| Y-PSNR | 31.2867 dB | 31.2867 dB |
| U-PSNR | 37.9628 dB | 37.9628 dB |
| V-PSNR | 37.9239 dB | 37.9239 dB |
| YUV-PSNR | 32.6004 dB | 32.6004 dB |
| HM CPU time | 1.862 s | 1.975 s |
| Wall time | 1.867 s | 1.982 s |
| Trace wall time | 2.547 s | 1.967 s |

## Determinism Evidence

| Artifact | SHA-256 in both runs |
|---|---|
| Bitstream | `1cb82870707b13c7395ab26a14af223ab2c8534a43291c1abaf3b25f44fd6f07` |
| Reconstruction | `af0ddea378a5ee1fc19babc8b689fd043a419ba80506a4c05fd453cf711b42ad` |
| JSONL telemetry | `2ef063e588ed2c87990ba490e2ef3c36f4722aa33ea35ea493d591900ad5289d` |

Evidence:

- `results/baseline/synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5/result.json`
- `results/baseline/synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5-verification1/result.json`

## Scaling Observation

The input sample count is eight times the 64x64x4 smoke input. Search calls,
RDO evaluations, and RQT refinements also increased exactly eightfold. JSONL
grew from approximately 2.8 MB to 22 MB, which is consistent with event-count
scaling and establishes that the current trace is usable for focused local
experiments.

The trace is too verbose for large sequence sweeps. Before research-scale runs,
the project should support summary-only telemetry or compressed/checkpointed
trace output.

## Limitations

- The sequence is deterministic synthetic content, not a standard HEVC test sequence.
- Runtime differs between replicates because CPU affinity, frequency, and cache state are not controlled. Coding metrics and telemetry are deterministic; timing is treated as a noisy measurement.
- `HHI_RQT_INTRA_SPEEDUP` remains enabled.
- This validation used no GCP resources and cost USD 0.

## Decision

The larger local validation passes. The next allowed step is cost-controlled GCP
bootstrap followed by exact smoke-baseline parity, not adaptive-K.
