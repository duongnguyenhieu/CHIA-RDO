# Phase-5 Pareto Analysis

The broad CHIA screen evaluated 72 `(P,D,B,W)` configurations. Verilator elaboration is measured; cycle and storage figures in that screen are explicitly analytical proxies. Width 48 overflows measured HM vectors and is infeasible. B greater than 35 adds capacity unused by the frozen K maximum and is dominated. D greater than 1 adds state unless required for timing.

The measured timing-feasible KV260 set retains P1/D1, P2/D1, P4/D1, and P4/D2 as tradeoffs among LUT, FF, power, and candidate throughput. P4/D2 has slightly better routed timing than P4/D1 but uses 224 more FF and nearly identical power. P8 is not feasible at 200 MHz.

All points use the same frozen `adaptive-threshold.v1` software policy, so the Phase-4 coding metrics remain `-0.025564794%` aggregate BD-rate and `97.91%` winner retention on the synthetic held-out corpus. Those are software coding measurements shared by the hardware points; they are not FPGA-measured quality results.

No encoder frame-throughput claim is made because five upstream RDO stages are not implemented. `max_candidates_per_second` is the only post-route throughput quantity and covers this kernel alone.
