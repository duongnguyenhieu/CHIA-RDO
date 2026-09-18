# Proposal Algorithm Requirements

Source of truth: `docs/project_plan.md`, especially lines 68-118 and 156-168.

| Requirement | Current status at Phase 3 lock | Implementation location | Missing work | Planned experiment |
|---|---|---|---|---|
| Preserve Full-RDO and compare identical tuples | Baseline verified at QP32 | `software/run_baseline.py`, Phase 1 patch and quality gate | Regress after Phase 3 patch; create references for every matched QP | Hash and metric regression, then matched QP 22/27/32/37 |
| Independently written adaptive-threshold policy inspired by Chung/Yim | Missing; Adaptive-K v0 is not a substitute | None | Explicit independent feature, thresholds, K levels and documentation | Bounded replay search, online finalists, matched multi-QP |
| Independently written relative-SATD policy inspired by Gwon/Choi | Missing | None | Define normalization and selection rule without claiming exact paper reproduction | Bounded replay search, online finalists, matched multi-QP |
| Preserve prior-art-inspired Adaptive-K v0 | Complete online baseline | `TEncSearch.cpp`, `software/run_policy.py` | Freeze name and artifacts | Include unchanged in matched matrix |
| Unit tests for ranking, ties, thresholds, bounds and deterministic K | Partial | `tests/test_baseline.py` | Add both new policies, feature and replay tests | Unit suite and online trace validation |
| Report K, RDO evaluations, runtime, bitrate and PSNR | Complete for existing online policies | `software/run_policy.py` | Extend schema for new policy/model fields | Every online run |
| BD-rate only from complete matched curves | Not available | Result schema currently stores `null` | QP 22/27/32/37 references and policy runs; implement calculation | Matched multi-QP matrix |
| Hardware policy uses SATD features, activity, QP, CU size, P and explicit hardware state | Missing; current policy only uses confidence and P | Existing batch-fill in `TEncSearch.cpp` | Common feature schema and feature-rich `adaptive_hw_v1` | Replay search and matched online matrix for every P |
| Batch-boundary-aware actions | Baseline fill exists | `hardware_fill_k`, HM adaptive_hw path | Preserve as `adaptive_hw_batch_fill_baseline`; add cost-aware v1 decisions | Counterexamples and P=1/2/4/8 comparison |
| Decisions replayable from recorded feature vectors | Partial for confidence policy | Policy JSONL and `scripts/sweep_policy_replay.py` | Version common feature vector and replay all policies | Online/replay decision equivalence |
| Default quality constraint delta BD-rate below 1% | Not evaluable | Project plan | Enforce after matched curves | Pareto feasibility filter |
| Analytical cycle model for fill/drain, latency, bubbles and utilization | Missing | None | Versioned model with explicit estimated status and infeasibility checks | Unit tests and per-experiment estimates |
| Cycle model and RTL agree later | Scheduler regression exists, comparison missing | `rtl/rdo_scheduler.sv` and regression | Defer RTL work; validate analytical `ceil(K/P)` against existing scheduler evidence only | Software gate report, no new RTL |
| Matched central Fixed-K/software-adaptive/hardware-aware experiment | Missing | Existing pilots are unmatched in policy levels | Build one immutable experiment matrix | Same sequence, QP, encoder config and P |
| Pareto frontiers preserve hard quality constraints | Missing | None | BD-rate/cycle and retention/cycle frontiers with tests | Database-derived analysis |
| Distinguish measured, modeled and unavailable values | Partial | Existing reports qualify BD-rate/timing | Add typed provenance to database/reports | Gate audit |

The proposal does not contain enough detail to claim exact reproduction of Chung/Yim or Gwon/Choi. New policies will therefore be labeled inspired implementations, with their exact mathematical definitions owned and documented by this project.
