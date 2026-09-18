# Phase-7B Gate

## Status: PARTIAL

The optimized Full-RDO kernel passes functional regression, routing, the 70% internal resource budget, and the throughput-improvement gate. It does not close the 5 ns timing constraint, so no 200 MHz or encoder-FPS claim is made.

| Gate | Evidence | Status |
|---|---|---|
| Serial depth-3 correctness | 8,960 vectors, 35 modes, QP 22/27/32/37, zero failures | PASS |
| Width-56 P-way correctness | 28,160 candidate evaluations, P 1/2/4/8, depths 2/3, zero failures | PASS |
| Width-31 P-way correctness | 56,320 candidate evaluations, P 1..8, depths 2/3, zero failures | PASS |
| Extended-P correctness | 17,600 candidate evaluations, P 9/10/12/14/16, depth 3, zero failures | PASS |
| Balanced-tree correctness | 10,560 candidate evaluations, P 1/8/16, depth 3, zero candidate/order/winner/cycle/interface failures | PASS |
| Candidate latency | 132 cycles at depth 3; wrapper batch 134 cycles | PASS |
| Route completion | P16 depth-3 width-31 balanced-tree implementation routed | PASS |
| 70% internal resource budget | 61,207 LUT, 11,895 FF, 816 DSP, 3,162 CARRY8, no BRAM/URAM | PASS |
| Baseline throughput improvement | 8.134 M candidates/s versus 3.823 M candidates/s | PASS, 2.128x |
| 5 ns timing constraint | WNS -9.680 ns, TNS -80,096.086 ns | FAIL |

Vivado ran out of context on `xck26-sfvc784-2LV-c`. Missing `HD.CLK_SRC` and `HD.PARTPIN_LOCS` constraints qualify the timing result; physical resource counts remain authoritative `report_utilization` values.

Evidence: `results/phase7b/serial_rtl_gate_d3.json`, `results/phase7b/pway_rtl_gate.json`, `results/phase7b/pway_rtl_gate_w31.json`, `results/phase7b/pway_rtl_gate_p16.json`, `results/phase7b/pway_rtl_gate_tree.json`, and `results/phase7b/synthesis_results.json`.
