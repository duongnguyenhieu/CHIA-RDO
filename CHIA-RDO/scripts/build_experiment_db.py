#!/usr/bin/env python3
"""Normalize measured Phase 3 records and derive matched curves/model fields."""

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


def matrix_label(policy: dict) -> str | None:
    name = policy["name"]
    if name == "fixed" and policy.get("k") in (8, 16):
        return f"fixed_k{policy['k']}"
    if name == "adaptive_v0":
        levels = (policy["high_k"], policy["medium_k"], policy["low_k"])
        return "adaptive_v0" if levels == (4, 8, 16) else "adaptive_v0_aggressive" if levels == (2, 4, 8) else None
    if name == "adaptive_threshold" and (policy["easy_threshold"], policy["hard_threshold"], policy["easy_k"], policy["medium_k"], policy["hard_k"]) == (0.04, 0.2, 4, 16, 35):
        return "adaptive_threshold"
    if name == "relative_satd" and (policy["relative_threshold"], policy["minimum_k"], policy["maximum_k"]) == (0.5, 8, 35):
        return "relative_satd"
    if name == "adaptive_hw" and (policy["high_k"], policy["medium_k"], policy["low_k"]) == (2, 4, 8):
        return f"adaptive_hw_batch_fill_p{policy['parallelism']}"
    if name == "adaptive_hw_v1" and policy["weights"]["quality_weight"] == 1.0 and policy["weights"]["cycle_weight"] == 0.3:
        return f"adaptive_hw_v1_p{policy['hardware_state']['parallelism']}"
    return None


