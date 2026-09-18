# Phase-5 Initial State

## Frozen inputs

- Git HEAD at inspection: `03c3313`; the worktree was already dirty and remains uncommitted.
- HM revision: `22178e370178133438c0339f57b3b3a29f112909` (`HM-16.20`).
- Frozen policy: `adaptive-threshold.v1`, thresholds `0.04/0.20`, K `4/16/35`.
- Phase-4 gate: PASS with `-0.025564794%` aggregate BD-rate, `38.21%` RDO reduction, and `97.91%` winner retention on the synthetic held-out corpus.
- Generalization status remains LIMITED.

## Tools

- CHIA editable checkout with Ray `2.54.0` in `chia_env`.
- Verilator `5.052` in `chia_env`; it is not on the default PATH.
- Vivado `2024.2` at `/tools/Xilinx/Vivado/2024.2/bin/vivado`; local license/part evidence exists for `xck26-sfvc784-2LV-c`.
- GCP project `project-1bfffc90-767b-48e2-ac1` has billing enabled and no running instances, disks, or reserved addresses at inspection.

## Constraints and blockers

- Current GCP spend and remaining free credit are unknown because no billing export is configured. The substantial remote campaign is blocked pending operator confirmation.
- Existing HM telemetry did not expose candidate distortion, rate, or lambda. Phase-5 instrumentation now adds those fields without changing encoder decisions or the frozen algorithm.
- The current MVP validates fixed-point rate-distortion cost formation only. It is not a Full-RDO prediction/transform/quantization datapath.
- Vivado execution is local unless remote installation and licensing are demonstrated.

Protected Phase-4 reports and result JSON files must remain byte-identical throughout Phase 5.
