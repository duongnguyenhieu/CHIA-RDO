# Phase 5.1 Full-RDO MVP Gate


#### Verdict: PASS

The explicitly scoped 4x4 luma intra-DC Full-RDO candidate datapath matches HM-16.20 exactly for all captured stages and meets the 5 ns KV260 post-route timing target. This verdict applies only to the supported MVP profile below; it is not a claim of complete HEVC RDO support.

## Frozen-policy integrity

The Phase-5.1 work does not modify or reinterpret `adaptive-threshold.v1`, its `0.04/0.20` thresholds, or K `{4,16,35}`. All six protected Phase-4 artifacts retain their recorded SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| `reports/phase4_gate.md` | `2cae0420d4a090c23dd815dd044edf3d93ee9169c2b43b04be8e5db7046c88d6` |
| `docs/final_algorithm_spec.md` | `263426135cd3bca61c455fa326573858dd5c5f3113e63f8e45d979890de65b` |
| `docs/rtl_rdo_architecture_spec.md` | `3deff2d728e99db87310f13430a078c5735b609e847fae10f702ee261b42d591` |
| `results/phase4/gate.json` | `400e44c20555e1db054ff5c9ccaeaa1da230a371ae92bb9d9e057ed09793d118` |
| `results/phase4/database.json` | `89191953937bd9fe81bc6fb3bc329818384694406909ad3bcad2b9aa03311516` |
| `results/phase4/analysis.json` | `22d708b1efa3bcc1f5dddddd7699e0c39223347149e6d744df365b0c6d78f846` |

## Supported profile

- 4x4 luma TU, intra DC mode 1, 8-bit internal precision.
- HEVC integer 4x4 DST and inverse DST.
- QP 22, 27, 32, and 37.
- Scalar quantization with RDOQ/RDOQTS, transform skip, sign-data hiding, scaling lists, and transquant bypass disabled.
- HM 8-bit luma SSE distortion.
- Exact HM candidate CABAC bit count supplied at the interface.
- Existing 32-bit Q16.16 lambda and 56-bit Q16.16 RD-cost PE.

## Golden vectors

The environment-gated `CHIA_FULL_RDO_TRACE` instrumentation records references, source pixels, every codec intermediate, distortion, exact candidate bits, lambda, and cost from pinned HM revision `22178e370178133438c0339f57b3b3a29f112909`.

The checked corpus contains 256 transactions:

| Coverage | Count |
|---|---:|
| QP 22 | 64 |
| QP 27 | 64 |
| QP 32 | 64 |
| QP 37 | 64 |
| Tiny deterministic source | 128 |
| Flat source | 64 |
| High-contrast source | 64 |

The selected corpus observes transform coefficients from -16,248 through 16,247 and quantized coefficients from -63 through 63. Before vector emission, the integer software oracle checks every captured HM stage exactly. The emitted JSONL SHA-256 is `9e6f672aab3c0de8d880c30603c1ffa2fa2277876d102d395c48fd8e3031c940`.

## Exact RTL gates

`scripts/run_full_rdo_rtl.py` builds the integrated SystemVerilog design with Verilator and compares all 256 transactions independently at each boundary:

| Stage | Pass | Fail |
|---|---:|---:|
| DC prediction | 256 | 0 |
| Residual | 256 | 0 |
| Forward DST | 256 | 0 |
| Scalar quantization | 256 | 0 |
| Inverse quantization | 256 | 0 |
| Inverse DST residual | 256 | 0 |
| Reconstruction/clipping | 256 | 0 |
| SSE distortion | 256 | 0 |
| Q16.16 RD cost | 256 | 0 |
| Mode/QP support and latency interface | 258 | 0 |

The additional interface cases verify rejection of mode 2 and QP 23. With no backpressure, output valid is asserted two elapsed cycles after input acceptance, crossing three registering edges including the acceptance edge. The initial wrapper serializes transactions and accepts one candidate every three cycles.

## Reproducibility

- `software/patches/hm-16.20-phase5-full-rdo-mvp.patch` applies after the existing Phase-1 through Phase-5 patches.
- Applying the complete stack in a clean detached HM worktree produced byte-identical SHA-256 values for all three modified HM sources.
- `scripts/setup_hm.sh` applies the new patch idempotently and rebuilt both HM encoder and decoder successfully.
- `scripts/capture_full_rdo_vectors.py` regenerates deterministic source material, traces HM, joins stage/bit records by sample ID, validates the oracle, and emits the corpus.

## KV260 characterization

Vivado 2024.2 out-of-context implementation targeted `xck26-sfvc784-2LV-c` at 5 ns:

| Metric | Result |
|---|---:|
| WNS | +1.094 ns |
| Estimated Fmax | 256.016 MHz |
| LUT | 39,182 |
| FF | 1,663 |
| DSP | 1,026 |
| BRAM | 0 |
| Estimated on-chip power | 1.573 W |

Timing passes, but the unoptimized combinational codec kernel consumes substantial DSP resources. That is an explicit optimization target for a later phase, not evidence for broader support or an optimized production architecture.

## Regression evidence

- Repository unit tests: 22/22 PASS.
- Full-RDO integrated exact gate: 256/256 per stage, zero total failures.
- Existing RD-cost PE regression: 7,002/7,002 PASS.
- Existing P-way array regression: 24/24 scenarios PASS.
- Existing scheduler regression: 2,000/2,000 vectors PASS.
- Verilator lint, Python compile checks, shell syntax checks, and `git diff --check`: PASS.

## Unsupported and blocked scope

Planar/angular modes, chroma, transform sizes other than 4x4, transform skip, RDOQ, sign-data hiding, scaling lists, transquant bypass, hardware CABAC/context estimation, and multi-candidate scheduling for this longer codec path remain unsupported. Exact HM CABAC bits are inputs to this MVP. Remote GCP execution remains blocked under the fail-closed budget policy because verified spend and remaining promotional credit are unavailable; no cloud resources were launched for Phase 5.1.
