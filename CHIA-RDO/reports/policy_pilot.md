# Fixed-K And Adaptive-K v0 Pilot

Run date: 2026-09-08

| Method | Avg K | Winner hit | RDO evals | RDO reduction | Wall s | kbps | Y dB | U dB | V dB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full RDO K=35 | 35.000 | 100.00% | 47,740 | 0.00% | 0.403 | 195.060 | 31.2822 | 37.3787 | 37.2178 |
| Fixed K=2 | 2.000 | 27.79% | 2,728 | 94.29% | 0.069 | 204.780 | 31.0855 | 37.6306 | 37.2955 |
| Fixed K=4 | 4.000 | 43.04% | 5,456 | 88.57% | 0.070 | 199.740 | 31.0504 | 37.7631 | 36.8857 |
| Fixed K=8 | 8.000 | 64.30% | 10,912 | 77.14% | 0.088 | 198.660 | 31.1883 | 37.3482 | 37.2516 |
| Fixed K=16 | 16.000 | 83.80% | 21,824 | 54.29% | 0.128 | 192.900 | 31.0985 | 37.4172 | 37.2889 |
| Fixed K=35 | 35.000 | 100.00% | 47,740 | 0.00% | 0.224 | 195.060 | 31.2822 | 37.3787 | 37.2178 |
| Adaptive-K v0 | 11.930 | 72.58% | 16,272 | 65.92% | 0.113 | 197.160 | 31.1900 | 37.5217 | 37.1017 |

## Findings

Adaptive-K v0 selected average K `11.930`, reduced candidate-loop evaluations by `65.92%`, and retained the matched exhaustive winner in `72.58%` of events.
At P=4 it requires `2.982` average batches, versus 2 for fixed K=8 and 4 for fixed K=16.
Fixed K=35 reproduces the exhaustive bitstream and reconstruction hashes exactly, validating the control path.
Bitrate and PSNR are non-monotonic across this one QP. This is expected because each policy changes mode/tree decisions; only matched multi-QP curves can establish BD-rate.

## Limitations

- Winner hit is candidate-hit correctness, not bitstream equivalence.
- Structural event matching reached 100%, but earlier pruning can still change predictor/reconstruction state.
- Smoke timing is too short and noisy for a performance claim.
- BD-rate is unavailable until matched QP curves are run.
