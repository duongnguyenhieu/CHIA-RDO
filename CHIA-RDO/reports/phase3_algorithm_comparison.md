# Phase 3 Algorithm Comparison

All values aggregate two deterministic synthetic workloads at matched QP 22/27/32/37. Bitrate and YUV-PSNR columns are the mean of the two QP32 workload measurements; BD-rate uses each workload's Y-PSNR curve and then averages the two BD-rates. Cycle fields are analytical estimates, not FPGA measurements.

| Policy | Avg K | RDO reduction | Winner retention | QP32 kbps | QP32 YUV-PSNR | BD-rate | P | Avg batches | Est. cycles/event |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_rdo | 35.000 | 0.00% | 100.00% | 444.345 | 32.5636 | +0.000% | 4 | 9.000 | 86.000 |
| fixed_k8 | 8.000 | 77.14% | 68.05% | 456.405 | 32.4678 | +3.574% | 4 | 2.000 | 23.000 |
| fixed_k16 | 16.000 | 54.29% | 86.33% | 448.680 | 32.4684 | +1.818% | 4 | 4.000 | 41.000 |
| adaptive_v0 | 11.568 | 66.95% | 75.67% | 453.495 | 32.4986 | +2.866% | 4 | 2.892 | 31.028 |
| adaptive_threshold | 18.651 | 46.71% | 90.25% | 444.210 | 32.5200 | +0.755% | 4 | 4.706 | 47.350 |
| relative_satd | 25.624 | 26.79% | 96.07% | 446.040 | 32.5663 | +0.528% | 4 | 6.549 | 63.937 |
| adaptive_v0_aggressive | 5.814 | 83.39% | 57.53% | 458.025 | 32.3999 | +4.925% | 4 | 1.568 | 19.109 |
| adaptive_hw_batch_fill_p4 | 6.268 | 82.09% | 60.76% | 456.480 | 32.4104 | +4.581% | 4 | 1.567 | 19.103 |
| adaptive_hw_batch_fill_p8 | 8.000 | 77.14% | 68.05% | 456.405 | 32.4678 | +3.574% | 8 | 1.000 | 14.000 |
| adaptive_hw_v1_p4 | 25.620 | 26.80% | 88.98% | 447.330 | 32.5452 | +1.033% | 4 | 6.577 | 64.193 |
| adaptive_hw_v1_p8 | 26.698 | 23.72% | 93.88% | 445.875 | 32.5046 | +0.613% | 8 | 3.752 | 38.771 |

## Answers

1. Adaptive-K v0 is faster than Fixed K=16 but has worse BD-rate and retention; it does not dominate Fixed K=8 or K=16.
2. Adaptive-threshold improves the measured tradeoff: +0.755% BD-rate with 46.7% RDO reduction and 90.2% retention.
3. Relative-SATD improves quality further: +0.528% BD-rate and 96.1% retention, at a smaller 26.8% RDO reduction.
4. Batch-fill adds candidates at unchanged modeled batch cost. Against its exact aggressive-v0 base (+4.925%), P4 reaches +4.581% and P8 +3.574%; it improves quality but saves zero cycles versus that base.
5. Feature-rich HW-v1 strongly improves quality over batch-fill. P8 reaches +0.613%, but relative-SATD still dominates it slightly in both quality and estimated P8 cycles.
6. P changes HW-v1's selected K: the measured average K differs across P=1/2/4/8 because the objective contains batch cost and lane waste.
7. Batch-boundary awareness produces no cycle reduction over its exact base by construction; it provides candidate filling at the same estimated cycles. HW-v1 provides estimated cycle reductions versus Full-RDO through cost-aware K selection.
8. Adaptive-threshold is the balanced point under the 1% BD-rate constraint; relative-SATD is quality-oriented and Fixed K=8 is speed-oriented.
9. The selected controller for the next RTL specification is adaptive-threshold, not HW-v1, because measured data do not justify choosing the more complex controller.
10. Its controller feature vector is `best_rough_cost`, `PU width`, `PU height`, and bit depth, plus configured easy/hard thresholds and K levels. The ranker separately supplies the stable 35-mode rough-cost ordering.

These conclusions apply only to the two deterministic synthetic All-Intra fixtures and are not a general HEVC corpus claim.
