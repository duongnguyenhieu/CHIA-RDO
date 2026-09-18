# Phase 4 Software Pareto Frontier

The frontier uses aggregate held-out BD-rate, measured software RDO reduction, and analytical P=8 estimated hardware cycles. Lower BD-rate/cycles and higher RDO reduction are preferred.

## All Candidates

| Policy | BD-rate | RDO reduction | Est. P8 cycles/event | Winner retention |
|---|---:|---:|---:|---:|
| Adaptive-HW batch-fill baseline P=8 | +1.430% | 77.14% | 14.000 | 75.60% |
| Fixed-K 2 | +1.559% | 94.29% | 14.000 | 53.13% |
| Fixed-K 4 | +1.374% | 88.57% | 14.000 | 66.32% |
| Fixed-K 8 | +1.430% | 77.14% | 14.000 | 75.60% |
| Adaptive-K v0 | +0.005% | 76.06% | 16.987 | 80.12% |
| Fixed-K 16 | +0.016% | 54.29% | 23.000 | 85.70% |
| Adaptive-HW v1 P=8 | +0.013% | 39.40% | 31.224 | 91.02% |
| Adaptive-threshold | -0.026% | 38.21% | 33.596 | 97.91% |
| Relative-SATD | +0.001% | 24.21% | 38.429 | 92.08% |
| Full-RDO | +0.000% | 0.00% | 50.000 | 100.00% |

## Nondominated Set

| Policy | BD-rate | RDO reduction | Est. P8 cycles/event | Winner retention |
|---|---:|---:|---:|---:|
| Adaptive-threshold | -0.026% | 38.21% | 33.596 | 97.91% |
| Adaptive-K v0 | +0.005% | 76.06% | 16.987 | 80.12% |
| Fixed-K 2 | +1.559% | 94.29% | 14.000 | 53.13% |
| Fixed-K 4 | +1.374% | 88.57% | 14.000 | 66.32% |

Quality-optimal: `adaptive_threshold`. Speed-optimal: `fixed_k2`. Balanced under the predeclared aggregate BD-rate and 85% retention constraints: `fixed_k16`.

Adaptive-threshold remains the freeze candidate because it passes every predeclared policy-specific criterion and provides the highest winner retention among the practical non-exhaustive adaptive choices. The frontier still exposes Fixed-K 16 and other alternatives rather than forcing Adaptive-threshold to dominate them.
