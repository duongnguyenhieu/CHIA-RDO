# GCP Parity Preflight

Inspection date: 2026-09-08

Status: preflight passed and the authorized parity run completed on 2026-09-08.

## Target

- Project: `project-1bfffc90-767b-48e2-ac1`
- Zone: `us-central1-a`
- Machine: one on-demand `e2-standard-2`
- Image: Ubuntu 24.04 LTS x86-64
- Boot disk: 15 GB `pd-standard`, deleted with the VM
- Maximum lifetime: 55 minutes, enforced by the startup script
- Experiment: `tiny64-all-intra-full-rdo-qp32-faed5f414b11-gcp-parity`

Spot execution is not selected because `PREEMPTIBLE_CPUS` has limit 0 in
`us-central1`, `us-east1`, and `us-west1`. Each region has at least 24 unused E2
CPUs, 24 unused instance slots, 8 unused in-use address slots, and 4096 GB of
unused persistent-disk quota. The selected VM needs 2 E2 CPUs and one address.

## Cost Ceiling

The conservative public list-price assumptions checked on 2026-09-08 are:

| Resource | USD/hour |
|---|---:|
| `e2-standard-2` VM | 0.067012 |
| 15 GB standard persistent disk | 0.000822 |
| External IPv4 | 0.005000 |
| Total | 0.072834 |

At the 55-minute lifetime limit, the projected maximum is USD 0.066765. This
is below the USD 220 hard stop even without promotional-credit discounts.

Cloud Billing does not expose a reliable current-spend value through the
available `gcloud billing` commands, and no billing export is configured.
`cloud/bootstrap_vm.sh` therefore requires an operator-confirmed
`--current-spend-usd` value and refuses to proceed without one. The run was
authorized with the pre-resource project spend recorded as USD 0. Taxes and
delayed/unrelated charges remain limitations.

## Controls Verified

- All lifecycle scripts pass `bash -n`.
- A no-resource dry run succeeds with an explicitly supplied test spend.
- The estimator rejects a projection above USD 220.
- Cleanup is idempotent and currently reports no CHIA-RDO VM or boot disk.
- The remote encode has a 20-minute timeout.
- VM labels include project, experiment purpose, and cleanup expiry.
- The VM has no service account or API scopes.
- Unit tests pass: 5 of 5 via `python3 -m unittest discover -s tests -v`.

`pytest` and `shellcheck` are not installed in the active environment, so those
two optional command paths were unavailable. Dependency-free unit tests and
the shell parser were used instead.
