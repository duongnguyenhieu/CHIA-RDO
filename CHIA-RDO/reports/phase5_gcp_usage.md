# Phase-5 GCP Usage and Budget Gate

## Policy change

| Item | Amount | Status |
|---|---:|---|
| Approximate original Free Trial credit | USD 300 | Historical/unverified current balance |
| Previous authorized limit | USD 220 | Verified policy value |
| New authorized limit | USD 280 | Verified policy value |
| Safety reserve | USD 20 | Mandatory policy value |

The USD 280 value is an authorization ceiling, not a statement that USD 280 remains available.

## Current billing query

Google Cloud confirms that billing is enabled and the billing account is open. BigQuery is enabled, but the project contains no Billing export dataset. The Billing Budgets API is not enabled. The available Google Cloud APIs therefore did not return current spend or remaining promotional credit.

| Accounting field | Value | Status |
|---|---:|---|
| `current_verified_spend` | `null` | Unverified |
| `current_verified_remaining_credit` | `null` | Unverified |
| Actual billed spend | `null` | Unverified, not replaced by an estimate |
| Promotional/free-credit consumption | `null` | Unverified |
| Known Phase-5 incremental cloud spend | USD 0.00 | Verified from zero Phase-5 launches |
| `authorized_campaign_limit` | USD 280.00 | Verified policy value |

No remaining-credit value is inferred from the approximate USD 300 original grant or the Phase-3 cost upper bound.

## Next campaign estimate

The proposed high-information campaign targets remote CHIA graph validation, P8 timing-bottleneck refinements, selected P/D/B/W configurations, Pareto updates, and one intentional reproducibility rerun. It does not blindly repeat the 72-point local Cartesian screen.

| Field | Proposal |
|---|---|
| Experiment ID | `phase5-chia-pareto-refinement` |
| Workers | 4 short-lived `e2-standard-8` CPU workers |
| GPUs | None |
| Maximum runtime | 90 minutes per worker |
| Checkpoint/result path | `results/cloud/phase5-chia-pareto-refinement` |
| VM price assumption | USD 0.268048/hour per worker |
| Disk assumption | 15 GB `pd-standard` per worker |
| IPv4 assumption | USD 0.005/hour per worker |
| `estimated_campaign_cost` | USD 1.643220 |
| Estimate status | Estimated, not actual billed spend |
| Budget mode | Unverified/fail-closed |
| Launch allowed | No |

The estimate is recorded in `results/cloud/phase5-chia-pareto-refinement/preflight.json` with the required verified, estimated, promotional-credit, and unconfirmed-billing fields.

## Resource state

- Global CPU quota: 32, usage 0 at query time.
- In-use address quota: 8, usage 0 at query time.
- Current instances: 0.
- Current persistent disks: 0.
- Current reserved addresses: 0.
- Phase-5 workers launched by this update: 0.

The campaign was not launched because both verified billing fields are unavailable. This is required by the fail-closed budget policy and prevents unexpected paid overage.
