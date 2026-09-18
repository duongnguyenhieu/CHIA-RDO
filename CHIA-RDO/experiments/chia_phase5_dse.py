#!/usr/bin/env python3
"""Native asynchronous CHIA graph for Phase-5 RTL design-space exploration."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from chia.base.ChiaFunction import ChiaFunction, get


ROOT = Path(__file__).resolve().parents[1]
P_VALUES = (1, 2, 4, 8)
D_VALUES = (1, 2, 4)
B_VALUES = (35, 48, 64)
W_VALUES = (48, 56)


@ChiaFunction(num_cpus=0)
def generate_experiments(stage: str, completed_keys: set[str]) -> list[dict]:
    if stage == "smoke":
        combinations = ((p, 2, 35, 56) for p in P_VALUES)
    elif stage == "broad":
        combinations = itertools.product(P_VALUES, D_VALUES, B_VALUES, W_VALUES)
    elif stage == "refinement":
        combinations = ((p, 1, 35, 56) for p in P_VALUES)
    else:
        raise ValueError(f"unsupported stage: {stage}")
    experiments = []
    for p, depth, buffer_depth, cost_width in combinations:
        key = f"p{p}-d{depth}-b{buffer_depth}-w{cost_width}"
        if key not in completed_keys:
            experiments.append({"key": key, "p": p, "pipeline_depth": depth,
                                "buffer_depth": buffer_depth, "cost_width": cost_width})
    return experiments


def _verilator() -> str:
    executable = shutil.which("verilator")
    if executable:
        return executable
    candidate = Path(os.environ.get("CONDA_PREFIX", "")) / "bin/verilator"
    if candidate.is_file():
        return str(candidate)
    raise RuntimeError("verilator is not available")


@ChiaFunction(resources={"rtl_sim_cpu": 0.25}, num_cpus=0.25, max_retries=1)
def elaborate_rtl(config: dict) -> dict:
    commands = (
        [_verilator(), "--lint-only", "--top-module", "rdo_pe",
         f"-GPIPELINE_DEPTH={config['pipeline_depth']}", f"-GCOST_WIDTH={config['cost_width']}",
         "rtl/rdo_pe.sv"],
        [_verilator(), "--lint-only", "--top-module", "rdo_scheduler",
         f"-GP={config['p']}", f"-GPIPELINE_DEPTH={config['pipeline_depth']}",
         f"-GCOST_WIDTH={config['cost_width']}", f"-GBUFFER_DEPTH={config['buffer_depth']}",
         "rtl/rdo_scheduler.sv"],
        [_verilator(), "--lint-only", "--top-module", "rdo_array",
         f"-GP={config['p']}", f"-GPIPELINE_DEPTH={config['pipeline_depth']}",
         f"-GCOST_WIDTH={config['cost_width']}", f"-GMAX_CANDIDATES={config['buffer_depth']}",
         "rtl/rdo_pe.sv", "rtl/rdo_array.sv"],
    )
    started = time.perf_counter()
    logs = []
    with tempfile.TemporaryDirectory(prefix="chia-rdo-phase5-") as directory:
        for command in commands:
            process = subprocess.run(command + ["--Mdir", directory], cwd=ROOT, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            logs.append(process.stdout)
            if process.returncode:
                raise RuntimeError(f"RTL elaboration failed for {config['key']}:\n{process.stdout}")
    elapsed = time.perf_counter() - started
    return {**config, "verilator_status": "pass", "verilator_seconds": elapsed,
            "verilator_log_sha256": hashlib.sha256("".join(logs).encode()).hexdigest(),
            "worker_host": socket.gethostname()}


@ChiaFunction(num_cpus=0)
def evaluate_result(elaboration: dict, average_k_values: list[float], vector_metadata: dict) -> dict:
    average_cycles = sum(
        elaboration["pipeline_depth"] + math.ceil(k / elaboration["p"])
        for k in average_k_values
    ) / len(average_k_values)
    raw_costs = [
        (int(fields[0]) << 16) + int(fields[1]) * int(fields[2])
        for line in (ROOT / "results/phase5/rdo_pe_vectors.txt").read_text().splitlines()[:-2]
        for fields in (line.split(),)
    ]
    overflow_vectors = sum(cost >= (1 << elaboration["cost_width"]) for cost in raw_costs)
    logic_bit_proxy = (
        elaboration["p"] * elaboration["pipeline_depth"]
        * (elaboration["cost_width"] + 32 + 24 + 32 + 6)
        + elaboration["buffer_depth"] * (elaboration["cost_width"] + 6)
    )
    return {**elaboration, "schema_version": "chia-rdo.phase5-experiment.v1",
            "measurement_level": "measured Verilator elaboration plus analytical RTL cycle/storage proxy",
            "average_cycles_per_event": average_cycles, "logic_bit_proxy": logic_bit_proxy,
            "hm_vector_overflow": overflow_vectors, "feasible": overflow_vectors == 0,
            "quality_policy": "adaptive-threshold.v1", "qp_values": vector_metadata["qp_values"]}


def dominates(left: dict, right: dict) -> bool:
    objectives = ("average_cycles_per_event", "logic_bit_proxy")
    return all(left[key] <= right[key] for key in objectives) and any(left[key] < right[key] for key in objectives)


@ChiaFunction(num_cpus=0)
def update_pareto(stage: str, previous: list[dict], rows: list[dict]) -> dict:
    combined = previous + rows
    feasible = [row for row in combined if row["feasible"]]
    frontier = [row for row in feasible if not any(dominates(other, row) for other in feasible if other is not row)]
    return {"stage": stage, "evaluated": len(rows), "all_results": combined,
            "pareto": sorted(frontier, key=lambda row: (row["average_cycles_per_event"], row["logic_bit_proxy"]))}


@ChiaFunction(num_cpus=0)
def persist_result(state: dict) -> dict:
    result = {"schema_version": "chia-rdo.phase5-dse.v1", "status": "pass",
              "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "orchestration": "native ChiaFunction graph over Ray object references",
              "design_space": {"p": P_VALUES, "pipeline_depth": D_VALUES,
                               "buffer_depth": B_VALUES, "cost_width": W_VALUES}, **state}
    path = ROOT / "results/phase5/chia_dse.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return {"path": str(path.relative_to(ROOT)), "evaluated": len(state["all_results"]),
            "pareto_points": len(state["pareto"]), "status": "pass"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("smoke", "broad", "refinement"), default="smoke")
    parser.add_argument("--address", default=None, help="Ray address; omit for a local CHIA runtime")
    parser.add_argument("--force", action="store_true", help="re-evaluate configurations already in the artifact")
    args = parser.parse_args()
    import ray
    ray.init(address=args.address, resources={"rtl_sim_cpu": 1.0} if args.address is None else None,
             ignore_reinit_error=True)

    existing_path = ROOT / "results/phase5/chia_dse.json"
    existing = (json.loads(existing_path.read_text())
                if existing_path.exists() and not args.force else {"all_results": []})
    completed = {row["key"] for row in existing["all_results"]}
    configs = get(generate_experiments.chia_remote(args.stage, completed))
    metadata = json.loads((ROOT / "results/phase5/rdo_pe_vectors.json").read_text())
    phase4 = json.loads((ROOT / "results/phase4/database.json").read_text())
    average_k_values = [row["avg_k"] for row in phase4["records"] if row["policy"] == "adaptive_threshold"]
    if not average_k_values:
        raise RuntimeError("Phase-4 adaptive_threshold records are unavailable")

    elaboration_refs = [elaborate_rtl.chia_remote(config) for config in configs]
    evaluation_refs = [evaluate_result.chia_remote(ref, average_k_values, metadata) for ref in elaboration_refs]
    evaluated_rows = get(evaluation_refs)
    state_ref = update_pareto.chia_remote(args.stage, existing["all_results"], evaluated_rows)
    summary = get(persist_result.chia_remote(state_ref))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
