# Phase-5 Gate

Overall status: **BLOCKED / NOT PASS**

| Requirement | Status | Evidence |
|---|:---:|---|
| Phase-4 artifacts immutable | PASS | Protected SHA-256 values unchanged |
| Frozen policy unchanged | PASS | `adaptive-threshold.v1`, 0.04/0.20, K 4/16/35 |
| Native CHIA asynchronous graph | PASS (local) | 72-point local Ray graph with `ChiaFunction` nodes and object refs |
| Remote GCP CHIA execution | BLOCKED | Live billing query returned no verified spend/free-credit balance |
| Substantial GCP campaign | BLOCKED | USD 1.643220 next-campaign estimate recorded, but no Phase-5 cloud resources launched; `$0.00` known incremental spend |
| HM candidate D/R/lambda vectors | PASS | 7,000 candidates, QP 22/27/32/37, bit-exact coding output |
| Stage-by-stage Full-RDO vectors | FAIL | Prediction/residual/transform/quantization/reconstruction unavailable |
| Fixed-point RD cost PE | PASS | 7,002/7,002 Verilator vectors |
| Full-RDO PE | FAIL | Only cost formation is implemented |
| P-way integration | PASS | 24/24 integrated array scenarios across P 1/2/4/8 and D 1/2/4 |
| Vivado evidence | PASS (kernel scope) | Six KV260 post-route implementations with timing, area, DSP, BRAM, and power estimates |
| 5 ns timing | PARTIAL | P1/P2/P4 pass; P8 fails |
| Synthesis feedback loop | PASS | Arithmetic pipeline and balanced reduction implemented after measured failure |
| Pareto analysis | PASS (kernel scope) | Measured synthesis frontier kept separate from analytical CHIA screen |
| Encoder/FPGA throughput | NOT CLAIMED | Full datapath is absent; only candidate-kernel rates are reported |

Phase 5 cannot receive PASS while the Full-RDO stages and substantial GCP run are absent. All partial evidence is labeled by scope and provenance.
