#!/usr/bin/env python3
"""Deterministic CHIA graph for cached Phase 3 proposal/evaluation updates."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from chia.base.ChiaFunction import ChiaFunction, get


ROOT = Path(__file__).resolve().parents[1]
ACTIONS = (
    {"policy": "adaptive_threshold", "command": ["python3", "software/run_policy.py", "--policy", "adaptive_threshold", "--easy-threshold", "0.04", "--hard-threshold", "0.20", "--easy-k", "4", "--medium-k", "16", "--hard-k", "35"]},
    {"policy": "relative_satd", "command": ["python3", "software/run_policy.py", "--policy", "relative_satd", "--relative-threshold", "0.50", "--minimum-k", "8", "--maximum-k", "35"]},
    {"policy": "adaptive_hw_v1_p8", "command": ["python3", "software/run_policy.py", "--policy", "adaptive_hw_v1", "--p", "8"]},
)


@ChiaFunction(num_cpus=0)
def generate_policy(state: dict) -> dict | None:
    index = state["iteration"]
    return ACTIONS[index] if index < len(ACTIONS) else None


@ChiaFunction(resources={"hevc_cpu": 0.01})
def run_experiment(action: dict, execute: bool) -> dict:
    if execute:
        process = subprocess.run(action["command"], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
        if process.returncode:
            raise RuntimeError(process.stdout)
    return {"policy": action["policy"], "status": "cached-or-executed" if execute else "cached"}


@ChiaFunction(num_cpus=0)
def collect_and_evaluate(experiment: dict) -> dict:
    subprocess.run(["python3", "scripts/build_experiment_db.py"], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    database = json.loads((ROOT / "results/experiments/database.json").read_text())
    rows = [row for row in database["records"] if row["policy"] == experiment["policy"]]
    if not rows:
        raise RuntimeError(f"no database rows for {experiment['policy']}")
    bd_rate = database["policy_bd_rate_percent"][experiment["policy"]]
    cycles = sum(row["estimated_by_p"]["8"]["estimated_cycles"] for row in rows) / len(rows)
    retention = sum(row["winner_retention"] for row in rows) / len(rows)
    reward = -bd_rate - 0.03 * cycles if bd_rate < 1.0 else -100.0 - bd_rate
    return {**experiment, "bd_rate_percent": bd_rate, "estimated_cycles_p8": cycles,
            "winner_retention": retention, "reward": reward,
            "objective": "maximize reward=-BD_rate-0.03*estimated_cycles subject to BD_rate<1%"}


@ChiaFunction(num_cpus=0)
def update_pareto(state: dict, result: dict) -> dict:
    history = state["history"] + [result]
    return {"iteration": state["iteration"] + 1, "history": history,
            "best_action": max(history, key=lambda row: row["reward"])["policy"]}


def invoke(function, remote: bool, *args):
    return get(function.chia_remote(*args)) if remote else function(*args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="execute commands instead of validating cached records")
    parser.add_argument("--remote", action="store_true", help="dispatch nodes through a local Ray runtime")
    args = parser.parse_args()
    if args.remote:
        import ray
        ray.init(resources={"hevc_cpu": 1.0}, ignore_reinit_error=True)
    state = {"iteration": 0, "history": [], "best_action": None}
    while True:
        action = invoke(generate_policy, args.remote, state)
        if action is None:
            break
        experiment = invoke(run_experiment, args.remote, action, args.execute)
        result = invoke(collect_and_evaluate, args.remote, experiment)
        state = invoke(update_pareto, args.remote, state, result)
    output = {"schema_version": "chia-rdo.deterministic-loop.v1", "status": "PASS",
              "state": state, "actions": list(ACTIONS),
              "transition": "generate policy -> run/cache experiment -> collect metrics -> evaluate -> update Pareto state"}
    path = ROOT / "results/experiments/chia-loop.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
