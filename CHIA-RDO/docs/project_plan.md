# CHIA-RDO Project Plan

## Research Scope

The contribution under study is hardware-aware adaptive RDO candidate budgeting
that jointly explores candidate policy, parallel width, and microarchitecture.
Adaptive candidate reduction itself is prior art and will be treated only as a
baseline. No claim of novelty or performance will be made before reproducible
experiments support it.

The key quantity to preserve throughout the software and hardware measurements
is:

```text
RDO batches = ceil(K / P)
```

Every phase has a runnable checkpoint and a verification gate. A later phase
must not consume synthetic or estimated measurements as if they were measured
HEVC, RTL, or synthesis results.

## Phase 0: Environment

Status: complete

Outputs:

- Host, CHIA API/runtime, toolchain, HEVC, RTL, Vivado license, FPGA, and GCP inventory.
- Reproducible minimal Conda specification.
- Explicit separation of local licensed synthesis from future GCP workloads.
- No cloud resources created and no credentials recorded.

Gate:

- CHIA 1.0.1 imports in `chia_env`.
- Ray and Google Compute client imports pass.
- ADC performs a real read against the selected candidate GCP project.
- Vivado performs a real `synth_design` for the KV260 device.

## Phase 1: Full-RDO HEVC Baseline

Status: smoke baseline, instrumentation quality gate, and deterministic
128x128x8 local validation passed on 2026-09-08. The next required checkpoint
is local/GCP parity.

Acquire and pin a public HM release, document source provenance and license,
build the encoder reproducibly, and add one small deterministic smoke sequence.
Then add a full-RDO configuration and instrumentation for encoding time,
candidate modes, RDO evaluation count, bitrate, PSNR, and CU/PU statistics where
HM exposes them. Store raw logs separately from parsed JSON.

Gate:

- A clean checkout can build HM using documented commands.
- Repeated smoke runs produce equivalent bitstream metrics and schema-valid JSON.
- No adaptive candidate pruning is enabled.
- Baseline result records source revision, config hash, sequence hash, QP, host, and runtime.

Exact next implementation step:

```text
Add a dependency bootstrap/check script, pin HM-16.20 source provenance, build
EncoderApp with GCC/CMake, and run one deterministic all-intra Full-RDO smoke
encode that emits results/baseline/<experiment-id>.json.
```

## Phase 2: Prior-Art-Inspired Adaptive-K Baselines

Implement two independently written policies behind one candidate-selection
interface: an adaptive threshold policy inspired by Chung/Yim and a relative
SATD policy inspired by Gwon/Choi. Preserve citations and avoid copying source.
Compare each policy with full RDO on identical sequence/QP/config tuples.

Gate:

- Unit tests cover ranking, ties, thresholds, bounds, and deterministic K.
- Every run reports K distribution, RDO evaluations, runtime, bitrate, and PSNR.
- BD-rate is computed only from complete, matched QP curves.

## Phase 3: Hardware-Aware Policy

Add policies parameterized by SATD features, activity, QP, CU size, P, and
explicit hardware state. Include batch-boundary-aware actions without assuming
that SATD gap is the optimal confidence feature. Keep software-adaptive and
hardware-aware policy families distinguishable in every result.

Gate:

- Counterexample tests cover `P=4`: K=3 and K=4 share one batch; K=5 uses two.
- Policy decisions are replayable from recorded feature vectors.
- The default quality constraint is delta BD-rate below 1 percent.

## Phase 4: Cycle Model

Implement a fast analytical model for SATD, control, buffering, pipeline fill,
RDO latency, bubbles, utilization, and `ceil(K/P)` batches. Add conservative
dominance pruning and calibrate parameters against the RTL testbench later.

Gate:

- Closed-form tests cover all P values and K boundaries.
- Model rejects infeasible buffer/pipeline combinations with explicit reasons.
- Model outputs identify estimates rather than measured RTL values.

## Phase 5: Parameterized RTL Prototype

Implement functionally correct SATD/ranking, K control, candidate dispatch, P
parallel simplified RDO processing elements, and best-mode reduction. Parameters
will include P in 1/2/4/8, pipeline depth, buffer depth, SATD width, and candidate
count. Verilator provides correctness and cycle measurements; local Vivado
provides Fmax and area for KV260.

Gate:

- RTL and analytical model agree on candidate selection and batch count.
- Tests cover backpressure, partial final batches, ties, reset, and bubbles.
- Synthesis reports are parsed from tool output, never fabricated.

## Phase 6: CHIA Agentic Loop

Represent HEVC evaluation, model screening, RTL simulation, local synthesis,
result persistence, and Pareto evaluation as resource-tagged `ChiaFunction`
nodes. Expose constrained experiment tools through `ChiaTool` so an agent can
propose legal policies and architectures. Cache by immutable experiment ID.

Initial backend mapping:

```text
Local licensed worker: Vivado synthesis and implementation
Local or GCP CPU worker: HEVC encode, analytical model, Verilator simulation
Head worker: result index, cache, Pareto update, cost ledger
Agent worker: proposal and feedback loop
```

Gate:

- A deterministic non-agent loop completes end to end first.
- Agent proposals are schema-validated and constrained before execution.
- Duplicate experiment IDs resolve from cache.

## Phase 7: GCP Scaling

Add cost-controlled Compute Engine workers using CHIA's native `gcp_nodes`
support. Begin with small Spot CPU instances for screening and promote only
non-dominated designs. Use shutdown traps, VM labels, budget checks, per-run cost
records, and no cloud Vivado claim.

Gate:

- User confirms project, region, zone, quotas, budget, and network policy.
- Setup and shutdown are idempotent.
- An interrupted Spot run is retried from cache without duplicating completed work.
- `results/cost_log.json` records estimated cost and experiment identity.

## Phase 8: Analysis and Reporting

Run the central fixed-K versus software-adaptive-K versus hardware-aware-K
experiment for P=1/2/4/8. Generate matched quality curves, measured hardware
tables, Pareto frontiers, figures, and reports that answer the nine required
research questions. Clearly label measured, modeled, and unavailable fields.

Gate:

- Every plotted row traces to immutable raw configuration and result artifacts.
- Delta BD-rate uses matched sequences and QPs.
- Pareto calculations have unit tests and preserve hard quality constraints.
- Claims distinguish observations, statistical uncertainty, and hypotheses.

## Reproducibility Rules

- Do not hard-code machine-specific paths; use config files and environment variables.
- Hash input sequence, encoder config, policy config, RTL parameters, and tool versions.
- Include repository commit, timestamp, runtime, sequence, QP, policy, P, pipeline, BD-rate, PSNR, cycles, Fmax, and area where applicable.
- Cache only successful outputs under a complete experiment identity.
- Persist raw logs and parsed results; parsers must fail visibly on missing metrics.
- Never store cloud credentials in the repository, results, logs, containers, or VM images.
- Never infer Vivado metrics for cloud experiments when synthesis ran only locally.

## Deferred Decisions

Phase 0 deliberately does not select the final policy representation, search
algorithm, database schema, GCP machine family, dataset suite, or RTL datapath.
Those decisions will be made only after the full-RDO baseline exposes the actual
HM integration points and measurement overhead.
