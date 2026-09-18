# Phase-7B Optimization

## Selected Configuration

`serial-p16-d3-w31-tree` is the measured throughput winner among routed configurations that fit the 70% internal resource budget.

| Metric | Baseline P1 | P16 serial scan | P16 balanced tree |
|---|---:|---:|---:|
| LUT | 36,454 | 60,232 | 61,207 |
| FF | 1,714 | 11,850 | 11,895 |
| DSP | 178 | 816 | 816 |
| CARRY8 | 3,653 | 3,159 | 3,162 |
| Power | 1.667 W | 2.338 W | 2.288 W |
| WNS | -60.395 ns | -19.092 ns | -9.680 ns |
| Derived Fmax | 15.292 MHz | 41.508 MHz | 68.120 MHz |
| Kernel throughput proxy | 3.823 M/s | 4.956 M/s | 8.134 M/s |

The balanced tree adds 975 LUTs and 45 FFs relative to the P16 serial scan, leaves DSP effectively unchanged, reduces reported power by 0.050 W, and improves derived Fmax by 64.1%. Kernel throughput improves by 112.8% over baseline.

The old P16 path crossed the serial 16-way winner reduction and had 80 logic levels. The new critical path is internal to one candidate lane, has 39 logic levels, and ends in a residual-sample RAM input. Further timing work must therefore target the forward-transform accumulation/lane datapath rather than winner selection.

The selected design consumes 74.66% of the LUT budget and 93.47% of the DSP budget, equivalent to 52.26% and 65.38% of the full device respectively. DSP is the limiting internal budget with 57 DSP48E2 blocks of headroom.

Cost width 31 is justified by the observed regression corpus maximum RD cost of 1,312,532,898. This is not a formal arbitrary-input bound.
