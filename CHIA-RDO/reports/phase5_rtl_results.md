# Phase-5 RTL Results

## Scope

The implemented MVP is a fixed-point HEVC rate-distortion cost-formation kernel, not a complete Full-RDO codec datapath. It computes `J_q16 = (D << 16) + R * lambda_q16`, propagates candidate identity, saturates explicitly on overflow, supports ready/valid backpressure, and integrates `P` copies with streaming scheduling and stable best-candidate reduction.

Prediction, residual formation, transform, quantization, and reconstruction remain unsupported in RTL and are not counted as passing stages.

## HM vectors and Verilator

- HM revision: `22178e370178133438c0339f57b3b3a29f112909`.
- QP coverage: 22, 27, 32, and 37.
- Instrumentation leaves all four baseline bitstreams byte-identical.
- Cost PE: 7,002/7,002 vectors PASS, including 7,000 HM candidates and two boundary/overflow vectors.
- Maximum absolute Q16.16 versus HM-double cost error: `0.0704224` cost units.
- Integrated array: 24/24 scenarios PASS over P `{1,2,4,8}`, D `{1,2,4}`, K=35, and tail batches.

## KV260 post-route

Vivado 2024.2, `xck26-sfvc784-2LV-c`, out-of-context implementation, 5 ns constraint:

| P | D | LUT | FF | DSP | BRAM | WNS ns | Timing | Power W |
|---:|---:|---:|---:|---:|---:|---:|:---:|---:|
| 1 | 1 | 184 | 143 | 18 | 0 | +2.105 | PASS | 0.292 |
| 2 | 1 | 402 | 207 | 36 | 0 | +1.253 | PASS | 0.296 |
| 4 | 1 | 821 | 335 | 72 | 0 | +0.303 | PASS | 0.307 |
| 4 | 2 | 821 | 559 | 72 | 0 | +0.439 | PASS | 0.308 |
| 8 | 1 | 1780 | 594 | 144 | 0 | -0.989 | FAIL | 0.330 |
| 8 | 2 | 1789 | 1040 | 144 | 0 | -1.021 | FAIL | 0.334 |

Power is Vivado vectorless estimation. Fmax and candidate rates in `results/phase5/vivado_kv260.json` are derived from post-route timing, not measured on a board. P8 is infeasible at the requested 5 ns target and its derived lower-frequency rate is diagnostic only.

## Feedback

The first synthesis used a serial comparator chain and a non-arithmetic output delay. It failed timing at P4 and P8. The revised PE places a register between multiplication and accumulation for D >= 2, and the array uses a balanced lane-reduction tree. P4 subsequently met timing; P8 remained outside the 5 ns constraint and is excluded from the timing-feasible frontier.
