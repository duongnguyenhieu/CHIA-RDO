# Phase-7B Pareto

The calibrated analytical frontier contains 16 points. Every point uses pipeline depth 3 and the minimum corpus-safe width of 31 bits; P spans 1..16. Increasing P trades LUT, DSP, and power for increasing Full-RDO kernel throughput.

| Point | P | Estimated LUT | Estimated DSP | Estimated Fmax | Estimated throughput |
|---|---:|---:|---:|---:|---:|
| Minimum resource | 1 | 4,051 | 51 | 76.609 MHz | 0.572 M/s |
| First estimated baseline-throughput win | 8 | 30,765 | 408 | 70.010 MHz | 4.180 M/s |
| Maximum throughput | 16 | 61,295 | 816 | 67.811 MHz | 8.097 M/s |

The measured P8 point reaches 4.084 M candidates/s, 1.068x baseline. The measured P16 balanced-tree point reaches 8.134 M candidates/s, 2.128x baseline, and is selected when maximizing throughput under the 70% internal resource budget.

P16 is not universally dominant because lower-P points consume less LUT, DSP, and power. It is the throughput endpoint of the tradeoff frontier, not a minimum-area or minimum-power winner.

These rates are Full-RDO candidate-kernel throughput proxies computed as `P * Fmax / batch_cycles`; they are not encoder FPS. Evidence: `results/phase7b/pareto.json` and `results/phase7b/synthesis_results.json`.
