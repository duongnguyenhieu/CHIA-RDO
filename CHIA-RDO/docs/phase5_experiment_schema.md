# Phase-5 Experiment Schema

Each `chia-rdo.phase5-experiment.v1` record contains:

| Field | Type | Provenance |
|---|---|---|
| `key` | string | Canonical `pP-dD-bB-wW` design identity |
| `p` | integer | RDO lane count |
| `pipeline_depth` | integer | Configured RTL pipeline depth |
| `buffer_depth` | integer | Maximum scheduler candidate capacity |
| `cost_width` | integer | Q16.16 RD-cost width |
| `verilator_status` | string | Measured tool outcome |
| `verilator_seconds` | number | Measured worker wall time |
| `verilator_log_sha256` | string | Hash of tool output |
| `worker_host` | string | Execution host identity |
| `average_cycles_per_event` | number | Analytical model using the measured Phase-4 K distribution |
| `logic_bit_proxy` | integer | Analytical register/storage proxy, not LUT/FF area |
| `hm_vector_overflow` | integer | Whether measured HM vectors exceed W |
| `feasible` | boolean | False on measured-vector overflow |
| `quality_policy` | string | Frozen policy identity |
| `qp_values` | integer array | HM vector QP coverage |
| `measurement_level` | string | Explicit measured/modeled provenance |

Vivado timing, LUT, FF, BRAM, DSP, power, and derived throughput belong to a separate synthesis record and must never be populated from analytical proxies.
