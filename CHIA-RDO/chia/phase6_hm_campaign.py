#!/usr/bin/env python3
"""Run matched Phase-6 HM policy curves through native CHIA nodes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chia.base.ChiaFunction import ChiaFunction, get


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from software.analysis import bd_rate  # noqa: E402

RESULT_DIR = ROOT / "results/phase6/hm_experiments"
PHASE4_DB = ROOT / "results/phase4/database.json"
CONFIG_DIR = ROOT / "results/phase4/configs"
QPS = (22, 27, 32, 37)
P_VALUES = (1, 2, 4, 8)

POLICIES: dict[str, dict[str, Any]] = {
    "adaptive_hw_v1_baseline": {
        "policy_version": "adaptive-hw-v1.analytical-cost.v1",
        "arguments": [],
        "hypothesis": "Measure whether the existing hardware-aware baseline changes with P.",
    },
    "phase6_hw_quality_v1": {
        "policy_version": "phase6-hw-quality.v1",
        "arguments": ["--cycle-weight", "0.15", "--waste-weight", "0.05"],
        "hypothesis": "Lower cycle pressure may recover quality at acceptable RTL cost.",
    },
    "phase6_hw_cycle_v1": {
        "policy_version": "phase6-hw-cycle.v1",
        "arguments": ["--cycle-weight", "0.45", "--waste-weight", "0.05"],
        "hypothesis": "Higher cycle pressure may reduce K without violating quality constraints.",
    },
    "phase6_hw_batch_v1": {
        "policy_version": "phase6-hw-batch.v1",
        "arguments": ["--cycle-weight", "0.30", "--waste-weight", "0.20"],
        "hypothesis": "A stronger lane-waste penalty may favor efficient batch boundaries.",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def experiment_id(policy_id: str, p: int, replicate: str | None = None) -> str:
    values = {"policy_id": policy_id, "p": p}
    if replicate:
        values["replicate"] = replicate
    identity = json.dumps(values, sort_keys=True, separators=(",", ":"))
    return f"phase6-b-hm-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def load_history() -> list[dict[str, Any]]:
    if not RESULT_DIR.exists():
        return []
    return [json.loads(path.read_text()) for path in sorted(RESULT_DIR.glob("*.json"))]


def result_id_from_output(output: str) -> str:
    first = next((line.strip() for line in output.splitlines() if line.strip()), "")
    if first.startswith("cache hit: "):
        return first.split(": ", 1)[1]
    path = Path(first)
    if path.name == "result.json":
        return path.parent.name
    raise RuntimeError(f"could not identify HM result from output: {first!r}")


@ChiaFunction(num_cpus=0)
def proposal_agent(history: list[dict[str, Any]], policy_ids: list[str], p_values: list[int], run_id: str,
                   replicate: str | None) -> dict:
    completed = {row["experiment_id"] for row in history if row.get("result_status") == "PASS"}
    feasible = [row for row in history if row.get("result_status") == "PASS"]
    parent = min(feasible, key=lambda row: row["bd_rate_percent"])["experiment_id"] if feasible else None
    proposals = []
    for policy_id in policy_ids:
        definition = POLICIES[policy_id]
        for p in p_values:
            identifier = experiment_id(policy_id, p, replicate)
            if identifier in completed:
                continue
            proposals.append({
                "experiment_id": identifier,
                "parent_experiment_id": parent,
                "chia_run_id": run_id,
                "track": "B",
                "policy_id": policy_id,
                "policy_version": definition["policy_version"],
                "p": p,
                "arguments": definition["arguments"],
                "hypothesis": definition["hypothesis"],
                "replicate": replicate,
            })
    return {"history_count_consumed": len(history), "proposals": proposals,
            "agent": "history-aware-matched-hm-curve.v1"}


@ChiaFunction(num_cpus=1, max_retries=1)
def run_hm_curve(proposal: dict[str, Any], timeout_seconds: int) -> dict:
    corpus = json.loads((ROOT / "configs/phase4_heldout_corpus.json").read_text())
    records = []
    commands = []
    started = time.monotonic()
    try:
        for workload in corpus["workloads"]:
            for qp in QPS:
                config = CONFIG_DIR / f"{workload['name']}-qp{qp}.json"
                command = [sys.executable, "software/run_policy.py", "--config", str(config),
                           "--policy", "adaptive_hw_v1", "--p", str(proposal["p"]), *proposal["arguments"]]
                if proposal.get("replicate"):
                    command.extend(["--replicate", proposal["replicate"]])
                commands.append(command)
                process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                                         timeout=timeout_seconds, check=False)
                if process.returncode:
                    raise RuntimeError(f"HM command failed ({process.returncode}): {' '.join(command)}\n{process.stderr[-2000:]}")
                identifier = result_id_from_output(process.stdout)
                records.append(json.loads((ROOT / "results/policy" / identifier / "result.json").read_text()))
    except Exception as error:
        return {"status": "FAILED", "proposal": proposal, "records": records, "commands": commands,
                "elapsed_seconds": time.monotonic() - started, "error": str(error)}
    return {"status": "PASS", "proposal": proposal, "records": records, "commands": commands,
            "elapsed_seconds": time.monotonic() - started, "error": None}


@ChiaFunction(num_cpus=0)
def aggregate_curve(execution: dict[str, Any]) -> dict[str, Any]:
    proposal = execution["proposal"]
    common = {
        "schema_version": "chia-rdo.phase6-hm-curve.v1", **proposal,
        "workload": "phase4-heldout-matched", "qp": list(QPS),
        "execution_backend": "local", "elapsed_seconds": execution["elapsed_seconds"],
        "timestamp": utc_now(), "commands": execution["commands"],
    }
    if execution["status"] != "PASS":
        return {**common, "result_status": "FAILED", "software_metrics_status": "FAILED",
                "rtl_metrics_status": "UNAVAILABLE", "error": execution["error"],
                "hm_run_count": len(execution["records"])}

    records = execution["records"]
    phase4 = json.loads(PHASE4_DB.read_text())
    by_workload: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_workload.setdefault(record["sequence"]["name"], []).append(record)
    workload_bd = {}
    for workload, curve in by_workload.items():
        curve.sort(key=lambda row: row["configuration"]["qp"])
        reference = sorted((row for row in phase4["records"]
                            if row["workload"] == workload and row["policy"] == "full_rdo"),
                           key=lambda row: row["qp"])
        if [row["configuration"]["qp"] for row in curve] != list(QPS) or len(reference) != 4:
            raise RuntimeError(f"incomplete matched curve for {workload}")
        workload_bd[workload] = bd_rate(
            [(row["bitrate"], row["psnr"]["y"]) for row in reference],
            [(row["metrics"]["annex_b_kbps"], row["metrics"]["psnr_y_db"]) for row in curve],
        )
    metrics = [row["metrics"] for row in records]
    searches = sum(row["search_calls"] for row in metrics)
    histogram = {str(k): sum(row["k_histogram"][str(k)] for row in metrics) for k in (2, 4, 8, 16, 35)}
    points = [{"workload": row["sequence"]["name"], "qp": row["configuration"]["qp"],
               "bitrate": row["metrics"]["annex_b_kbps"],
               "psnr": {key: row["metrics"][f"psnr_{key}_db"] for key in ("y", "u", "v", "yuv")}}
              for row in records]
    workload_metrics = {}
    for workload, curve in by_workload.items():
        workload_rows = [row["metrics"] for row in curve]
        workload_searches = sum(row["search_calls"] for row in workload_rows)
        workload_matched = sum(row["matched_events"] for row in workload_rows)
        workload_metrics[workload] = {
            "average_k": sum(row["average_k"] * row["search_calls"] for row in workload_rows) / workload_searches,
            "rdo_reduction": sum(row["rdo_reduction_fraction"] * row["search_calls"] for row in workload_rows) / workload_searches,
            "winner_retention": sum(row["winner_retained_events"] for row in workload_rows) / workload_matched,
        }
    aggregate_bd_rate = sum(workload_bd.values()) / len(workload_bd)
    average_k = sum(row["average_k"] for row in workload_metrics.values()) / len(workload_metrics)
    winner_retention = sum(row["winner_retention"] for row in workload_metrics.values()) / len(workload_metrics)
    rdo_reduction = sum(row["rdo_reduction"] for row in workload_metrics.values()) / len(workload_metrics)
    quality_constraints = {
        "aggregate_bd_rate_max_percent": 1.5,
        "aggregate_winner_retention_min": 0.85,
        "positive_rdo_reduction_required": True,
        "pass": aggregate_bd_rate <= 1.5 and winner_retention >= 0.85 and rdo_reduction > 0,
    }
    return {
        **common, "result_status": "PASS", "software_metrics_status": "VERIFIED_HM16.20",
        "rtl_metrics_status": "UNAVAILABLE", "hm_run_count": len(records),
        "average_k": average_k,
        "k_distribution": histogram, "rdo_evaluations": sum(row["rdo_evaluations"] for row in metrics),
        "rdo_reduction": rdo_reduction,
        "winner_retention": winner_retention, "candidate_recall": winner_retention,
        "bd_rate_percent": aggregate_bd_rate, "quality_constraints": quality_constraints,
        "feasible": quality_constraints["pass"],
        "bd_rate_by_workload_percent": workload_bd, "software_metrics_by_workload": workload_metrics,
        "bitrate_psnr_points": points,
        "source_experiment_ids": [row["experiment_id"] for row in records], "error": None,
    }


@ChiaFunction(num_cpus=0)
def persist_curve(result: dict[str, Any]) -> dict[str, Any]:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULT_DIR / f"{result['experiment_id']}.json"
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", action="append", choices=tuple(POLICIES), dest="policies")
    parser.add_argument("--p", action="append", type=int, choices=P_VALUES, dest="p_values")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--refresh-aggregates", action="store_true")
    parser.add_argument("--replicate")
    args = parser.parse_args()
    run_id = f"phase6-hm-local-{uuid.uuid4().hex[:12]}"
    history = load_history()
    if args.refresh_aggregates:
        refreshes = []
        for row in history:
            if row.get("result_status") != "PASS" or not row.get("source_experiment_ids"):
                continue
            proposal = {key: row.get(key) for key in ("experiment_id", "parent_experiment_id", "chia_run_id",
                                                       "track", "policy_id", "policy_version", "p", "arguments",
                                                       "hypothesis", "replicate")}
            execution = {"status": "PASS", "proposal": proposal,
                         "records": [json.loads((ROOT / "results/policy" / identifier / "result.json").read_text())
                                     for identifier in row["source_experiment_ids"]],
                         "commands": row["commands"], "elapsed_seconds": row["elapsed_seconds"], "error": None}
            refreshes.append(persist_curve.chia_remote(aggregate_curve.chia_remote(execution)))
        if refreshes:
            get(refreshes)
            history = load_history()
    batch = get(proposal_agent.chia_remote(history, args.policies or ["adaptive_hw_v1_baseline"],
                                           args.p_values or list(P_VALUES), run_id, args.replicate))
    executions = [run_hm_curve.chia_remote(proposal, args.timeout_seconds) for proposal in batch["proposals"]]
    outputs = [persist_curve.chia_remote(aggregate_curve.chia_remote(execution)) for execution in executions]
    results = get(outputs) if outputs else []
    summary = {
        "schema_version": "chia-rdo.phase6-hm-campaign.v1", "chia_run_id": run_id,
        "history_count_consumed": batch["history_count_consumed"],
        "completed_new_experiments": len(results),
        "passed": sum(row["result_status"] == "PASS" for row in results),
        "failed": sum(row["result_status"] == "FAILED" for row in results),
        "experiment_ids": [row["experiment_id"] for row in results],
        "status": "PASS" if all(row["result_status"] == "PASS" for row in results) else "FAILED",
        "created_utc": utc_now(),
    }
    output = ROOT / "results/phase6/hm_campaign_latest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
