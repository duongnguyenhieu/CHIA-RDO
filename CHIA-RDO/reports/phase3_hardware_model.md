# Phase 3 Analytical Hardware Model

This is an estimated hardware cycle model, not measured RTL or FPGA performance.

For K candidates, parallelism P, initial occupied position `q`, pending batches `b_pending`, fill `F`, drain `D`, per-batch RDO service `R`, and batch overhead `O`:

```text
initial_capacity = P - q
new_batches = 1 + ceil(max(0, K - initial_capacity) / P)
batches = new_batches + b_pending
estimated_cycles = F + batches * (R + O) + D
```

The locked experiments use `q=0`, `b_pending=0`, `F=3`, `D=2`, `R=8`, and `O=1`. They separately record candidate evaluations, RD evaluations, batch count, lane utilization, and estimated cycles. P is restricted to 1/2/4/8; K is restricted to 2/4/8/16/35. Invalid P, K, negative latency, zero RDO service, and impossible batch positions are rejected. The model includes fill/drain and lane waste but not measured memory contention, clock frequency, power, or a complete HEVC datapath.
