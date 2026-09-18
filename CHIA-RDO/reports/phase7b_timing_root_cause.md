# Phase 7B Timing Root Cause

## Measured Critical Paths

| P | Startpoint | Endpoint | Data delay | Cell delay | Route delay | Logic levels |
|---:|---|---|---:|---:|---:|---:|
| 1 | `count_reg_reg[2]` | `candidate_lanes[0].lane_pe/out_distortion_reg[31]/D` | 65.391 ns | 34.071 ns (52.104%) | 31.320 ns (47.896%) | 170 |
| 2 | `launched_count_reg[1]_replica_10` | `candidate_lanes[1].lane_pe/out_distortion_reg[31]/D` | 69.648 ns | 35.610 ns (51.129%) | 34.038 ns (48.871%) | 175 |

At a 5 ns requirement these paths have WNS -60.395 ns and -64.653 ns respectively. P=1 has 69 CARRY8 levels and traverses 4 DSP multipliers plus DSP pre-add/ALU/output stages; P=2 has the same 69 CARRY8 levels and DSP multiplier count with additional LUT depth and routing.

## Classification

The root cause is a giant combinational Full-RDO codec, not the two-stage RD-cost pipeline by itself. The detailed routed path starts in scheduler/control-derived mode selection, enters angular prediction, crosses residual and both forward-transform passes, quantization/dequantization, both inverse-transform passes, reconstruction, and ends at the registered distortion result. Approximately half the delay is logic and half is routing, consistent with an unrolled arithmetic cone spanning the device.

The dominant symptoms are:

- No registers between prediction, residual, transform, quantization, inverse path, reconstruction, and distortion.
- 69 serial CARRY8 levels in the worst path.
- Multiple cascaded DSP arithmetic stages in the same clock cycle.
- High spatial replication and long interconnect; route delay rises from 31.320 ns at P=1 to 34.038 ns at P=2.
- Clock fanout is 1,725 at P=1 and 1,936 at P=2, but clock skew is only about -0.013/-0.014 ns and is not the setup failure cause.

## Optimization Consequence

The first variant serializes work per candidate and places state boundaries at prediction, forward transform pass 1, forward transform pass 2, quantization, inverse transform pass 1, inverse transform pass 2, reconstruction/distortion, and RD cost. This intentionally trades cycles for sharing and removes the complete-codec single-cycle path. Later variants may increase transform or quantization parallelism only after the serial baseline is functionally proven and physically measured.

## Evidence

- `results/phase7b/p1_baseline/timing_paths_detailed.rpt`
- `results/phase7b/p2_baseline/timing_paths_detailed.rpt`
- `build/phase7/vivado/p1-d2-b35-w56/timing_summary.rpt`
- `build/phase7/vivado/p2-d2-b35-w56/timing_summary.rpt`
