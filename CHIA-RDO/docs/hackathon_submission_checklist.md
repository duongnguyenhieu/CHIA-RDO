# A3 CHIA Hackathon Final Submission Checklist

Source checked: <https://agentic-arch.org/hackathon.html#final-submission> on 2026-09-13.

## Published Requirements

| Requirement | Published detail | CHIA-RDO status |
|---|---|---|
| Deadline | September 24, 2026, Anywhere on Earth | Pending submission |
| Write-up | Four-page paper describing the loop and findings | LaTeX source in `docs/paper.tex` |
| Future publication | Hackathon paper does not preclude later conference/workshop publication | Noted |
| Artifact | Open-source the CHIA loop and its produced results | Code/results exist locally; public release URL pending |
| Reusability | Strong loops may be upstreamed as composable mainline CHIA blocks | Artifact map drafted in `HACKATHON_ARTIFACT.md` |
| Registration | No prior proposal/registration required if funding is not needed | Confirm team funding path |
| Eligibility | UC Berkeley affiliates are not eligible | Team must confirm |

The organizers state that detailed final-submission instructions will be available later. The final upload form, paper template, anonymity policy, file-size limit, supplemental-material rules, and required licenses are therefore not yet specified on the page.

## Required Human Inputs

- [x] Replace `[AUTHOR ...]` with all author names, affiliations, and contact email.
- [x] Confirm that no team member is a UC Berkeley affiliate.
- [ ] Confirm whether the team received hackathon credits and whether any credit acknowledgement is required.
- [x] Add the public repository URL and versioned release tag.
- [ ] Replace the Chung/Yim reference placeholder with exact title, venue, year, and DOI; the Gwon-Choi citation was recovered from the local PDF.
- [x] Confirm the artifact license and third-party HM redistribution boundaries.
- [ ] Add acknowledgements for Google, NVIDIA, IEEE Computer Society TCMM, or other support when applicable.
- [ ] Check the final instructions page again before submission.

## Paper Completion

- [x] State the architecture problem and cross-layer motivation.
- [x] Explain the prior-art basis and evolution from Adaptive-K v0 and relative SATD to the frozen adaptive-threshold policy.
- [x] Describe the CHIA loop and history-aware proposal behavior.
- [x] Separate the frozen software policy from later Track-B policies.
- [x] Report coding, RTL, Vivado, Pareto, cache, and GCP evidence.
- [x] Distinguish measured, modeled, and unavailable values.
- [x] State corpus, RTL, timing, and billing limitations.
- [ ] Move the manuscript into the official template when published.
- [ ] Keep the main content within four pages; place references only as allowed by the final rules.
- [ ] Add one compact loop diagram and one Pareto/physical-feedback figure if space permits.
- [ ] Verify every number against the immutable release artifact.
- [ ] Export and visually inspect the final PDF.

## Artifact Completion

- [x] Identify the CHIA graphs and proposal controller.
- [x] Identify RTL, regression, parser, result, and report paths.
- [x] Provide analytical replay and result-validation commands.
- [ ] Commit or deliberately exclude all dirty worktree changes before release.
- [ ] Capture a clean release commit in every final result manifest.
- [ ] Resolve or disclose that pre-tree Vivado builds lack exact pre-edit source hashes.
- [ ] Resolve stale status documents, especially the Phase-6 blocked gate and pending Phase-7B smoke manifest.
- [ ] Reconcile Phase-7/7B cloud launches with the repository's fail-closed billing policy.
- [ ] Add a clean-environment quick-start test for the public artifact.
- [ ] Verify that no credentials, local absolute paths, or private cloud identifiers are released unintentionally.
- [ ] Create a versioned release archive and optionally a DOI.

## Claim-Safety Review

- [x] Say `candidate-kernel throughput proxy`, not encoder FPS.
- [x] Say `derived Fmax from post-route timing`, not achieved board frequency.
- [x] State that the 5 ns timing constraint is not met.
- [x] State that 31-bit safety is observed-corpus evidence, not a formal proof.
- [x] State that workloads are deterministic synthetic All-Intra fixtures.
- [x] State that the deterministic controller is history-aware; do not claim autonomous LLM RTL design.
- [x] State that 832 candidates are analytical evaluations, not 832 routed implementations.
- [x] Treat -0.026% aggregate BD-rate as no observed penalty, not a proven quality improvement.
- [x] Keep billed GCP spend and remaining credit as unknown.

## Suggested Submission Package

```text
paper.pdf
artifact-url.txt
release-commit.txt
```

Only include additional archives or supplemental files if the forthcoming detailed instructions explicitly permit them.
