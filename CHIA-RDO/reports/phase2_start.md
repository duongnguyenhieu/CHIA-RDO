# Phase 2 Starting State

Inspection date: 2026-09-08

## Verification

- `git diff --check`: PASS before Phase 2 edits.
- `python3 -m unittest discover -s tests -v`: 5/5 PASS.
- Current project commit: `03c3313`.
- The worktree already contains uncommitted Phase 1 GCP lifecycle scripts,
  provenance updates, and parity reports. They are preserved and are not part of
  the Phase 2 starting baseline.
- No Compute Engine VM, persistent disk, or reserved address remains after the
  Phase 1 parity run.

## Existing Implementation

- HM 16.20 is pinned to `22178e370178133438c0339f57b3b3a29f112909` and
  built by `scripts/setup_hm.sh`.
- `TEncSearch.cpp` computes SATD, mode bits, and rough cost for all 35 luma
  modes, ranks them stably, runs the candidate RD loop, refines the winner, and
  emits JSONL telemetry.
- The immutable exhaustive smoke reference is
  `tiny64-all-intra-full-rdo-qp32-faed5f414b11`.
- Exact local/GCP parity passed for coding metrics and bitstream,
  reconstruction, and trace hashes.
- `experiments/`, `models/`, `rtl/`, and `chia/` contain only sentinels; no
  scheduler RTL or CHIA experiment graph exists yet.
- Existing cloud scripts implement one cost-guarded VM lifecycle but are still
  specialized for the Phase 1 parity workload.

## Safe Extension Point

The first-pass ranking and recursive RDO implementation will not be rewritten.
Phase 2 will always form the complete 35-mode rough-cost ranking and apply the
selected K only to the second-stage RD-loop bound. This avoids MPM append
behavior changing exact-K semantics and leaves winner RQT refinement intact.

Reduced-K runs cannot provide same-state exhaustive winners without performing
the omitted work. Candidate-hit analysis therefore uses independent exhaustive
reference traces and is reported separately from the coding result of a pruned
encode. Reduced-K bitstream equality is not expected and will not be used as a
correctness criterion.

## Initial Limitations

- Available traces are deterministic synthetic All-Intra data at QP 32 only.
- Trace records include searched coding-tree alternatives, not only blocks in
  the final coded tree.
- Timing is host-dependent and short smoke timings are noisy.
- BD-rate requires matched multi-QP curves and is unavailable for the initial
  single-QP pilot.
