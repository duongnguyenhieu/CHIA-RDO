# CHIA Phase-5 Architecture

## Native graph

`experiments/chia_phase5_dse.py` uses CHIA's `@ChiaFunction` API directly. The graph is:

`generate_experiments -> elaborate_rtl[] -> evaluate_result[] -> update_pareto -> persist_result`

The elaboration workers are dispatched asynchronously before any result is resolved. Ray object references connect worker execution to evaluation and Pareto selection. `rtl_sim_cpu` is a real Ray custom resource requirement, not a metadata-only label.

The graph accepts a Ray address for a remote CHIA backend. The local smoke run uses the identical graph and resource scheduling path. Remote GCP execution must not begin until both current billed spend and remaining promotional credit are verified. The fail-closed policy, USD 280 authorization ceiling, USD 20 reserve, and adaptive budget modes are defined in `cloud/cost_policy.md`.

## Design vector

The design key is `(P,D,B,W)`:

- `P`: RDO lane count in `{1,2,4,8}`.
- `D`: PE and scheduler pipeline depth in `{1,2,4}`.
- `B`: candidate capacity in `{35,48,64}`. The frozen policy requires at least 35.
- `W`: Q16.16 cost width in `{48,56}`. Configurations that overflow measured HM vectors are infeasible.

The policy remains `adaptive-threshold.v1` with thresholds `0.04/0.20` and K `4/16/35`. Hardware exploration cannot modify it.

## Evidence levels

- `measured`: HM traces, Verilator functional regression, Verilator elaboration, and later Vivado reports.
- `modeled`: cycles per event and logic-bit storage proxy used for broad screening.
- `unsupported`: prediction, residual formation, transform, quantization, and reconstruction RTL.

Only feasible points participate in the Pareto frontier. Latency and logic storage remain separate objectives; the workflow does not collapse them into a hidden scalar reward.
