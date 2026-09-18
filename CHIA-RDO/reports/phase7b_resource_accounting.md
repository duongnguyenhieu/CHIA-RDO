# Phase 7B Resource Accounting

## Scope

The baseline runs target `xck26-sfvc784-2LV-c` with Vivado 2024.2. They are top-level `full_rdo_pway` out-of-context runs, not IP-only utilization reports. P=1 and P=2 are routed designs; P=4 reached synthesis and failed placement DRC.

## Accounting Correction

The original Phase-7 JSON used `get_cells -hierarchical -filter {REF_NAME =~ LUT*}` and equivalent patterns. Those values count logical primitives before physical LUT combining and also produced incorrect DSP totals. They are not device utilization.

The authoritative values below come from the `Used` column of Vivado `report_utilization`. The old values remain in `results/phase7/vivado_results.json` under `logical_cell_counts`; the primary `lut`, `ff`, `dsp`, `bram`, and `uram` fields now contain physical utilization.

| P | Report state | CLB LUT | CLB registers | DSP48E2 | BRAM tiles | URAM | CARRY8 |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Routed | 36,454 | 1,714 | 178 | 0 | 0 | 3,653 |
| 2 | Routed | 70,817 | 1,913 | 356 | 0 | 0 | 7,326 |
| 4 | Synthesized | 140,102 | 2,221 | 712 | 0 | 0 | 14,665 |

## Device Capacity And Internal Budget

| Resource | Device available | 70% internal budget |
|---|---:|---:|
| CLB LUT | 117,120 | 81,984 |
| CLB register | 234,240 | 163,968 |
| DSP48E2 | 1,248 | 873 |
| BRAM tile | 144 | 100 |
| URAM | 64 | 44 |
| CARRY8 | 14,640 | 10,248 |

Integer budgets are rounded down. They reserve at least 30% for AXI, control, buffers, integration, clocks/reset, and future encoder infrastructure.

## P=4 Breakpoint

P=4 is resource infeasible. After `opt_design`, placement DRC reported 139,452 LUT-as-logic cells for 117,120 sites and 14,649 CARRY8 cells for 14,640 sites. Vivado emitted `DRC UTLZ-1` and did not run the placer. P=4 timing, WNS, TNS, and Fmax are therefore `NOT AVAILABLE` and are not interpolated.

The breakpoint is LUT/CARRY limited, not DSP-site limited: P=4 uses 712 of 1,248 DSP48E2 sites (57.05%) but exceeds LUT capacity.

## Evidence

- `build/phase7/vivado/p1-d2-b35-w56/utilization_route.rpt`
- `build/phase7/vivado/p2-d2-b35-w56/utilization_route.rpt`
- `build/phase7/vivado/p4-d2-b35-w56/utilization_synth.rpt`
- `build/phase7/vivado/p4-d2-b35-w56.log`
- `results/phase7b/p1_baseline/utilization_hierarchical.rpt`
- `results/phase7b/p2_baseline/utilization_hierarchical.rpt`
- `results/phase7b/resource_accounting.json`
