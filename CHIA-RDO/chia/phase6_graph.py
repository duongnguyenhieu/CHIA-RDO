#!/usr/bin/env python3
"""Native asynchronous CHIA graph and checkpointed Phase-6 campaign driver."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from chia.base.ChiaFunction import ChiaFunction, get


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chia"))
from phase6_agent import FROZEN_POLICY, propose, validate_proposal  # noqa: E402
from phase6_objectives import model_rtl_error, normalized_balanced_score, pareto_frontier  # noqa: E402

RESULT_ROOT = ROOT / "results" / "phase6"
EXPERIMENT_ROOT = RESULT_ROOT / "experiments"
PARETO_ROOT = RESULT_ROOT / "pareto"
SUMMARY_ROOT = RESULT_ROOT / "summaries"
PHASE5_RTL = ROOT / "results" / "phase5_3" / "rtl_gate.json"
PHASE4_DB = ROOT / "results" / "phase4" / "database.json"
HM_REVISION = "22178e370178133438c0339f57b3b3a29f112909"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="ascii")
    temporary.replace(path)


def git_state() -> dict:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, check=True).stdout.strip())
    return {"commit": commit, "dirty": dirty}


def aggregate_policy(policy_id: str, p: int) -> dict:
    database = json.loads(PHASE4_DB.read_text())
    source_policy = {
        "adaptive_threshold_v1_frozen": "adaptive_threshold",
        "adaptive_hw_batch_fill_baseline": "adaptive_hw_batch_fill_p8",
        "adaptive_hw_v1_p8": "adaptive_hw_v1_p8",
        "full_rdo": "full_rdo",
        "fixed_k16": "fixed_k16",
    }.get(policy_id)
    if source_policy is None or (source_policy in {"adaptive_hw_batch_fill_p8", "adaptive_hw_v1_p8"} and p != 8):
        return {"status": "UNAVAILABLE", "reason": "matched Phase-4 software measurements do not exist"}
    records = [row for row in database["records"] if row["policy"] == source_policy]
    if not records:
        return {"status": "UNAVAILABLE", "reason": "policy absent from protected Phase-4 database"}
    event_weights = [row["rdo_evaluations"] / row["avg_k"] for row in records]
    event_total = sum(event_weights)

    def weighted(key: str) -> float:
        return sum(float(row[key]) * weight for row, weight in zip(records, event_weights)) / event_total

    psnr = {component: sum(row["psnr"][component] for row in records) / len(records)
            for component in ("y", "u", "v", "yuv")}
    batches = sum(row["estimated_by_p"][str(p)]["average_batches"] * weight
                  for row, weight in zip(records, event_weights)) / event_total
    return {
        "status": "VERIFIED", "source": "protected Phase-4 matched measurements",
        "source_policy": source_policy, "records": len(records),
        "bd_rate_percent": database["policy_bd_rate_percent"][source_policy],
        "average_k": weighted("avg_k"), "average_rdo_evaluations": weighted("avg_k"),
        "rdo_reduction": weighted("rdo_reduction"),
        "winner_retention": weighted("winner_retention"),
        "candidate_recall": weighted("candidate_recall"), "psnr": psnr,
        "average_batches": batches, "qp_values": [22, 27, 32, 37],
        "bd_rate_definition": database["bd_rate_definition"],
    }


@ChiaFunction(num_cpus=0)
def proposal_agent(history: list[dict], count: int, iteration: int) -> dict:
    selected = propose(history, count)
    history_digest = hashlib.sha256(
        json.dumps([row["experiment_id"] for row in history], separators=(",", ":")).encode()
    ).hexdigest()
    return {"iteration": iteration, "history_count_consumed": len(history),
            "history_digest": history_digest, "proposals": selected,
            "agent": "deterministic frontier-novelty-information-gain.v1"}


@ChiaFunction(num_cpus=0)
def analytical_screen(proposal: dict) -> dict:
    validate_proposal(proposal)
    hardware = proposal["hardware_configuration"]
    policy = aggregate_policy(proposal["policy"]["policy_id"], hardware["p"])
    maximum_cost = max(json.loads(line)["rd_cost_q16"] for line in
                       (ROOT / "tests/full_rdo/vectors/pway_candidates.jsonl").read_text().splitlines())
    width_feasible = maximum_cost < (1 << hardware["cost_width"])
    resource_proxy = (hardware["p"] * hardware["pipeline_depth"]
                      * (hardware["cost_width"] + 32 + 24 + 32 + 6)
                      + hardware["buffer_depth"] * (hardware["cost_width"] + 6))
    estimated_cycles = (4.0 * policy["average_batches"] if policy["status"] == "VERIFIED" else None)
    exact_rtl_shape = (hardware == {"p": hardware["p"], "pipeline_depth": 2, "buffer_depth": 35,
                                    "cost_width": 56, "scheduler_architecture": "static",
                                    "pe_architecture": "full_rdo_mvp_4x4"})
    return {
        "proposal": proposal, "analytical_status": "PASS", "policy_metrics": policy,
        "estimated_cycles": estimated_cycles, "estimated_batches": policy.get("average_batches"),
        "resource_proxy": resource_proxy, "resource_proxy_status": "ESTIMATED",
        "maximum_observed_cost_q16": maximum_cost, "cost_width_corpus_feasible": width_feasible,
        "rtl_promotion_eligible": proposal["measurement_level"] >= 2 and exact_rtl_shape and width_feasible,
        "screen_worker": socket.gethostname(), "screened_utc": utc_now(),
    }


def _pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def _write_memory(directory: Path, name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (directory / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values), encoding="ascii")


@ChiaFunction(resources={"rtl_sim_cpu": 1.0}, num_cpus=1, max_retries=1)
def run_rtl(screen: dict) -> dict:
    if not screen["rtl_promotion_eligible"]:
        return {"status": "NOT_PROMOTED", "reason": "configuration is analytical-only"}
    p = screen["proposal"]["hardware_configuration"]["p"]
    groups = [json.loads(line) for line in
              (ROOT / "tests/full_rdo/vectors/pway_groups.jsonl").read_text().splitlines()]
    with tempfile.TemporaryDirectory(prefix=f"chia-rdo-phase6-p{p}-") as temporary:
        build = Path(temporary)
        memories = {
            "references": ([_pack(row["references"], 8) for row in groups], 136),
            "original": ([_pack(row["original"], 8) for row in groups], 128),
            "qp": ([row["qp"] for row in groups], 6),
            "lambda": ([row["lambda_q16"] for row in groups], 32),
            "modes": ([_pack(row["modes"], 6) for row in groups], 210),
            "rates": ([_pack(row["rate_bits"], 24) for row in groups], 840),
            "costs": ([_pack(row["rd_cost_q16"], 56) for row in groups], 1960),
        }
        for k in (4, 16, 35):
            memories[f"winner_rank_k{k}"] = ([row["winners"][str(k)]["rank"] for row in groups], 6)
            memories[f"winner_mode_k{k}"] = ([row["winners"][str(k)]["mode"] for row in groups], 6)
            memories[f"winner_cost_k{k}"] = ([row["winners"][str(k)]["cost_q16"] for row in groups], 56)
        for name, (values, width) in memories.items():
            _write_memory(build, name, values, width)
        sources = [ROOT / "rtl" / name for name in
                   ("rdo_pe.sv", "full_rdo_codec_4x4.sv", "full_rdo_mvp_4x4.sv", "full_rdo_pway.sv")]
        sources.append(ROOT / "rtl/tb/full_rdo_pway_tb.sv")
        started = time.perf_counter()
        compile_process = subprocess.run(
            [shutil.which("verilator") or "verilator", "--binary", "--timing", "-Wall",
             "-Wno-DECLFILENAME", "--top-module", "full_rdo_pway_tb", f"-GP={p}",
             "--Mdir", str(build / "obj"), *map(str, sources)], cwd=build, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=300)
        if compile_process.returncode:
            raise RuntimeError(f"Verilator build failed for P={p}:\n{compile_process.stdout}")
        simulation = subprocess.run([str(build / "obj/Vfull_rdo_pway_tb")], cwd=build, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    check=False, timeout=300)
        if simulation.returncode:
            raise RuntimeError(f"RTL regression failed for P={p}:\n{simulation.stdout}")
        measured = json.loads(next(line for line in simulation.stdout.splitlines() if line.startswith("{")))
        return {"status": "PASS", "measurement": measured,
                "elapsed_seconds": time.perf_counter() - started,
                "worker_host": socket.gethostname(),
                "verilator_log_sha256": hashlib.sha256(compile_process.stdout.encode()).hexdigest()}


@ChiaFunction(num_cpus=0)
def evaluate_experiment(screen: dict, rtl: dict, run_id: str, iteration: int, backend: str) -> dict:
    proposal = screen["proposal"]
    policy = screen["policy_metrics"]
    measured_cycles = None
    utilization = None
    if rtl["status"] == "PASS" and policy["status"] == "VERIFIED":
        p = proposal["hardware_configuration"]["p"]
        cycles_per_batch = [rtl["measurement"][f"cycles_k{k}"] / ((k + p - 1) // p)
                            for k in (4, 16, 35)]
        if len(set(cycles_per_batch)) != 1:
            raise RuntimeError("RTL cycles per batch are not stable across frozen K levels")
        measured_cycles = policy["average_batches"] * cycles_per_batch[0]
        utilization = policy["average_k"] / (p * policy["average_batches"])
    software_available = policy["status"] == "VERIFIED"
    feasible = bool(screen["cost_width_corpus_feasible"] and screen["analytical_status"] == "PASS"
                    and software_available)
    row = {
        "schema_version": "chia-rdo.phase6-experiment.v1",
        "experiment_id": proposal["experiment_id"],
        "parent_experiment_id": proposal["parent_experiment_id"],
        "chia_run_id": run_id, "iteration": iteration,
        "track": proposal["track"], "proposal": proposal,
        "policy_id": proposal["policy"]["policy_id"],
        "policy_version": proposal["policy"]["policy_version"],
        "hardware_configuration": proposal["hardware_configuration"],
        "workload": proposal["workload_set"], "qp": policy.get("qp_values"),
        "k": proposal["policy"]["parameters"].get("k_levels", [4, 16, 35]),
        "p": proposal["hardware_configuration"]["p"],
        "batches": policy.get("average_batches"),
        "estimated_cycles": screen["estimated_cycles"],
        "rtl_cycles_per_event": measured_cycles,
        "utilization": utilization,
        "dispatch_overhead": 0 if measured_cycles is not None else None,
        "average_k": policy.get("average_k"),
        "average_rdo_evaluations": policy.get("average_rdo_evaluations"),
        "rdo_reduction": policy.get("rdo_reduction"),
        "winner_retention": policy.get("winner_retention"),
        "candidate_recall": policy.get("candidate_recall"),
        "bd_rate_percent": policy.get("bd_rate_percent"),
        "psnr": policy.get("psnr"), "bitrate": None,
        "resource_proxy": screen["resource_proxy"],
        "lut": None, "ff": None, "bram": None, "dsp": None, "fmax_mhz": None, "wns_ns": None,
        "result_status": "PASS" if feasible else "CANCELLED", "feasible": feasible, "dominated": False,
        "measurement_level": proposal["measurement_level"],
        "software_metrics_status": policy["status"],
        "rtl_metrics_status": "VERIFIED" if measured_cycles is not None else rtl["status"],
        "vivado_metrics_status": "UNAVAILABLE",
        "execution_backend": backend, "gcp_worker": None,
        "estimated_cloud_cost_usd": 0.0 if backend == "local" else None,
        "actual_cloud_cost_usd": None, "timestamp": utc_now(),
        "hm_revision": HM_REVISION, "git": git_state(), "rtl_evidence": rtl,
    }
    return row


@ChiaFunction(num_cpus=0)
def persist_experiment(row: dict) -> dict:
    path = EXPERIMENT_ROOT / f"{row['experiment_id']}.json"
    if path.exists():
        existing = json.loads(path.read_text())
        if existing["experiment_id"] != row["experiment_id"]:
            raise RuntimeError("experiment checkpoint identity mismatch")
    atomic_json(path, row)
    return row


@ChiaFunction(num_cpus=0)
def update_state(previous: list[dict], rows: list[dict], run_id: str, iteration: int) -> dict:
    indexed = {row["experiment_id"]: row for row in previous}
    indexed.update({row["experiment_id"]: row for row in rows})
    history = list(indexed.values())
    frontier = pareto_frontier(history)
    for row in frontier:
        row["balanced_score"] = normalized_balanced_score(row, frontier)
    state = {"schema_version": "chia-rdo.phase6-state.v1", "chia_run_id": run_id,
             "iteration": iteration, "updated_utc": utc_now(), "experiments": history,
             "pareto": frontier, "model_rtl_error": model_rtl_error(history)}
    atomic_json(PARETO_ROOT / "latest.json", state)
    return state


def load_history() -> list[dict]:
    if not EXPERIMENT_ROOT.exists():
        return []
    history = []
    for path in sorted(EXPERIMENT_ROOT.glob("*.json")):
        row = json.loads(path.read_text())
        if row.get("software_metrics_status") == "UNAVAILABLE":
            row["result_status"] = "CANCELLED"
            row["feasible"] = False
            row["invalidated_reason"] = "No matched HM software measurements exist for this policy label."
            atomic_json(path, row)
        history.append(row)
    return history


def run_wave(history: list[dict], count: int, iteration: int, run_id: str) -> tuple[list[dict], dict]:
    proposal_batch = get(proposal_agent.chia_remote(history, count, iteration))
    screens = [analytical_screen.chia_remote(proposal) for proposal in proposal_batch["proposals"]]
    rtl_results = [run_rtl.chia_remote(screen) for screen in screens]
    evaluations = [evaluate_experiment.chia_remote(screen, rtl, run_id, iteration, "local")
                   for screen, rtl in zip(screens, rtl_results)]
    rows = get([persist_experiment.chia_remote(evaluation) for evaluation in evaluations])
    state = get(update_state.chia_remote(history, rows, run_id, iteration))
    return state["experiments"], {"proposal_batch": proposal_batch, "state": state}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--first-wave", type=int, default=6)
    parser.add_argument("--address", default=None)
    args = parser.parse_args()
    if args.count < 1 or args.first_wave < 1 or args.first_wave > args.count:
        raise SystemExit("invalid campaign or first-wave size")
    import ray
    ray.init(address=args.address,
             resources={"rtl_sim_cpu": 4.0} if args.address is None else None,
             ignore_reinit_error=True)
    run_id = f"phase6-local-{uuid.uuid4().hex[:12]}"
    history = load_history()
    outputs = []
    remaining = args.count
    iteration = 1
    while remaining:
        wave = min(args.first_wave if iteration == 1 else remaining, remaining)
        before = len(history)
        history, output = run_wave(history, wave, iteration, run_id)
        outputs.append(output)
        completed = len(history) - before
        if completed <= 0:
            raise RuntimeError("agent proposed no new experiments")
        remaining -= completed
        iteration += 1
    state = outputs[-1]["state"]
    manifest = {
        "schema_version": "chia-rdo.phase6-manifest.v1", "created_utc": utc_now(),
        "chia_run_id": run_id, "orchestration": "native asynchronous ChiaFunction graph",
        "requested_new_experiments": args.count,
        "completed_new_experiments": sum(len(output["proposal_batch"]["proposals"]) for output in outputs),
        "history_experiments": len(history),
        "campaign_experiment_ids": sorted(row["experiment_id"] for row in history),
        "iterations": [{"iteration": output["proposal_batch"]["iteration"],
                        "history_count_consumed": output["proposal_batch"]["history_count_consumed"],
                        "history_digest": output["proposal_batch"]["history_digest"],
                        "experiment_ids": [row["experiment_id"] for row in output["proposal_batch"]["proposals"]]}
                       for output in outputs],
        "tracks": {"A": "frozen-policy hardware DSE", "B": "versioned hardware-aware policy DSE"},
        "frozen_reference": FROZEN_POLICY,
        "phase5_3_evidence": {"path": str(PHASE5_RTL.relative_to(ROOT)), "sha256": digest(PHASE5_RTL)},
        "execution_backend": "local", "gcp_launch_allowed": False,
        "gcp_block_reason": "verified spend and remaining promotional credit unavailable",
        "pareto_points": len(state["pareto"]), "model_rtl_error": state["model_rtl_error"],
    }
    atomic_json(ROOT / "experiments/phase6_manifest.json", manifest)
    atomic_json(SUMMARY_ROOT / f"{run_id}.json", {"manifest": manifest, "state": state})
    print(json.dumps(manifest, indent=2, sort_keys=True))
    ray.shutdown()


if __name__ == "__main__":
    main()
