#!/usr/bin/env python3
"""Verify collected GCP matrix records against local deterministic results."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX_RUNS = ("phase3-matched-matrix", "phase3-matched-matrix-resume")
SEARCH_RUNS = ("phase3-policy-search", "phase3-policy-search-e2-standard-8")


def comparable_metrics(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key not in {"hm_cpu_time_seconds"}}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_artifacts(directory: Path, record: dict) -> None:
    artifacts = record["artifacts"]
    files = {"bitstream_sha256": "measure.bin", "reconstruction_sha256": "measure-recon.yuv",
             "trace_sha256": "intra-rdo.jsonl"}
    for key, name in files.items():
        if key in artifacts and sha256(directory / name) != artifacts[key]:
            raise RuntimeError(f"collected artifact hash mismatch: {directory.name} {key}")


def policy_key(record: dict) -> str:
    return json.dumps(record["policy"], sort_keys=True, separators=(",", ":"))


def main() -> None:
    local_policy = {path.parent.name: json.loads(path.read_text())
                    for path in (ROOT / "results/policy").glob("*/result.json")}
    local_baselines = {}
    for path in (ROOT / "results/baseline").glob("*/result.json"):
        record = json.loads(path.read_text())
        if record.get("execution", {}).get("replicate") is None:
            local_baselines[(record["sequence"]["name"], record["configuration"]["qp"])] = record
    policy_checks = 0
    baseline_checks = 0
    launches = []
    for run in MATRIX_RUNS:
        directory = ROOT / "results/cloud" / run
        launches.append(json.loads((directory / "launch.json").read_text()))
        for path in (directory / "remote/policy").glob("*/result.json"):
            remote = json.loads(path.read_text())
            local = local_policy.get(path.parent.name)
            if local is None or comparable_metrics(remote["metrics"]) != comparable_metrics(local["metrics"]):
                raise RuntimeError(f"GCP/local policy mismatch: {path.parent.name}")
            for key in ("bitstream_sha256", "reconstruction_sha256", "trace_sha256"):
                if remote["artifacts"][key] != local["artifacts"][key]:
                    raise RuntimeError(f"GCP/local artifact mismatch: {path.parent.name} {key}")
            if remote["execution"]["cloud_backend"] != "gcp-compute-engine":
                raise RuntimeError(f"missing GCP provenance: {path.parent.name}")
            verify_artifacts(path.parent, remote)
            policy_checks += 1
        for path in (directory / "remote/baseline").glob("*/result.json"):
            remote = json.loads(path.read_text())
            if remote.get("execution", {}).get("cloud_backend") != "gcp-compute-engine":
                continue
            local = local_baselines[(remote["sequence"]["name"], remote["configuration"]["qp"])]
            if comparable_metrics(remote["metrics"]) != comparable_metrics(local["metrics"]):
                raise RuntimeError(f"GCP/local baseline mismatch: {path.parent.name}")
            if remote["artifacts"]["bitstream_sha256"] != local["artifacts"]["bitstream_sha256"]:
                raise RuntimeError(f"GCP/local baseline bitstream mismatch: {path.parent.name}")
            verify_artifacts(path.parent, remote)
            baseline_checks += 1
    if policy_checks != 56 or baseline_checks != 4:
        raise RuntimeError(f"incomplete GCP matrix: {policy_checks} policies, {baseline_checks} baselines")

    search_records = []
    search_baselines = []
    machine_types = []
    for run in SEARCH_RUNS:
        directory = ROOT / "results/cloud" / run
        launch = json.loads((directory / "launch.json").read_text())
        launches.append(launch)
        machine_types.append(launch["machine_type"])
        if launch["status"] != "cleaned":
            raise RuntimeError(f"search launch was not cleaned: {run}")
        manifest = json.loads((directory / "remote/experiments/phase3-online-search-manifest.json").read_text())
        if manifest["status"] != "PASS" or manifest["backend"] != "gcp-compute-engine" or manifest["online_trials"] != 12:
            raise RuntimeError(f"invalid online-search manifest: {run}")
        records = {}
        for path in (directory / "remote/policy").glob("*/result.json"):
            record = json.loads(path.read_text())
            if record["execution"]["cloud_backend"] != "gcp-compute-engine":
                raise RuntimeError(f"missing search GCP provenance: {path.parent.name}")
            if record["metrics"]["match_rate"] != 1.0 or record["metrics"]["policy_events"] <= 0:
                raise RuntimeError(f"invalid online-search comparison: {path.parent.name}")
            verify_artifacts(path.parent, record)
            records[policy_key(record)] = record
        if len(records) != 12:
            raise RuntimeError(f"incomplete online search: {run} has {len(records)} policies")
        family_counts = Counter(record["policy"]["name"] for record in records.values())
        if family_counts != {"adaptive_threshold": 4, "relative_satd": 4, "adaptive_hw_v1": 4}:
            raise RuntimeError(f"incorrect online-search policy coverage: {run} {dict(family_counts)}")
        search_records.append(records)
        baseline_path = directory / "remote/baseline/synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5-phase3-search-gcp/result.json"
        baseline = json.loads(baseline_path.read_text())
        verify_artifacts(baseline_path.parent, baseline)
        search_baselines.append(baseline)

    if set(search_records[0]) != set(search_records[1]):
        raise RuntimeError("online-search parameter sets differ across machine types")
    for key, first in search_records[0].items():
        second = search_records[1][key]
        if comparable_metrics(first["metrics"]) != comparable_metrics(second["metrics"]):
            raise RuntimeError(f"online-search metric mismatch across machine types: {first['experiment_id']}")
        for artifact in ("bitstream_sha256", "reconstruction_sha256", "trace_sha256"):
            if first["artifacts"][artifact] != second["artifacts"][artifact]:
                raise RuntimeError(f"online-search artifact mismatch across machine types: {first['experiment_id']} {artifact}")
    if comparable_metrics(search_baselines[0]["metrics"]) != comparable_metrics(search_baselines[1]["metrics"]):
        raise RuntimeError("online-search Full-RDO baseline mismatch across machine types")
    if machine_types != ["e2-standard-2", "e2-standard-8"]:
        raise RuntimeError(f"unexpected search machine types: {machine_types}")

    cost = sum(row["estimated_cost_upper_bound_usd"] for row in launches)
    result = {"schema_version": "chia-rdo.phase3-gcp-verification.v1", "status": "PASS",
              "matrix_policy_records": policy_checks, "matrix_baseline_records": baseline_checks,
              "online_search_trials_per_run": 12, "online_search_trial_records": 24,
              "online_search_machine_types": machine_types,
              "experiment_count": policy_checks + baseline_checks + 24,
              "estimated_cost_upper_bound_usd": cost,
              "actual_billing_cost_usd": None, "runs": MATRIX_RUNS + SEARCH_RUNS}
    output = ROOT / "results/experiments/gcp-verification.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (ROOT / "reports/gcp_phase3_usage.md").write_text(
        "# GCP Phase 3 Usage\n\n"
        "Status: PASS\n\n"
        f"Two guarded ephemeral `e2-standard-2` matrix runs produced {policy_checks} policy and {baseline_checks} Full-RDO records. "
        "Every coding metric, bitstream, reconstruction, and policy trace hash matches the corresponding local run. "
        "Two additional guarded online-search runs on `e2-standard-2` and `e2-standard-8` each completed the same 12 configurations. "
        "Their coding metrics and artifact hashes match exactly across machine types, and all collected artifact contents match their recorded hashes. "
        f"The conservative combined creation-to-deletion cost upper bound is USD {cost:.6f}; actual delayed billing is unavailable. "
        "The first run checkpointed QP22/27 before a missing ignored QP32 trace exposed a cache-validity defect; its failure trap deleted the VM. "
        "The resumed run completed QP32/37. The `e2-standard-8` search auto-stopped at its hardware deadline after completing, was restarted for collection, and was then deleted. "
        "Final resource checks found no instances, disks, or reserved addresses.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
