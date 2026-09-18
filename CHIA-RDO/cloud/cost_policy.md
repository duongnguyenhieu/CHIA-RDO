# GCP Cost Policy

The Google Cloud Free Trial credit was approximately USD 300. This is historical context, not a current balance. The previous CHIA-RDO authorization ceiling was USD 220. The Phase-5/Phase-6 ceiling is USD 280, with at least USD 20 reserved for emergencies.

## Authorization

- Previous authorized limit: USD 220.
- New absolute authorized limit: USD 280.
- Minimum safety reserve: USD 20.
- Never infer remaining credit by subtracting estimates from the approximate USD 300 grant.
- Never intentionally consume the safety reserve, exceed verified promotional credit, enable paid overage, or create an expected out-of-pocket charge.
- A higher ceiling authorizes an affordable campaign; it does not assert that USD 280 remains available.

## Mandatory Preflight

Before every launch:

1. Query Cloud Billing and any configured Billing export for current billed spend and remaining promotional credit.
2. Mark each value `verified`, `estimated`, `delayed`, or `unverified` according to its source.
3. Compute a conservative campaign estimate before creating resources.
4. Limit affordable cost to the smaller of verified promotional credit minus USD 20 and USD 280 minus verified cumulative spend.
5. Select only the affordable high-information subset and reject duplicate or already-dominated configurations.
6. Record the preflight metadata, launch short-lived workers, checkpoint results, and clean up on success or failure.

The launch gate fails closed when either `current_verified_spend` or `current_verified_remaining_credit` is unavailable. Delayed billing and list-price estimates are not verified charges.

## Budget Modes

| Verified remaining credit | Mode | Maximum pool | Allowed work |
|---:|---|---:|---|
| USD 100 or more | standard | 8 workers | Prioritized DSE and reproducibility |
| Below USD 100 | reduced | 4 workers | Reduced prioritized search |
| Below USD 60 | cautious | 2 workers | High-information experiments only |
| Below USD 30 | strict | 1 worker | No broad sweeps |
| Below USD 20 | stop | 0 workers | No new cloud compute |

Worker limits are additional guards, not targets. CPU quota, verified affordable cost, and useful non-duplicated work may reduce them further. GPUs are prohibited unless a later experiment demonstrates a concrete need and receives separate authorization.

## Productive Use

Prioritize parallel CHIA DSE, Verilator regression, P/D/B/W architecture sweeps, Pareto refinement, and intentional reproducibility reruns. Do not pay for idle VMs, duplicate experiments, dominated points, unnecessary GPUs, or rebuilds available from cache.

## Required Metadata

Every campaign record must include:

- `current_verified_spend`
- `current_verified_remaining_credit`
- `estimated_campaign_cost`
- `authorized_campaign_limit`
- actual billed spend status and value
- estimated spend status and value
- promotional/free-credit consumption status and value
- unconfirmed or delayed billing status
- worker count/type, expected runtime, cleanup deadline, checkpoint location, and price assumptions

## Runtime Controls

- Use deterministic experiment IDs and CHIA resource-aware prioritization.
- Use short-lived cost-efficient CPU workers with hard timeouts and automatic shutdown.
- Upload or collect checkpoints before deletion.
- Make cleanup idempotent and verify zero instances, disks, and reserved addresses after the campaign.
- Keep Vivado local unless a remote worker has an explicitly verified installation and license.
- Stop immediately if billing verification is lost, cleanup fails, results cannot be checkpointed, or the campaign would violate its active budget mode.
