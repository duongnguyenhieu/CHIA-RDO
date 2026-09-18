# Phase 7B DSP Breakdown

## Measured Hierarchy

P=1 has 178 DSP48E2 blocks. The `full_rdo_codec_4x4` instance owns 176 and the pipelined `rdo_pe` owns 2. P=2 duplicates this exactly: each lane owns 176 codec DSPs plus 2 RD-cost DSPs, for 356 total.

| Function per lane | DSP48E2 | Attribution evidence |
|---|---:|---|
| Intra angular prediction/interpolation | 64 | `angular_temporary*` primitive names |
| Forward transform | 0 | Constant DST arithmetic mapped to LUT/CARRY |
| Quantization | 32 | `(null)[0].value4*` wide variable-scale products |
| Inverse quantization | 32 | `clip164*` wide variable-scale products |
| Inverse transform | 0 | Constant DST arithmetic mapped to LUT/CARRY |
| Reconstruction | 0 | Add/clip logic |
| Distortion | 48 | `distortion*` square and accumulation primitives |
| RD arithmetic | 2 | `rd_cost/multi_stage.rate_stage0*` |
| **Total per lane** | **178** | Vivado hierarchy and DSP cell inventory |

The transform stages consume no DSP48E2 blocks in this implementation, but they are major LUT/CARRY consumers because all constant matrix products and additions are spatially unrolled. DSP reduction alone will not resolve P=4; transform serialization is needed for LUT/CARRY reduction, while prediction, quantization, inverse quantization, and distortion sharing target DSP reduction.

## Scaling

The physical DSP law is exactly `178 * P`, not `1602 * P`. The earlier 1,602/3,204/6,408 values were logical-cell parser artifacts. Physical DSP replication is still linear and confirms that every P-way lane duplicates the complete codec and RD-cost datapath.

## Evidence And Limits

- `results/phase7b/p1_baseline/utilization_hierarchical.rpt`
- `results/phase7b/p2_baseline/utilization_hierarchical.rpt`
- `results/phase7b/p1_baseline/dsp_cells.rpt`
- `build/phase7/vivado/p1-d2-b35-w56.log`

The codec is one monolithic combinational module, so Vivado cannot report transform/quant/reconstruction as separate RTL hierarchy. Functional attribution within the 176 codec DSPs uses preserved synthesized primitive names mapped to the corresponding named RTL expressions. The exact hierarchy total is measured; the functional grouping is name-based attribution, not an isolated-block utilization run.
