# Phase 4 Hardware Cost Model

All cycle values are estimated hardware cycles, not measured RTL or FPGA cycles.

For the locked empty scheduler state, `batches = ceil(K/P)` and `estimated_cycles = 3 + batches*(8+1) + 2`. Variable-K rows average the exact per-event K histogram; they do not apply ceil to average K.

| Policy | P | Avg K | Avg batches | Estimated cycles/event |
|---|---:|---:|---:|---:|
| Adaptive-HW batch-fill baseline P=8 | 1 | 8.000 | 8.000 | 77.000 |
| Adaptive-HW batch-fill baseline P=8 | 2 | 8.000 | 4.000 | 41.000 |
| Adaptive-HW batch-fill baseline P=8 | 4 | 8.000 | 2.000 | 23.000 |
| Adaptive-HW batch-fill baseline P=8 | 8 | 8.000 | 1.000 | 14.000 |
| Adaptive-HW v1 P=8 | 1 | 21.208 | 21.208 | 195.875 |
| Adaptive-HW v1 P=8 | 2 | 21.208 | 10.814 | 102.329 |
| Adaptive-HW v1 P=8 | 4 | 21.208 | 5.407 | 53.665 |
| Adaptive-HW v1 P=8 | 8 | 21.208 | 2.914 | 31.224 |
| Adaptive-threshold | 1 | 21.628 | 21.628 | 199.653 |
| Adaptive-threshold | 2 | 21.628 | 11.064 | 104.576 |
| Adaptive-threshold | 4 | 21.628 | 5.532 | 54.788 |
| Adaptive-threshold | 8 | 21.628 | 3.177 | 33.596 |
| Adaptive-K v0 | 1 | 8.380 | 8.380 | 80.418 |
| Adaptive-K v0 | 2 | 8.380 | 4.190 | 42.709 |
| Adaptive-K v0 | 4 | 8.380 | 2.095 | 23.855 |
| Adaptive-K v0 | 8 | 8.380 | 1.332 | 16.987 |
| Fixed-K 16 | 1 | 16.000 | 16.000 | 149.000 |
| Fixed-K 16 | 2 | 16.000 | 8.000 | 77.000 |
| Fixed-K 16 | 4 | 16.000 | 4.000 | 41.000 |
| Fixed-K 16 | 8 | 16.000 | 2.000 | 23.000 |
| Fixed-K 2 | 1 | 2.000 | 2.000 | 23.000 |
| Fixed-K 2 | 2 | 2.000 | 1.000 | 14.000 |
| Fixed-K 2 | 4 | 2.000 | 1.000 | 14.000 |
| Fixed-K 2 | 8 | 2.000 | 1.000 | 14.000 |
| Fixed-K 4 | 1 | 4.000 | 4.000 | 41.000 |
| Fixed-K 4 | 2 | 4.000 | 2.000 | 23.000 |
| Fixed-K 4 | 4 | 4.000 | 1.000 | 14.000 |
| Fixed-K 4 | 8 | 4.000 | 1.000 | 14.000 |
| Fixed-K 8 | 1 | 8.000 | 8.000 | 77.000 |
| Fixed-K 8 | 2 | 8.000 | 4.000 | 41.000 |
| Fixed-K 8 | 4 | 8.000 | 2.000 | 23.000 |
| Fixed-K 8 | 8 | 8.000 | 1.000 | 14.000 |
| Full-RDO | 1 | 35.000 | 35.000 | 320.000 |
| Full-RDO | 2 | 35.000 | 18.000 | 167.000 |
| Full-RDO | 4 | 35.000 | 9.000 | 86.000 |
| Full-RDO | 8 | 35.000 | 5.000 | 50.000 |
| Relative-SATD | 1 | 26.528 | 26.528 | 243.752 |
| Relative-SATD | 2 | 26.528 | 13.583 | 127.244 |
| Relative-SATD | 4 | 26.528 | 6.791 | 66.122 |
| Relative-SATD | 8 | 26.528 | 3.714 | 38.429 |

Existing scheduler validation status: `PASS` with 2,000 passing and 0 failing cases across P=1/2/4/8 and K=2/4/8/16/35. It validates `ceil(K/P)` batch accounting and stable reduction, but its pipeline timing is not calibration of the analytical constants above.

A fresh Phase-4 Verilator rerun was attempted but the `verilator` executable is not installed in the current environment. Therefore the scheduler statement above uses the existing recorded regression, and no Phase-4 cycle value is labeled as a new RTL measurement.
