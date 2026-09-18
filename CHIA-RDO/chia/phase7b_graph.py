#!/usr/bin/env python3
"""Native CHIA analytical funnel for the Phase-7B serial architecture."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from chia.base.ChiaFunction import ChiaFunction, get


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "results/phase7b"
EXPERIMENT_ROOT = RESULT_ROOT / "experiments"
SYNTHESIS = RESULT_ROOT / "synthesis_results.json"
WIDTHS = RESULT_ROOT / "width_analysis.json"
PWAY_GATE = RESULT_ROOT / "pway_rtl_gate.json"
MODEL_VERSION = "serial-balanced-tree-fit.v3"
P_VALUES = tuple(range(1, 17))
DEPTH_VALUES = (2, 3)
COST_WIDTH_VALUES = tuple(range(31, 57))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
    temporary.replace(path)


def candidate_id(configuration: dict) -> str:
    identity = {"model_version": MODEL_VERSION, "hardware_configuration": configuration}
    value = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return f"phase7b-{hashlib.sha256(value).hexdigest()[:16]}"


def candidate_pool() -> list[dict]:
    rows = []
    for p in P_VALUES:
        for depth in DEPTH_VALUES:
            for width in COST_WIDTH_VALUES:
                configuration = {
                    "p": p,
                    "pipeline_depth": depth,
                    "cost_width": width,
                    "max_candidates": 35,
                    "transform_parallelism": 1,
                    "quant_parallelism": 1,
                    "multiplier_mode": 0,
                    "scheduler_architecture": "static_lane_batch",
                    "pe_architecture": "resource_shared_serial",
                    "winner_reduction": "balanced_tree",
                }
                rows.append({"experiment_id": candidate_id(configuration),
                             "hardware_configuration": configuration})
    return rows


@ChiaFunction(num_cpus=0)
def screen_candidate(candidate: dict, calibration: dict) -> dict:
    hardware = candidate["hardware_configuration"]
    p = hardware["p"]
    depth = hardware["pipeline_depth"]
    width = hardware["cost_width"]
    measured = calibration[str(depth)]
    fits = calibration["measured_fits"][str(depth)]
    fmax = max(1.0, fits["fmax_log2"]["intercept"]
               + fits["fmax_log2"]["slope"] * math.log2(p))
    width_delta = width - 31
    lut = max(1, round(fits["lut"]["intercept"] + fits["lut"]["slope"] * p
                       + 2.0 * width_delta * p))
    ff = max(1, round(fits["ff"]["intercept"] + fits["ff"]["slope"] * p
                      + 1.0 * width_delta * p))
    dsp = max(1, round(fits["dsp"]["intercept"] + fits["dsp"]["slope"] * p))
    carry8 = max(1, round(fits["carry8"]["intercept"] + fits["carry8"]["slope"] * p))
    power = max(0.0, fits["power_w"]["intercept"] + fits["power_w"]["slope"] * p)
    batch_cycles = calibration["batch_cycles"][str(depth)]
    candidate_throughput = p * fmax * 1e6 / batch_cycles
    worst_event_cycles = math.ceil(35 / p) * batch_cycles
    budgets = calibration["budgets"]
    feasible = (width >= calibration["minimum_corpus_safe_cost_width"]
                and lut <= budgets["clb_lut"] and ff <= budgets["clb_register"]
                and dsp <= budgets["dsp48e2"] and carry8 <= budgets["carry8"])
    return {
        **candidate,
        "schema_version": "chia-rdo.phase7b-experiment.v1",
        "model_version": MODEL_VERSION,
        "result_status": "PASS" if feasible else "INFEASIBLE",
        "feasible": feasible,
        "measurement_level": "ANALYTICAL_CALIBRATED_EXTRAPOLATION",
        "estimated_lut": lut,
        "estimated_ff": ff,
        "estimated_dsp": dsp,
        "estimated_carry8": carry8,
        "estimated_power_w": power,
        "estimated_fmax_mhz": fmax,
        "candidate_latency_cycles": measured["candidate_latency_cycles"],
        "batch_cycles": batch_cycles,
        "worst_k35_event_cycles": worst_event_cycles,
        "candidate_throughput_proxy_per_second": candidate_throughput,
        "timing_status": "ESTIMATED_FAIL" if fmax < 200.0 else "ESTIMATED_PASS",
        "cost_width_corpus_feasible": width >= calibration["minimum_corpus_safe_cost_width"],
        "rtl_configuration_implemented": True,
        "calibration_scope": "Least-squares fit to routed width-31 builds; balanced-tree rows supersede matching serial-scan rows",
        "timestamp": utc_now(),
    }


def dominates(left: dict, right: dict) -> bool:
    minimizing = ("estimated_lut", "estimated_dsp", "estimated_power_w")
    no_worse = all(left[key] <= right[key] for key in minimizing)
    no_worse &= (left["candidate_throughput_proxy_per_second"]
                 >= right["candidate_throughput_proxy_per_second"])
    strictly_better = any(left[key] < right[key] for key in minimizing)
    strictly_better |= (left["candidate_throughput_proxy_per_second"]
                        > right["candidate_throughput_proxy_per_second"])
    return no_worse and strictly_better


def pareto(rows: list[dict]) -> list[dict]:
    feasible = [row for row in rows if row["feasible"]]
    return sorted(
        [row for row in feasible if not any(
            dominates(other, row) for other in feasible
            if other["experiment_id"] != row["experiment_id"]
        )],
        key=lambda row: (row["hardware_configuration"]["p"],
                         row["hardware_configuration"]["pipeline_depth"]),
    )


def linear_fit(points: list[tuple[float, float]]) -> dict:
    x_mean = sum(x for x, _ in points) / len(points)
    y_mean = sum(y for _, y in points) / len(points)
    denominator = sum((x - x_mean) ** 2 for x, _ in points)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator
    return {"intercept": y_mean - slope * x_mean, "slope": slope, "points": len(points)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=832)
    parser.add_argument("--address", default=None)
    args = parser.parse_args()
    pool = candidate_pool()
    if not 1 <= args.count <= len(pool):
        parser.error(f"count must be in 1..{len(pool)}")
    synthesis = json.loads(SYNTHESIS.read_text())
    widths = json.loads(WIDTHS.read_text())
    gate = json.loads(PWAY_GATE.read_text())
    measured = {
        str(row["pipeline_depth"]): row
        for row in synthesis["rows"]
        if row["p"] == 1 and row.get("cost_width") == 31
    }
    baseline = json.loads((ROOT / "results/phase7/vivado_results.json").read_text())["rows"]
    baseline_p1 = next(row for row in baseline if row["p"] == 1)
    baseline_p2 = next(row for row in baseline if row["p"] == 2)
    accounting = json.loads((RESULT_ROOT / "resource_accounting.json").read_text())
    batch_cycles = {str(row["pipeline_depth"]): row["batch_cycles"] for row in gate["runs"] if row["p"] == 1}
    routed_by_configuration = {}
    for row in synthesis["rows"]:
        if row.get("cost_width") != 31:
            continue
        key = (row["p"], row["pipeline_depth"])
        existing = routed_by_configuration.get(key)
        if existing is None or row.get("winner_reduction") == "balanced_tree":
            routed_by_configuration[key] = row
    routed_w31 = list(routed_by_configuration.values())
    measured_fits = {}
    for depth in DEPTH_VALUES:
        depth_rows = [row for row in routed_w31 if row["pipeline_depth"] == depth]
        measured_fits[str(depth)] = {
            metric: linear_fit([(row["p"], row[metric]) for row in depth_rows])
            for metric in ("lut", "ff", "dsp", "carry8", "power_w")
        }
        measured_fits[str(depth)]["fmax_log2"] = linear_fit([
            (math.log2(row["p"]), row["fmax_mhz"]) for row in depth_rows
        ])
    calibration = {
        **measured,
        "static_power_w": 0.289,
        "batch_cycles": batch_cycles,
        "minimum_corpus_safe_cost_width": widths["minimum_corpus_safe_cost_width"],
        "budgets": accounting["target"]["internal_budget_70_percent"],
        "measured_fits": measured_fits,
    }
    import ray
    ray.init(address=args.address, ignore_reinit_error=True)
    run_id = f"phase7b-{uuid.uuid4().hex[:12]}"
    selected_pool = pool[:args.count]
    cached = {}
    pending = []
    for candidate in selected_pool:
        path = EXPERIMENT_ROOT / f"{candidate['experiment_id']}.json"
        if path.is_file():
            cached[candidate["experiment_id"]] = json.loads(path.read_text())
        else:
            pending.append(candidate)
    evaluated = get([screen_candidate.chia_remote(candidate, calibration) for candidate in pending])
    for row in evaluated:
        atomic_json(EXPERIMENT_ROOT / f"{row['experiment_id']}.json", row)
        cached[row["experiment_id"]] = row
    rows = [cached[candidate["experiment_id"]] for candidate in selected_pool]
    frontier = pareto(rows)
    if len(frontier) <= 20:
        promoted = frontier
    else:
        indices = sorted({round(index * (len(frontier) - 1) / 19) for index in range(20)})
        promoted = [frontier[index] for index in indices]
    experiments_path = RESULT_ROOT / "experiments.jsonl"
    experiments_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                                encoding="ascii")
    provenance = {
        "schema_version": "chia-rdo.phase7b-search.v1",
        "created_utc": utc_now(),
        "chia_run_id": run_id,
        "orchestration": "native asynchronous ChiaFunction graph",
        "model_version": MODEL_VERSION,
        "candidate_count": len(rows),
        "cache_hits": len(rows) - len(evaluated),
        "new_evaluations": len(evaluated),
        "pareto_count": len(frontier),
        "promoted_count": len(promoted),
        "source_artifacts_sha256": {
            str(path.relative_to(ROOT)): digest(path)
            for path in (SYNTHESIS, WIDTHS, PWAY_GATE)
        },
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                                     text=True, stdout=subprocess.PIPE).stdout.strip(),
        "git_dirty": bool(subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.strip()),
    }
    atomic_json(RESULT_ROOT / "model_results.json", {**provenance, "calibration": calibration})
    atomic_json(RESULT_ROOT / "pareto.json", {**provenance, "rows": frontier})
    atomic_json(RESULT_ROOT / "vivado_candidates.json", {
        **provenance,
        "builds": [{"build_id": f"serial-p{row['hardware_configuration']['p']}-d{row['hardware_configuration']['pipeline_depth']}-w{row['hardware_configuration']['cost_width']}-tree",
                    "experiment_id": row["experiment_id"],
                    **row["hardware_configuration"]} for row in promoted],
    })
    print(json.dumps(provenance, indent=2, sort_keys=True))
    ray.shutdown()


if __name__ == "__main__":
    main()
