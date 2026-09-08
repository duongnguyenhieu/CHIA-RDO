# GCP Cost Policy

The total promotional credit is USD 300. CHIA-RDO may target USD 150-220 for
useful experiments, while preserving at least USD 80 as a safety margin.

## Hard Controls

- No VM launch without a deterministic experiment ID and a preflight estimate.
- Refuse launches when projected cumulative cost exceeds USD 220.
- Begin with at most two Spot CPU workers; no GPU workers by default.
- Set a maximum VM lifetime of 6 hours for screening and 12 hours for promoted runs.
- Wrap every remote experiment in a timeout shorter than VM lifetime.
- Label resources with project, experiment ID, owner purpose, and expiry time.
- Shut down after completion or failure; cleanup must be idempotent.
- Checkpoint outputs to durable storage before a Spot worker reports completion.
- Reuse successful experiment IDs from cache and never rerun identical work.
- Keep Vivado local unless a remote worker with an explicit valid license exists.

## Required Launch Record

Each launch must record the experiment ID, machine type, Spot status, start time,
estimated runtime, hourly price assumption, expected cost, cumulative projected
cost, output directory, and cleanup deadline. Actual elapsed time and estimated
actual cost are appended on termination.

## Cost Formula

```text
expected_cost_usd = hourly_vm_cost_usd * runtime_hours * instance_count
```

Disk, network egress, image storage, and durable result storage estimates must be
added separately when non-negligible. Price assumptions are configuration data,
not constants hidden in scripts, because GCP prices vary by region and date.

## Stop Conditions

Stop launching new jobs if projected spend exceeds USD 220, current spend cannot
be established, cleanup fails, results cannot be checkpointed, a proposed sweep
contains duplicate experiment IDs, or worker count/runtime exceeds policy.

Phase 0 and the initial local Phase 1 use no GCP resources and cost USD 0.
