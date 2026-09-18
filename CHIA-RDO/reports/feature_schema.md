# Common Feature Schema

Planned schema identifier: `chia-rdo.feature-vector.v1`.

| Feature | Definition | Producer | Consumer | Units/range | Normalization |
|---|---|---|---|---|---|
| `satd_by_mode` | Hadamard first-pass distortion for each of 35 luma modes | HM | all policies/replay | integer distortion | none |
| `rough_cost_by_mode` | `SATD + mode_bits*sqrt(lambda)` | HM | ranking, adaptive-threshold, replay | HM cost | none |
| `mode_bits_by_mode` | estimated mode signaling bits | HM | rough cost/replay | bits | none |
| `satd_rank_by_mode` | stable zero-based rank by absolute SATD | HM telemetry | relative-SATD/replay | 0..34 | divide by 34 when needed |
| `top1_rough_cost` | minimum rough cost | HM | adaptive policies | HM cost | `cost/(PU area*255)` |
| `top2_rough_cost` | second ranked rough cost | HM | Adaptive-K v0/hardware v1 | HM cost | same as top-1 |
| `top2_gap` | `top2-top1` | HM | diagnostics | HM cost | relative gap below |
| `relative_gap` | `(top2-top1)/top1`, zero if top1 is zero | HM | Adaptive-K v0/hardware v1 | nonnegative ratio | intrinsic |
| `relative_satd_by_mode` | `(SATD_i-min(SATD))/max(min(SATD),1)` | HM/Python reference | relative-SATD/hardware v1 | nonnegative ratio | intrinsic |
| `activity` | mean absolute deviation of original luma samples from their PU mean | HM | hardware v1 | sample levels | divide by 255 |
| `qp` | active CU QP | HM | hardware v1 | 0..63 | policy uses clipped `(37-QP)/15` |
| `cu_width`, `cu_height` | CU dimensions | HM | analysis/hardware v1 | pixels | area relative to 4096 |
| `pu_width`, `pu_height` | active PU dimensions | HM | normalization/hardware v1 | pixels | area relative to 4096 |
| `candidate_count` | selected K | HM | metrics/model | 1..35 | none |
| `parallelism_p` | modeled hardware lane count | policy config | hardware policies/model | 1/2/4/8 | none |
| `current_batch_position` | occupied lanes in the current batch when the event begins | model state | hardware v1/model | 0..P-1 | none |
| `remaining_batch_capacity` | `P-current_batch_position` | model | hardware v1/model | 1..P | none |
| `pending_batches` | explicit queued batches before this event | model state | hardware v1/model | nonnegative count | none |
| `pipeline_fill_cycles` | configured model fill latency | model config | model/hardware v1 | cycles | none |
| `pipeline_drain_cycles` | configured model drain latency | model config | model/hardware v1 | cycles | none |
| `rdo_cycles_per_batch` | configured analytical batch service cost | model config | model/hardware v1 | cycles/batch | none |

No measured FPGA state is available. Batch state and cycle fields are analytical inputs and must be labeled estimated. Online HM decisions begin each independently modeled PU event with batch position zero and no pending batches unless an experiment explicitly supplies another replay state.
