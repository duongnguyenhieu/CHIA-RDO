# Phase 3 Pareto Analysis

All policies are compared at analytical P=8 for a common hardware-width view.

## BD-rate Versus Estimated Cycles

| Policy | BD-rate | Est. cycles/event |
|---|---:|---:|
| full_rdo | +0.000% | 50.000 |
| fixed_k8 | +3.574% | 14.000 |
| fixed_k16 | +1.818% | 23.000 |
| adaptive_v0 | +2.866% | 19.064 |
| adaptive_threshold | +0.755% | 27.174 |
| relative_satd | +0.528% | 37.034 |
| adaptive_hw_batch_fill_p8 | +3.574% | 14.000 |

## Winner Retention Versus Estimated Cycles

| Policy | Retention | Est. cycles/event |
|---|---:|---:|
| full_rdo | 100.00% | 50.000 |
| fixed_k8 | 68.05% | 14.000 |
| fixed_k16 | 86.33% | 23.000 |
| adaptive_v0 | 75.67% | 19.064 |
| adaptive_threshold | 90.25% | 27.174 |
| relative_satd | 96.07% | 37.034 |
| adaptive_hw_batch_fill_p8 | 68.05% | 14.000 |

Adaptive-threshold is the lowest-cycle point satisfying the strict BD-rate <1% gate. Relative-SATD is the quality-oriented adaptive policy. HW-v1 P8 satisfies the gate but is dominated by relative-SATD on these fixtures.
