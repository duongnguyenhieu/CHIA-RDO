# CHIA-RDO Hackathon Artifact

## Scope

This artifact accompanies the paper “From HM-Side Adaptive K to Variable-K RTL: A CHIA Loop for HEVC RDO Co-Design.” It contains the Adaptive-K policy implementations, CHIA loops, pinned experiment outputs, Verilator regressions, Vivado report parsers, and final result summaries.

The primary claim is a traceable co-design result: a routed P16 depth-3 width-31 balanced-tree Full-RDO kernel reaches a derived 8.134 million candidates/s throughput proxy, 2.128x the routed P1 baseline, while remaining under the internal 70%-of-device resource budget. This is not encoder FPS, board performance, or 200 MHz timing closure.

## Artifact Map

| Component | Location |
|---|---|
| Frozen software policy | `docs/final_algorithm_spec.md` |
| Prior-art-inspired Adaptive-K specifications | `docs/adaptive_threshold_v1_spec.md`, `docs/relative_satd_policy.md` |
| Adaptive-K reference implementations | `software/policy_algorithms.py`, `software/run_policy.py` |
| History-aware proposal controller | `chia/phase6_agent.py` |
| Multi-wave CHIA graph | `chia/phase6_graph.py` |
| Final calibrated CHIA graph | `chia/phase7b_graph.py` |
| Optimized serial candidate lane | `rtl/phase7b/full_rdo_mvp_4x4_serial.sv` |
| Balanced P-way wrapper | `rtl/phase7b/full_rdo_pway_optimized.sv` |
| RTL regression runners | `scripts/run_phase7b_serial_rtl.py`, `scripts/run_phase7b_pway_rtl.py` |
| Vivado result extraction | `scripts/build_phase7b_synthesis_results.py` |
| CHIA search results | `results/phase7b/model_results.json`, `results/phase7b/pareto.json` |
| Routed measurements | `results/phase7b/synthesis_results.json` |
| Final reports | `reports/phase7b_gate.md`, `reports/phase7b_optimization.md`, `reports/phase7b_chia_search.md`, `reports/phase7b_pareto.md` |

## Reproduce the Analytical Search

The CHIA framework repository must be the parent of `CHIA-RDO`, and the `chia_env` Conda environment must contain the repository dependencies. From the CHIA repository root:

```bash
conda run -n chia_env env PYTHONPATH=. python CHIA-RDO/chia/phase7b_graph.py --count 832
```

A successful replay reports 832 candidates, 16 Pareto points, and 832 cache hits when the canonical v3 cache is present. Remove or relocate the matching experiment cache only when intentionally measuring a clean evaluation; retain it for artifact cache-replay validation.

## Regenerate Parsed Vivado Results

Vivado raw reports must exist under `build/phase7b/vivado/`. From `CHIA-RDO`:

```bash
python3 scripts/build_phase7b_synthesis_results.py
```

The parser fails when a required utilization, timing, critical-path, or power field is absent. The expected selected row is `serial-p16-d3-w31-tree` with width 31, balanced-tree reduction, 61,207 LUTs, 816 DSPs, and -9.680 ns WNS.

## Validate Published Results

```bash
jq -e '.candidate_count == 832 and .pareto_count == 16' results/phase7b/model_results.json
jq -e '.rows[] | select(.build_id == "serial-p16-d3-w31-tree") | .lut == 61207 and .dsp == 816 and .cost_width == 31' results/phase7b/synthesis_results.json
jq -e 'all(.rows[]; .hardware_configuration.pipeline_depth == 3 and .hardware_configuration.cost_width == 31)' results/phase7b/pareto.json
```

RTL regressions are designed for remote GCP execution in this project. Do not reinterpret checked-in PASS summaries as a fresh local regression. The canonical evidence files are:

- `results/phase7b/serial_rtl_gate_d3.json`
- `results/phase7b/pway_rtl_gate.json`
- `results/phase7b/pway_rtl_gate_w31.json`
- `results/phase7b/pway_rtl_gate_p16.json`
- `results/phase7b/pway_rtl_gate_tree.json`

## Evidence Qualifications

- Measured: HM outputs, Verilator outputs, and parsed Vivado reports.
- Modeled: non-routed CHIA candidate resource, power, Fmax, and throughput estimates.
- Unsupported: encoder FPS, board frequency, 200 MHz closure, arbitrary-input 31-bit safety, and complete HEVC acceleration.
- The software corpus is synthetic 8-bit 4:2:0 All-Intra content.
- The RTL kernel supports 4x4 luma and externally supplied exact HM candidate bit counts; it does not implement CABAC context estimation.
- Verified GCP billed spend and remaining promotional credit are unavailable.

## Release Metadata

- Public repository: <https://github.com/duongnguyenhieu/CHIA-RDO>
- Release: `chia-rdo-v1.0.0`
- License: `BSD-3-Clause` (see `LICENSE`); third-party HM source is fetched and not redistributed
- Contact: Nguyen Hieu Duong and Duy Hieu Bui, `24020497@vnu.edu.vn`
