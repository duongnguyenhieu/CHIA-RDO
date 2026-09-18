# Phase-7B GCP Usage

Phase-7B Verilator regressions ran on short-lived `e2-standard-8` workers in project `project-1bfffc90-767b-48e2-ac1`, zone `us-central1-a`. At most three workers ran concurrently under the regional E2 CPU quota of 24.

| Accounting field | Value | Status |
|---|---:|---|
| Verified billed spend | `null` | UNKNOWN |
| Verified remaining promotional credit | `null` | UNKNOWN |
| Regional E2 CPU quota | 24 | Verified |
| Current regional E2 CPU use | 0 | Verified at 2026-09-13T06:46:35Z |
| Current instances | 0 | Verified at 2026-09-13T06:46:35Z |
| Current persistent disks | 0 | Verified at 2026-09-13T06:46:35Z |
| Current reserved addresses | 0 | Verified at 2026-09-13T06:46:35Z |

Actual billed spend and promotional-credit consumption are not inferred from VM list state, runtime estimates, or historical credit values. The cleanup state was verified directly with Compute Engine list and quota APIs after regression.

Evidence: `results/phase7b/gcp_usage.json`, the Phase-7B RTL gate JSON files, and `cloud/startup_shutdown.sh`.
