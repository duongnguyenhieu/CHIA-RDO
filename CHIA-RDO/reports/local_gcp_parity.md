# Local/GCP Phase 1 Parity

Run date: 2026-09-08

Status: PASS

## Configuration

- Local reference: `tiny64-all-intra-full-rdo-qp32-faed5f414b11`
- GCP replicate: `tiny64-all-intra-full-rdo-qp32-faed5f414b11-gcp-parity`
- GCP target: one on-demand `e2-standard-2` in `us-central1-a`
- OS: Ubuntu 24.04, Linux `7.0.0-1011-gcp`, x86-64
- HM: 16.20 revision `22178e370178133438c0339f57b3b3a29f112909`
- Compiler: GCC/G++ 13.3.0
- Input: deterministic 64x64 YUV420p8, 4 frames, QP 32

## Parity Result

All recorded coding metrics match, including per-picture bits and PSNR:

| Metric | Local | GCP |
|---|---:|---:|
| Bitstream bytes | 3,251 | 3,251 |
| Annex-B bitrate | 195.060 kbps | 195.060 kbps |
| YUV-PSNR | 32.5269 dB | 32.5269 dB |
| Search calls | 1,364 | 1,364 |
| RDO evaluations | 47,740 | 47,740 |
| RQT refinements | 1,364 | 1,364 |
| Average/minimum/maximum K | 35/35/35 | 35/35/35 |

Artifact equality:

| Artifact | Matching SHA-256 |
|---|---|
| Bitstream | `68de30e7f7ca39f8df9fb412a3c38f31b54aadc063791876525ea94a700d4a45` |
| Reconstruction | `9695e6606861cc58de4398bfe70b4b894010ea6a377a8c7adf64db3f9752d606` |
| RDO trace | `56f12bb400649ea148f2bae06cbf63ea4eb31f915c34dd60fdef2dd761cca7fd` |

Host-dependent timing was recorded but excluded from the parity decision. GCP
reported 0.548 seconds encode wall time, 0.684 seconds trace wall time, and
0.542 seconds HM CPU time.

Machine-code binary hashes are not parity criteria. The source revision, HM
patch, preset, compiler major version, input, output bitstream, reconstruction,
trace, and coding metrics provide the relevant reproducibility evidence.

## Lifecycle And Cost

Two setup attempts stopped before encoding: the first exposed a repository-root
path error, and the second reached SSH before the restarted guest was ready.
Both failures invoked the shutdown guard. The scripts were corrected to use the
repository's actual nested path and wait up to 120 seconds for SSH. The third
attempt completed the build and encode on the same VM and disk; no additional VM
was created.

The original 55-minute preflight ceiling was USD 0.066765. The conservative
wall-clock upper bound from creation through deletion is USD 0.025719. It
deliberately overcounts stopped intervals. Actual usage cost and trial-credit
offset remain unavailable until Cloud Billing reports settle, so no measured
cost is claimed.

Cleanup completed at `2026-09-08T11:56:23Z`. Independent post-cleanup queries
returned no VM and no persistent disk in the project.

## Evidence

- Parsed comparison: `results/cloud/tiny64-all-intra-full-rdo-qp32-faed5f414b11-gcp-parity/parity.json`
- Remote result: `results/cloud/tiny64-all-intra-full-rdo-qp32-faed5f414b11-gcp-parity/baseline/result.json`
- Launch/cost record: `results/cloud/tiny64-all-intra-full-rdo-qp32-faed5f414b11-gcp-parity/launch.json`
- Raw remote logs and artifacts remain under the same ignored result directory.

The remote worktree is recorded as dirty because the cloud-backend provenance
field was transferred as an uncommitted local change on top of commit
`03c3313`. The exact transferred file and all output hashes are retained; this
does not affect coding parity, but the lifecycle scripts and provenance change
must be committed before claiming clean-checkout cloud reproduction.