def modeled(metrics: dict, p: int) -> dict:
    histogram = metrics.get("k_histogram", {"35": metrics["search_calls"]})
    events = sum(histogram.values())
    total_cycles = sum(count * int(estimate_cycles(int(k), HardwareState(parallelism=p))["estimated_cycles"])
                       for k, count in histogram.items())
    total_batches = sum(count * ((int(k) + p - 1) // p) for k, count in histogram.items())
    slots = sum(count * ((int(k) + p - 1) // p) * p for k, count in histogram.items())
    return {"P": p, "average_batches": total_batches / events, "estimated_cycles": total_cycles / events,
            "total_estimated_cycles": total_cycles, "estimated_throughput_events_per_cycle": events / total_cycles,
            "hardware_utilization_proxy": sum(int(k) * count for k, count in histogram.items()) / slots}


def main() -> None:
    records = []
    baseline_by_workload_qp = {}
    for path in (ROOT / "results/baseline").glob("*/result.json"):
        source = json.loads(path.read_text())
        qp = source.get("configuration", {}).get("qp")
        if qp in (22, 27, 32, 37) and source.get("execution", {}).get("replicate") is None:
            baseline_by_workload_qp[(source["sequence"]["name"], qp)] = source
    for (workload, qp), source in baseline_by_workload_qp.items():
        metrics = source["metrics"]
        estimates = {str(p): modeled(metrics, p) for p in (1, 2, 4, 8)}
        records.append({"experiment_id": source["experiment_id"], "source_record": str((ROOT / "results/baseline" / source["experiment_id"] / "result.json").relative_to(ROOT)),
                        "policy": "full_rdo", "workload": workload, "policy_version": "full-rdo.hm16.20", "parameters": {},
                        "hm_commit": source["encoder"]["revision"], "input": source["sequence"], "qp": qp,
                        "cu_size": "HM-default-max-CU-64", "P": 4, "avg_k": metrics["average_k"],
                        "rdo_evaluations": metrics["rdo_evaluations"], "rdo_reduction": 0.0,
                        "winner_retention": 1.0, "candidate_recall": 1.0, "bitrate": metrics["annex_b_kbps"],
                        "psnr": {key: metrics[f"psnr_{key}_db"] for key in ("y", "u", "v", "yuv")},
                        "estimated_batches": estimates["4"]["average_batches"], "estimated_cycles": estimates["4"]["estimated_cycles"],
                        "estimated_by_p": estimates, "measurement_type": "software_measured_with_analytical_hardware_estimate",
                        "in_matched_matrix": True, "status": "PASS"})
    for path in (ROOT / "results/policy").glob("*/result.json"):
        source = json.loads(path.read_text())
        qp = source.get("configuration", {}).get("qp")
        label = matrix_label(source.get("policy", {}))
        if (qp not in (22, 27, 32, 37) or label is None
                or "phase3_algorithms" not in source.get("identity", {}).get("patch_sha256", {})):
            continue
        metrics, policy = source["metrics"], source["policy"]
        actual_p = policy.get("parallelism", policy.get("hardware_state", {}).get("parallelism"))
        comparison_p = actual_p or 4
        estimates = {str(p): modeled(metrics, p) for p in (1, 2, 4, 8)}
        records.append({"experiment_id": source["experiment_id"], "source_record": str(path.relative_to(ROOT)),
                        "policy": label, "workload": source["sequence"]["name"], "policy_version": policy.get("version", "legacy"),
                        "parameters": {key: value for key, value in policy.items() if key not in {"name", "version"}},
                        "hm_commit": source["encoder"]["revision"], "input": source["sequence"], "qp": qp,
                        "cu_size": "HM-default-max-CU-64", "P": comparison_p, "avg_k": metrics["average_k"],
                        "rdo_evaluations": metrics["rdo_evaluations"], "rdo_reduction": metrics["rdo_reduction_fraction"],
                        "winner_retention": metrics["winner_retention_rate"], "candidate_recall": metrics["winner_retention_rate"],
                        "bitrate": metrics["annex_b_kbps"],
                        "psnr": {key: metrics[f"psnr_{key}_db"] for key in ("y", "u", "v", "yuv")},
                        "estimated_batches": estimates[str(comparison_p)]["average_batches"],
                        "estimated_cycles": estimates[str(comparison_p)]["estimated_cycles"], "estimated_by_p": estimates,
                        "measurement_type": "software_measured_with_analytical_hardware_estimate",
                        "in_matched_matrix": True, "status": "PASS"})
    groups = defaultdict(list)
    for record in records:
        groups[(record["workload"], record["policy"])].append(record)
    bd_rates_by_workload = {}
    for (workload, policy), rows in groups.items():
        if policy == "full_rdo":
            bd_rates_by_workload[f"{workload}:full_rdo"] = 0.0
            continue
        if len(rows) != 4:
            continue
        reference_curve = [(row["bitrate"], row["psnr"]["y"]) for row in sorted(groups[(workload, "full_rdo")], key=lambda item: item["qp"])]
        curve = [(row["bitrate"], row["psnr"]["y"]) for row in sorted(rows, key=lambda item: item["qp"])]
        bd_rates_by_workload[f"{workload}:{policy}"] = bd_rate(reference_curve, curve)
    policy_values = defaultdict(list)
    for key, value in bd_rates_by_workload.items():
        policy_values[key.split(":", 1)[1]].append(value)
    bd_rates = {policy: sum(values) / len(values) for policy, values in policy_values.items()}
    for record in records:
        record["bd_rate_percent"] = bd_rates_by_workload.get(f"{record['workload']}:{record['policy']}")
        full_cycles = next(row for row in groups[(record["workload"], "full_rdo")] if row["qp"] == record["qp"])["estimated_by_p"][str(record["P"])]["estimated_cycles"]
        record["estimated_cycle_reduction"] = 1 - record["estimated_cycles"] / full_cycles
    records.sort(key=lambda row: (row["policy"], row["qp"]))
    payload = {"schema_version": "chia-rdo.experiment-database.v1", "bd_rate_definition": "cubic log(rate) versus Y-PSNR over QP 22/27/32/37 overlap",
               "records": records, "policy_bd_rate_percent": bd_rates,
               "bd_rate_by_workload_percent": bd_rates_by_workload}
    output = ROOT / "results/experiments/database.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with (output.parent / "database.csv").open("w", newline="") as stream:
        fields = ["experiment_id", "workload", "policy", "policy_version", "qp", "P", "avg_k", "rdo_evaluations", "rdo_reduction", "winner_retention", "bitrate", "psnr_y", "psnr_yuv", "bd_rate_percent", "estimated_batches", "estimated_cycles", "estimated_cycle_reduction", "status"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({**{key: row.get(key) for key in fields}, "psnr_y": row["psnr"]["y"], "psnr_yuv": row["psnr"]["yuv"]})
    print(json.dumps({"records": len(records), "curves": len(bd_rates), "bd_rate_percent": bd_rates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
