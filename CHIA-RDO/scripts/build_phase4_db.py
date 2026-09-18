#!/usr/bin/env python3
"""Build the isolated Phase-4 held-out experiment database and BD-rate curves."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))
from analysis import bd_rate  # noqa: E402
from policy_algorithms import HardwareState, estimate_cycles  # noqa: E402


def label(policy: dict) -> str | None:
    name = policy["name"]
    if name == "fixed" and policy["k"] in (2, 4, 8, 16):
        return f"fixed_k{policy['k']}"
    if name == "adaptive_v0" and (policy["high_k"], policy["medium_k"], policy["low_k"]) == (4, 8, 16):
        return "adaptive_v0"
    if name == "adaptive_threshold" and (
        policy["easy_threshold"], policy["hard_threshold"], policy["easy_k"], policy["medium_k"], policy["hard_k"]
    ) == (0.04, 0.2, 4, 16, 35):
        return "adaptive_threshold"
    if name == "relative_satd" and (policy["relative_threshold"], policy["minimum_k"], policy["maximum_k"]) == (0.5, 8, 35):
        return "relative_satd"
    if name == "adaptive_hw" and policy["parallelism"] == 8 and (policy["high_k"], policy["medium_k"], policy["low_k"]) == (2, 4, 8):
        return "adaptive_hw_batch_fill_p8"
    if name == "adaptive_hw_v1" and policy["hardware_state"]["parallelism"] == 8:
        return "adaptive_hw_v1_p8"
    return None


def modeled(histogram: dict[str, int], p: int) -> dict[str, float]:
    events = sum(histogram.values())
    batches = sum(count * int(estimate_cycles(int(k), HardwareState(parallelism=p))["batches"])
                  for k, count in histogram.items())
    cycles = sum(count * int(estimate_cycles(int(k), HardwareState(parallelism=p))["estimated_cycles"])
                 for k, count in histogram.items())
    return {"average_batches": batches / events, "estimated_cycles": cycles / events,
            "estimated_cycle_total": cycles}


def main() -> None:
    corpus = json.loads((ROOT / "configs/phase4_heldout_corpus.json").read_text())
    workload_names = {row["name"] for row in corpus["workloads"]}
    records = []
    references = {}
    for path in (ROOT / "results/baseline").glob("*/result.json"):
        source = json.loads(path.read_text())
        if source.get("sequence", {}).get("name") not in workload_names or source.get("configuration", {}).get("evaluation_split") != corpus["split"]:
            continue
        references[(source["sequence"]["name"], source["configuration"]["qp"])] = source
    for (workload, qp), source in references.items():
        metrics = source["metrics"]
        histogram = {"35": metrics["search_calls"]}
        records.append({"experiment_id": source["experiment_id"], "source_record": str((ROOT / "results/baseline" / source["experiment_id"] / "result.json").relative_to(ROOT)),
                        "workload": workload, "qp": qp, "policy": "full_rdo", "policy_version": "full-rdo.hm16.20",
                        "parameters": {}, "avg_k": 35.0, "rdo_evaluations": metrics["rdo_evaluations"], "rdo_reduction": 0.0,
                        "winner_retention": 1.0, "candidate_recall": 1.0, "bitrate": metrics["annex_b_kbps"],
                        "psnr": {key: metrics[f"psnr_{key}_db"] for key in ("y", "u", "v", "yuv")},
                        "estimated_by_p": {str(p): modeled(histogram, p) for p in (1, 2, 4, 8)},
                        "measurement_type": "software_measured_with_analytical_hardware_estimate", "status": "PASS"})
    for path in (ROOT / "results/policy").glob("*/result.json"):
        source = json.loads(path.read_text())
        if source.get("sequence", {}).get("name") not in workload_names or source.get("configuration", {}).get("evaluation_split") != corpus["split"]:
            continue
        policy_name = label(source["policy"])
        if policy_name is None:
            continue
        metrics = source["metrics"]
        estimates = {str(p): modeled(metrics["k_histogram"], p) for p in (1, 2, 4, 8)}
        records.append({"experiment_id": source["experiment_id"], "source_record": str(path.relative_to(ROOT)),
                        "workload": source["sequence"]["name"], "qp": source["configuration"]["qp"],
                        "policy": policy_name, "policy_version": source["policy"]["version"],
                        "parameters": {key: value for key, value in source["policy"].items() if key not in {"name", "version"}},
                        "avg_k": metrics["average_k"], "rdo_evaluations": metrics["rdo_evaluations"],
                        "rdo_reduction": metrics["rdo_reduction_fraction"], "winner_retention": metrics["winner_retention_rate"],
                        "candidate_recall": metrics["winner_retention_rate"], "bitrate": metrics["annex_b_kbps"],
                        "bitrate_delta_percent": metrics["bitrate_delta_percent"],
                        "psnr": {key: metrics[f"psnr_{key}_db"] for key in ("y", "u", "v", "yuv")},
                        "estimated_by_p": estimates, "measurement_type": "software_measured_with_analytical_hardware_estimate",
                        "status": "PASS"})
    groups = defaultdict(list)
    for record in records:
        groups[(record["workload"], record["policy"])].append(record)
    bd_by_workload = {}
    for (workload, policy), rows in groups.items():
        if len(rows) != 4:
            raise RuntimeError(f"incomplete Phase-4 curve: {workload} {policy} has {len(rows)} points")
        if policy == "full_rdo":
            bd_by_workload[f"{workload}:{policy}"] = 0.0
            continue
        reference = sorted(groups[(workload, "full_rdo")], key=lambda row: row["qp"])
        curve = sorted(rows, key=lambda row: row["qp"])
        bd_by_workload[f"{workload}:{policy}"] = bd_rate(
            [(row["bitrate"], row["psnr"]["y"]) for row in reference],
            [(row["bitrate"], row["psnr"]["y"]) for row in curve],
        )
    policy_values = defaultdict(list)
    for key, value in bd_by_workload.items():
        policy_values[key.rsplit(":", 1)[1]].append(value)
    aggregate_bd = {policy: sum(values) / len(values) for policy, values in policy_values.items()}
    for record in records:
        record["bd_rate_percent"] = bd_by_workload[f"{record['workload']}:{record['policy']}"]
        record["estimated_batches"] = record["estimated_by_p"]["8"]["average_batches"]
        record["estimated_cycles"] = record["estimated_by_p"]["8"]["estimated_cycles"]
    records.sort(key=lambda row: (row["workload"], row["qp"], row["policy"]))
    payload = {"schema_version": "chia-rdo.phase4-database.v1", "split": corpus["split"],
               "bd_rate_definition": "cubic log(rate) versus Y-PSNR over matched QP 22/27/32/37",
               "records": records, "bd_rate_by_workload_percent": bd_by_workload,
               "policy_bd_rate_percent": aggregate_bd}
    output = ROOT / "results/phase4/database.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    fields = ("experiment_id", "workload", "qp", "policy", "avg_k", "rdo_reduction", "winner_retention",
              "candidate_recall", "bitrate", "psnr_y", "psnr_u", "psnr_v", "psnr_yuv", "bd_rate_percent",
              "estimated_batches", "estimated_cycles", "status")
    with (output.parent / "database.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({**{field: row.get(field) for field in fields},
                             **{f"psnr_{key}": row["psnr"][key] for key in ("y", "u", "v", "yuv")}})
    print(json.dumps({"records": len(records), "curves": len(bd_by_workload),
                      "policy_bd_rate_percent": aggregate_bd}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
