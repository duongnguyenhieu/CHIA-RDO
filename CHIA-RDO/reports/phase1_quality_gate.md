# Phase 1 Quality Gate

Gate execution: 2026-09-08 10:49:49 UTC

Status: **PASS**

Primary machine-readable evidence:
`results/quality_gate/20260908T104949Z/phase1-quality-gate.json`

## Tests

| Test | Method | Expected result | Actual result | Status | Evidence path |
|---|---|---|---|---|---|
| HM baseline reproducibility | Run unit tests and repeat the exhaustive encode in a new evidence directory | Tests pass and immutable output hashes match the recorded baseline | 4 unit tests passed; repeated hashes are checked separately below | PASS | `results/quality_gate/20260908T104949Z/unit-tests.log` |
| All 35 modes covered | Validate every `ranked_modes` vector | Every event is a permutation of modes 0 through 34 | All 1,364 events cover all 35 modes exactly once | PASS | `results/quality_gate/20260908T104949Z/repeat-intra-rdo.jsonl` |
| SATD telemetry | Check nonnegative SATD and `rough_cost = SATD + mode_bits * sqrt(lambda)` within each event | Every event satisfies the HM rough-cost identity and content produces mode-dependent values | All 1,364 events satisfy the identity; 1,344 have mode-dependent SATD | PASS | `results/quality_gate/20260908T104949Z/repeat-intra-rdo.jsonl` |
| Candidate ranking | Reconstruct stable ordering from `rough_cost_by_mode` | Reconstructed and recorded rankings match | All 1,364 rankings match | PASS | `results/quality_gate/20260908T104949Z/repeat-intra-rdo.jsonl` |
| RD-cost telemetry | Check vector length, finiteness, sign, winner membership, and winner-cost bound | Every executed candidate has a valid cost and the winner is in the list | All 1,364 events satisfy the invariants | PASS | `results/quality_gate/20260908T104949Z/repeat-intra-rdo.jsonl` |
| RDO count | Sum event counters | `search_calls * 35` | `1,364 * 35 = 47,740` | PASS | `results/quality_gate/20260908T104949Z/phase1-quality-gate.json` |
| RQT refinement count | Sum event refinement counters | One stock-HM winner refinement per event | 1,364 refinements for 1,364 events | PASS | `results/quality_gate/20260908T104949Z/phase1-quality-gate.json` |
| Encoder/decoder reconstruction | Decode repeated bitstream and compare SHA-256 | Encoder reconstruction equals decoder output | Both equal `9695e6606861cc58de4398bfe70b4b894010ea6a377a8c7adf64db3f9752d606` | PASS | `results/quality_gate/20260908T104949Z/repeat-decoded.yuv` |
| Bitstream determinism | Compare repeated exhaustive output with recorded baseline | Hash remains unchanged | Both equal `68de30e7f7ca39f8df9fb412a3c38f31b54aadc063791876525ea94a700d4a45` | PASS | `results/quality_gate/20260908T104949Z/repeat-exhaustive.bin` |
| Parser and trace determinism | Parse the same log twice and compare repeated JSONL with recorded JSONL | Parsed objects and trace bytes remain unchanged | Trace hash remains `56f12bb400649ea148f2bae06cbf63ea4eb31f915c34dd60fdef2dd761cca7fd` | PASS | `results/quality_gate/20260908T104949Z/repeat-intra-rdo.jsonl` |
| Trace corresponds to HM decisions | Validate that each winner was executed and its final refined cost is no greater than the initial candidate minimum | Every event identifies the candidate-loop winner produced by HM | All 1,364 events satisfy the decision invariants | PASS | `results/quality_gate/20260908T104949Z/repeat-intra-rdo.jsonl` |
| Instrumentation transparency | Build pristine HM-16.20 and compare stock encoding against patched HM with CHIA variables unset | Bitstream, reconstruction, and coding metrics are identical | Both stock bitstreams hash to `af27f0269993d15d1e177965a6ea8571c8cdfbd2c9633c896151c8470ad48f4a` | PASS | `results/quality_gate/20260908T104949Z/` |
| Larger benchmark available | Validate a deterministic configuration larger than the smoke input | A generator-compatible configuration larger than 64x64 exists | `synthetic-128x128-8f-yuv420p8`, 128x128, 8 frames | PASS | `configs/nontrivial_local.json` |

## Executed Experiment

The gate repeated the exhaustive 64x64, four-frame, QP 32 experiment in a new
directory. It also ran two stock-policy encodes: one with the instrumented
binary and one with an independently cloned and built pristine HM-16.20 binary.
No previous experiment directory was overwritten.

## Interpretation

The telemetry is internally consistent and deterministic enough to support
candidate-policy work. Constant SATD across all modes occurred in 20 of 1,364
events. These are valid boundary/reference-availability cases, not a global
telemetry failure; the other 1,344 events show mode-dependent SATD.

The trace records actual candidate-search alternatives and the selected luma
candidate-loop winner. It does not claim that every traced alternative becomes
a coding-tree unit committed to the final bitstream.

## Limitations

- `HHI_RQT_INTRA_SPEEDUP` remains enabled. All 35 luma modes enter the candidate RD loop, while transform-tree refinement follows stock HM behavior.
- The validated 64x64 input is synthetic and only establishes correctness and reproducibility.
- The 128x128 benchmark is available but is intentionally executed after the Git checkpoint, following the phase order.
- No GCP resource was used. Cloud cost remains USD 0.

## Decision

**PHASE 1 QUALITY GATE: PASS**

The project may proceed to the larger local validation. GCP bootstrap remains
blocked until that run is recorded and reviewed.
