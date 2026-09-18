# Phase 3 State Lock

State captured on 2026-09-09 before Phase 3 algorithm changes.

## Repository

- Repository HEAD: `03c3313 test(chia-rdo): validate larger local HM workload`.
- Branch state: `main` is two commits ahead of `origin/main` and the worktree contains uncommitted Phase 1/2 work.
- `git diff --check`: PASS.
- Existing changes and ignored result artifacts must not be discarded or overwritten.

## HM And Patch Stack

- Encoder: HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909`.
- Phase 1 exhaustive telemetry: `software/patches/hm-16.20-chia-rdo.patch`.
- Phase 2 Fixed-K and Adaptive-K v0: `software/patches/hm-16.20-phase2-k-policy.patch`.
- Phase 2 hardware batch-fill: `software/patches/hm-16.20-phase2-hardware-policy.patch`.
- Current default with no CHIA policy environment remains stock HM; the locked experiment reference uses the separately selected exhaustive path.
- Current patched encoder SHA-256 before Phase 3: `ad5509a197b1392ac85f0c13070efe26ee456067ba01de7bc1b2448d2f5af210`.

## Frozen Baselines

| Baseline | Immutable evidence |
|---|---|
| Full-RDO tiny64 QP32 | `tiny64-all-intra-full-rdo-qp32-faed5f414b11` |
| Full-RDO 128x128 QP32 | `synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5` |
| Fixed K=2/4/8/16/35 | Existing successful records under `results/policy/`; K=35 exactly matches Full-RDO |
| prior-art-inspired Adaptive-K v0 | `tiny64-all-intra-full-rdo-qp32-adaptive-v0-26b250dc6298` |
| Adaptive-HW batch-fill baseline P=1/2/4/8 | Existing `adaptive-hw-p*` records using base K levels 2/4/8 |

The canonical tiny64 Full-RDO invariants are 1,364 search calls, 47,740 candidate RD evaluations, 195.060 kbps, 32.5269 dB YUV-PSNR, bitstream SHA-256 `68de30e7f7ca39f8df9fb412a3c38f31b54aadc063791876525ea94a700d4a45`, reconstruction SHA-256 `9695e6606861cc58de4398bfe70b4b894010ea6a377a8c7adf64db3f9752d606`, and trace SHA-256 `56f12bb400649ea148f2bae06cbf63ea4eb31f915c34dd60fdef2dd761cca7fd`.

## Existing Policy Behavior

- Fixed-K evaluates the first K modes in a stable 35-mode rough-cost ranking.
- prior-art-inspired Adaptive-K v0 uses `confidence=(rough_cost[1]-rough_cost[0])/rough_cost[0]`, thresholds 0.045/0.088, and K levels 16/8/4.
- Adaptive-HW batch-fill starts from the same threshold decision and fills to the largest allowed K that does not add a `ceil(K/P)` batch.
- The latest hardware pilot deliberately used base K levels 2/4/8; it is not a P-only comparison with the Adaptive-K v0 4/8/16 pilot.
- `software/run_policy.py` executes online HM encodes, validates policy traces, decodes the bitstream, and records policy parameters in the experiment identity.

## Existing Telemetry

Exhaustive rows record event identity, QP and CU/PU geometry, a stable 35-mode ranking, per-mode SATD, mode bits and rough cost, per-rank RD costs, selected mode, distortion, and RD cost. Policy schema `chia-rdo.policy-trace.v1` adds selected K, confidence, evaluated prefix, and for hardware batch-fill, base K, P, batch count, and hardware evaluated prefix.

Missing Phase 3 features at state lock are an explicit activity definition, normalized SATD features, current/remaining batch capacity, estimated cycle fields, and a versioned common feature-vector object.

## Existing Measurements

- Fixed-K and Adaptive-K v0 pilot: `reports/policy_pilot.md` and `results/analysis/policy-pilot-summary.json`.
- Exhaustive telemetry analysis: `reports/telemetry_analysis.md`.
- Local/GCP exact parity: `reports/local_gcp_parity.md`.
- GCP Phase 2 bounded adaptive-v0 sweep: `results/cloud/phase2-adaptive-k-sweep/`.
- No matched multi-QP curves or valid BD-rate exist at state lock.
- GCP Phase 2 per-result cost fields are not authoritative because the backend variable was not exported; the launch ledger records a conservative upper bound of USD 0.012759.

## Verification State

- Latest stored Phase 1 quality gate: PASS.
- Current test source contains 10 unit tests; the stored report's older count is stale.
- Full-RDO semantics must be rerun after the Phase 3 patch layer is introduced.

## RTL State

`rtl/rdo_scheduler.sv` is a scheduler, buffer, P-way dispatch, batch counter, and stable minimum-reduction prototype only. Verilator passed 2,000 cases. An interrupted Vivado invocation left partial P=1/P=2 build artifacts, but no completed synthesis result exists. Per Phase 3 rules, no RTL or synthesis work will continue until the software algorithm gate passes.

## Cloud State

The project is `project-1bfffc90-767b-48e2-ac1`. Existing scripts create guarded ephemeral `e2-standard-2` resources and perform idempotent cleanup. Spot CPU quota was previously zero. Resource and billing state must be checked again immediately before any Phase 3 launch.
