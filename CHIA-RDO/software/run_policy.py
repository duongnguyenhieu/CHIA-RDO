#!/usr/bin/env python3
"""Run a fixed or adaptive candidate-budget policy against the Phase 1 reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import socket
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generate_sequence import TINY64_SHA256, write_sequence
from run_baseline import (
    DECODER,
    ENCODER,
    HM_REVISION,
    PRESET,
    ROOT,
    encoder_argv,
    git_output,
    parse_hm_log,
    run_process,
    sha256_file,
)
from policy_algorithms import (
    HardwareState,
    estimate_cycles,
    normalized_best_rough_cost,
    relative_satd_values,
    select_adaptive_hw_v1_k,
    select_adaptive_threshold_k,
    select_relative_satd_k,
)


EVENT_KEY = (
    "poc", "ctu_rs_addr", "cu_x", "cu_y", "cu_width", "cu_height", "cu_depth",
    "pu_part_offset", "pu_x", "pu_y", "pu_width", "pu_height", "qp",
)
K_LEVELS = (2, 4, 8, 16, 35)


def select_adaptive_k(
    confidence: float,
    medium_threshold: float = 0.045,
    high_threshold: float = 0.088,
    high_k: int = 4,
    medium_k: int = 8,
    low_k: int = 16,
) -> int:
    if not math.isfinite(confidence) or confidence < 0:
        raise ValueError("confidence must be finite and nonnegative")
    if not 0 <= medium_threshold <= high_threshold:
        raise ValueError("thresholds must satisfy 0 <= medium <= high")
    if any(k not in K_LEVELS for k in (high_k, medium_k, low_k)):
        raise ValueError(f"K levels must belong to {K_LEVELS}")
    if confidence >= high_threshold:
        return high_k
    if confidence >= medium_threshold:
        return medium_k
    return low_k


def hardware_fill_k(k: int, parallelism: int) -> int:
    if parallelism not in (1, 2, 4, 8):
        raise ValueError("parallelism must be one of 1,2,4,8")
    batches = math.ceil(k / parallelism)
    return max(level for level in K_LEVELS if math.ceil(level / parallelism) <= batches)


def policy_environment(policy: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("CHIA_RDO_") and key not in {"CHIA_RDO_CLOUD_BACKEND"}:
            del env[key]
    env["LC_ALL"] = "C"
    env["CHIA_RDO_POLICY"] = policy["name"]
    if policy["name"] == "full":
        env["CHIA_RDO_POLICY"] = "exhaustive"
    elif policy["name"] == "fixed":
        k = policy["k"]
        if k not in K_LEVELS:
            raise ValueError(f"fixed K must belong to {K_LEVELS}")
        env["CHIA_RDO_FIXED_K"] = str(k)
    elif policy["name"] in {"adaptive_v0", "adaptive_hw"}:
        select_adaptive_k(
            0.0, policy["medium_threshold"], policy["high_threshold"],
            policy["high_k"], policy["medium_k"], policy["low_k"],
        )
        env.update({
            "CHIA_RDO_MEDIUM_THRESHOLD": str(policy["medium_threshold"]),
            "CHIA_RDO_HIGH_THRESHOLD": str(policy["high_threshold"]),
            "CHIA_RDO_HIGH_K": str(policy["high_k"]),
            "CHIA_RDO_MEDIUM_K": str(policy["medium_k"]),
            "CHIA_RDO_LOW_K": str(policy["low_k"]),
        })
        if policy["name"] == "adaptive_hw":
            hardware_fill_k(policy["high_k"], policy["parallelism"])
            env["CHIA_RDO_P"] = str(policy["parallelism"])
    elif policy["name"] == "adaptive_threshold":
        select_adaptive_threshold_k(
            0.0, policy["easy_threshold"], policy["hard_threshold"],
            policy["easy_k"], policy["medium_k"], policy["hard_k"],
        )
        env.update({
            "CHIA_RDO_EASY_ROUGH_THRESHOLD": str(policy["easy_threshold"]),
            "CHIA_RDO_HARD_ROUGH_THRESHOLD": str(policy["hard_threshold"]),
            "CHIA_RDO_EASY_K": str(policy["easy_k"]),
            "CHIA_RDO_MEDIUM_K": str(policy["medium_k"]),
            "CHIA_RDO_HARD_K": str(policy["hard_k"]),
        })
    elif policy["name"] == "relative_satd":
        select_relative_satd_k([0] * 35, policy["relative_threshold"], policy["minimum_k"], policy["maximum_k"])
        env.update({
            "CHIA_RDO_RELATIVE_SATD_THRESHOLD": str(policy["relative_threshold"]),
            "CHIA_RDO_MIN_K": str(policy["minimum_k"]),
            "CHIA_RDO_MAX_K": str(policy["maximum_k"]),
        })
    elif policy["name"] == "adaptive_hw_v1":
        state = HardwareState(**policy["hardware_state"])
        select_adaptive_hw_v1_k(
            confidence=0.0, relative_satd_count=1, activity_norm=0.0,
            normalized_rough_cost=0.0, qp=32, block_area=16, state=state,
            **policy["weights"],
        )
        env.update({
            "CHIA_RDO_P": str(state.parallelism),
            "CHIA_RDO_RELATIVE_SATD_THRESHOLD": str(policy["relative_threshold"]),
            "CHIA_RDO_HW_GAP_SCALE": str(policy["weights"]["gap_scale"]),
            "CHIA_RDO_HW_RELATIVE_SATD_SCALE": str(policy["weights"]["relative_satd_scale"]),
            "CHIA_RDO_HW_QUALITY_WEIGHT": str(policy["weights"]["quality_weight"]),
            "CHIA_RDO_HW_CYCLE_WEIGHT": str(policy["weights"]["cycle_weight"]),
            "CHIA_RDO_HW_WASTE_WEIGHT": str(policy["weights"]["waste_weight"]),
            "CHIA_RDO_PIPELINE_FILL": str(state.pipeline_fill_cycles),
            "CHIA_RDO_PIPELINE_DRAIN": str(state.pipeline_drain_cycles),
            "CHIA_RDO_RDO_CYCLES": str(state.rdo_cycles_per_batch),
            "CHIA_RDO_BATCH_OVERHEAD": str(state.batch_overhead_cycles),
        })
    else:
        raise ValueError(f"unsupported policy {policy['name']}")
    return env


def load_policy_trace(path: Path, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            row = json.loads(line)
            k = row.get("selected_k")
            ranking = row.get("ranked_modes", [])
            if row.get("trace_schema") != "chia-rdo.policy-trace.v1":
                raise RuntimeError(f"line {line_number}: wrong policy trace schema")
            if row.get("policy") != policy["name"] or row.get("ranking_count") != 35:
                raise RuntimeError(f"line {line_number}: policy or ranking count mismatch")
            if sorted(ranking) != list(range(35)):
                raise RuntimeError(f"line {line_number}: invalid ranking")
            if row.get("evaluated_modes") != ranking[:k]:
                raise RuntimeError(f"line {line_number}: evaluated modes are not the ranked prefix")
            if row.get("candidate_count") != k or row.get("rdo_candidate_evaluations") != k:
                raise RuntimeError(f"line {line_number}: evaluation count mismatch")
            if len(row.get("rd_cost_by_rank", [])) != k or row.get("best_mode") not in ranking[:k]:
                raise RuntimeError(f"line {line_number}: invalid RD result")
            if policy["name"] == "fixed" and k != policy["k"]:
                raise RuntimeError(f"line {line_number}: fixed-K decision mismatch")
            if policy["name"] in {"adaptive_v0", "adaptive_hw"}:
                base_k = select_adaptive_k(
                    row["confidence"], policy["medium_threshold"], policy["high_threshold"],
                    policy["high_k"], policy["medium_k"], policy["low_k"],
                )
                expected = hardware_fill_k(base_k, policy["parallelism"]) if policy["name"] == "adaptive_hw" else base_k
                if k != expected:
                    raise RuntimeError(f"line {line_number}: adaptive decision mismatch")
                if policy["name"] == "adaptive_hw" and (
                    row.get("base_k") != base_k or row.get("parallelism_p") != policy["parallelism"]
                    or row.get("batch_count") != math.ceil(k / policy["parallelism"])
                    or row.get("hardware_evaluated_modes") != ranking[:k]
                ):
                    raise RuntimeError(f"line {line_number}: hardware policy telemetry mismatch")
            if policy["name"] == "adaptive_threshold":
                expected = select_adaptive_threshold_k(
                    row["normalized_best_rough_cost"], policy["easy_threshold"],
                    policy["hard_threshold"], policy["easy_k"], policy["medium_k"], policy["hard_k"],
                )
                if k != expected:
                    raise RuntimeError(f"line {line_number}: adaptive-threshold decision mismatch")
            if policy["name"] == "relative_satd":
                expected = select_relative_satd_k(
                    row["satd_by_mode"], policy["relative_threshold"],
                    policy["minimum_k"], policy["maximum_k"],
                )
                if k != expected:
                    raise RuntimeError(f"line {line_number}: relative-SATD decision mismatch")
            if policy["name"] == "adaptive_hw_v1":
                state = HardwareState(**policy["hardware_state"])
                expected, details = select_adaptive_hw_v1_k(
                    confidence=row["confidence"], relative_satd_count=row["relative_satd_count"],
                    activity_norm=row["activity_norm"],
                    normalized_rough_cost=row["normalized_best_rough_cost"], qp=row["qp"],
                    block_area=row["pu_width"] * row["pu_height"], state=state,
                    **policy["weights"],
                )
                model = estimate_cycles(k, state)
                if (k != expected or row.get("batch_count") != model["batches"]
                        or row.get("estimated_cycles") != model["estimated_cycles"]
                        or row.get("hardware_evaluated_modes") != ranking[:k]
                        or not math.isclose(row.get("policy_difficulty", -1), details["difficulty"], rel_tol=1e-12)):
                    raise RuntimeError(f"line {line_number}: adaptive-hardware-v1 decision mismatch")
            rows.append(row)
    if not rows:
        raise RuntimeError("policy trace contains no events")
    counts = [row["selected_k"] for row in rows]
    summary = {
        "search_calls": len(rows),
        "rdo_evaluations": sum(counts),
        "rqt_refinement_evaluations": sum(row["rqt_refinement_evaluations"] for row in rows),
        "average_k": sum(counts) / len(counts),
        "minimum_k": min(counts),
        "maximum_k": max(counts),
        "k_histogram": {str(k): Counter(counts)[k] for k in K_LEVELS},
        "average_batches_by_p": {
            str(p): sum(math.ceil(k / p) for k in counts) / len(counts) for p in (1, 2, 4, 8)
        },
    }
    if policy["name"] == "adaptive_hw_v1":
        summary.update({
            "average_estimated_cycles": sum(row["estimated_cycles"] for row in rows) / len(rows),
            "total_estimated_cycles": sum(row["estimated_cycles"] for row in rows),
            "average_modeled_lane_utilization": sum(
                row["selected_k"] / (row["batch_count"] * policy["hardware_state"]["parallelism"])
                for row in rows
            ) / len(rows),
        })
    return rows, summary


def find_reference(config: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    matches = []
    for path in (ROOT / "results/baseline").glob("*/result.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        stored = record.get("configuration", {})
        if (record.get("status") == "success" and (path.parent / "intra-rdo.jsonl").is_file()
                and stored.get("qp") == config.get("qp")
                and stored.get("frame_rate_hz") == config.get("frame_rate_hz")
                and stored.get("sequence") == config.get("sequence")):
            matches.append((record.get("execution", {}).get("replicate") is not None, path.parent, record))
    if not matches:
        raise RuntimeError("no matched Full-RDO reference; run software/run_baseline.py with this config first")
    _, directory, record = sorted(matches, key=lambda item: (item[0], item[1].name))[0]
    return directory, record


def compare_reference(
    policy_rows: list[dict[str, Any]], output_path: Path, reference_dir: Path
) -> dict[str, Any]:
    reference: dict[tuple[Any, ...], dict[str, Any]] = {}
    with (reference_dir / "intra-rdo.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            reference[tuple(row[key] for key in EVENT_KEY)] = row
    matched = retained = same_winner = 0
    with output_path.open("w", encoding="utf-8") as output:
        for row in policy_rows:
            key = tuple(row[name] for name in EVENT_KEY)
            full = reference.get(key)
            if full is None:
                continue
            matched += 1
            hit = full["best_mode"] in row["evaluated_modes"]
            retained += hit
            same_winner += full["best_mode"] == row["best_mode"]
            record = {
                **{name: row[name] for name in EVENT_KEY},
                "selected_k": row["selected_k"],
                "confidence": row["confidence"],
                "evaluated_modes": row["evaluated_modes"],
                "policy_selected_mode": row["best_mode"],
                "full_rdo_winner": full["best_mode"],
                "full_rdo_winner_reference_rank": full["ranked_modes"].index(full["best_mode"]) + 1,
                "full_rdo_winner_current_rank": row["ranked_modes"].index(full["best_mode"]) + 1,
                "full_rdo_winner_retained": hit,
                "same_selected_mode": full["best_mode"] == row["best_mode"],
            }
            output.write(json.dumps(record, sort_keys=True) + "\n")
    return {
        "reference_events": len(reference),
        "policy_events": len(policy_rows),
        "matched_events": matched,
        "match_rate": matched / len(policy_rows),
        "winner_retained_events": retained,
        "winner_retention_rate": retained / matched if matched else None,
        "same_winner_events": same_winner,
        "same_winner_rate": same_winner / matched if matched else None,
        "qualification": "Matched by structural event identity across independent encodes; prior pruning can change coding state.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", choices=("full", "fixed", "adaptive_v0", "adaptive_hw", "adaptive_threshold", "relative_satd", "adaptive_hw_v1"), default="full")
    parser.add_argument("--k", type=int)
    parser.add_argument("--medium-threshold", type=float, default=0.045)
    parser.add_argument("--high-threshold", type=float, default=0.088)
    parser.add_argument("--high-k", type=int, default=4)
    parser.add_argument("--medium-k", type=int, default=8)
    parser.add_argument("--low-k", type=int, default=16)
    parser.add_argument("--p", type=int, choices=(1, 2, 4, 8))
    parser.add_argument("--easy-threshold", type=float, default=0.08)
    parser.add_argument("--hard-threshold", type=float, default=0.20)
    parser.add_argument("--easy-k", type=int, default=4)
    parser.add_argument("--hard-k", type=int, default=16)
    parser.add_argument("--relative-threshold", type=float, default=0.15)
    parser.add_argument("--minimum-k", type=int, default=4)
    parser.add_argument("--maximum-k", type=int, default=35)
    parser.add_argument("--gap-scale", type=float, default=0.10)
    parser.add_argument("--relative-satd-scale", type=float, default=8.0)
    parser.add_argument("--quality-weight", type=float, default=1.0)
    parser.add_argument("--cycle-weight", type=float, default=0.30)
    parser.add_argument("--waste-weight", type=float, default=0.05)
    parser.add_argument("--pipeline-fill", type=int, default=3)
    parser.add_argument("--pipeline-drain", type=int, default=2)
    parser.add_argument("--rdo-cycles", type=int, default=8)
    parser.add_argument("--batch-overhead", type=int, default=1)
    parser.add_argument("--replicate")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/baseline_smoke.json")
    args = parser.parse_args()
    if args.policy == "full":
        subprocess.run([sys.executable, str(ROOT / "software/run_baseline.py"), "--config", str(args.config)],
                       cwd=ROOT, check=True)
        return
    if args.policy == "fixed" and args.k is None:
        parser.error("--k is required for fixed policy")
    if args.policy in {"adaptive_hw", "adaptive_hw_v1"} and args.p is None:
        parser.error("--p is required for hardware-aware policies")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.policy == "fixed":
        policy = {"name": "fixed", "version": "fixed-k.v1", "k": args.k}
    elif args.policy in {"adaptive_v0", "adaptive_hw"}:
        policy = {"name": args.policy, "version": "adaptive-v0.v1" if args.policy == "adaptive_v0" else "adaptive-hw-batch-fill.v1",
                  "medium_threshold": args.medium_threshold, "high_threshold": args.high_threshold,
                  "high_k": args.high_k, "medium_k": args.medium_k, "low_k": args.low_k}
    elif args.policy == "adaptive_threshold":
        policy = {"name": args.policy, "version": "adaptive-threshold.v1",
                  "easy_threshold": args.easy_threshold, "hard_threshold": args.hard_threshold,
                  "easy_k": args.easy_k, "medium_k": args.medium_k, "hard_k": args.hard_k}
    elif args.policy == "relative_satd":
        policy = {"name": args.policy, "version": "relative-satd.v1",
                  "relative_threshold": args.relative_threshold,
                  "minimum_k": args.minimum_k, "maximum_k": args.maximum_k}
    else:
        policy = {"name": args.policy, "version": "adaptive-hw-v1.analytical-cost.v1",
                  "relative_threshold": args.relative_threshold,
                  "hardware_state": {"parallelism": args.p, "pipeline_fill_cycles": args.pipeline_fill,
                                     "pipeline_drain_cycles": args.pipeline_drain,
                                     "rdo_cycles_per_batch": args.rdo_cycles,
                                     "batch_overhead_cycles": args.batch_overhead,
                                     "current_batch_position": 0, "pending_batches": 0},
                  "weights": {"gap_scale": args.gap_scale, "relative_satd_scale": args.relative_satd_scale,
                              "quality_weight": args.quality_weight, "cycle_weight": args.cycle_weight,
                              "waste_weight": args.waste_weight}}
    if args.policy == "adaptive_hw":
        policy["parallelism"] = args.p
    env = policy_environment(policy)
    patch_path = ROOT / "software/patches/hm-16.20-chia-rdo.patch"
    phase2_patch_path = ROOT / "software/patches/hm-16.20-phase2-k-policy.patch"
    hardware_patch_path = ROOT / "software/patches/hm-16.20-phase2-hardware-policy.patch"
    phase3_patch_path = ROOT / "software/patches/hm-16.20-phase3-algorithms.patch"
    patch_hashes = {"phase1": sha256_file(patch_path), "phase2": sha256_file(phase2_patch_path),
                     "hardware_policy": sha256_file(hardware_patch_path),
                     "phase3_algorithms": sha256_file(phase3_patch_path)}
    identity = {"config": config, "policy": policy, "hm_revision": HM_REVISION,
                "patch_sha256": patch_hashes, "policy_runner_version": 1}
    if args.replicate:
        identity["replicate"] = args.replicate
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    label = f"fixed-k{args.k}" if args.policy == "fixed" else (
        f"{args.policy.replace('_', '-')}-p{args.p}" if args.policy in {"adaptive_hw", "adaptive_hw_v1"}
        else args.policy.replace("_", "-"))
    experiment_id = f"{config['name']}-{label}-{digest[:12]}"
    output_dir = ROOT / "results/policy" / experiment_id
    log_dir = ROOT / "logs/policy" / experiment_id
    result_path = output_dir / "result.json"
    if result_path.exists():
        existing = json.loads(result_path.read_text())
        if existing.get("identity") == identity and existing.get("status") == "success":
            print(f"cache hit: {experiment_id}")
            return
        raise RuntimeError(f"stale or unsuccessful result exists: {result_path}")
    # A failed remote attempt may leave an incomplete directory. Reuse that
    # checkpoint location so a retry keeps the same logical experiment ID.
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    sequence = config["sequence"]
    input_path = ROOT / "datasets/generated" / f"{sequence['name']}.yuv"
    input_hash = write_sequence(
        input_path, sequence["width"], sequence["height"], sequence["frames"], sequence["generator"]
    )
    if sequence.get("expected_sha256") and input_hash != sequence["expected_sha256"]:
        raise RuntimeError(f"generated input hash does not match the locked corpus: {input_hash}")
    if sequence["name"] == "tiny-64x64-4f-yuv420p8" and input_hash != TINY64_SHA256:
        raise RuntimeError("generated input hash mismatch")

    measure_bitstream = output_dir / "measure.bin"
    measure_recon = output_dir / "measure-recon.yuv"
    argv = encoder_argv(config, input_path, measure_bitstream, measure_recon)
    measure_wall, measure_log = run_process(argv, env, log_dir / "measure.log")
    metrics = parse_hm_log(measure_log, sequence["frames"])
    trace_path = output_dir / "intra-rdo.jsonl"
    trace_env = dict(env)
    trace_env["CHIA_RDO_TRACE"] = str(trace_path)
    trace_bitstream = output_dir / "trace.bin"
    trace_recon = output_dir / "trace-recon.yuv"
    trace_argv = encoder_argv(config, input_path, trace_bitstream, trace_recon)
    trace_wall, trace_log = run_process(trace_argv, trace_env, log_dir / "trace.log")
    trace_metrics = parse_hm_log(trace_log, sequence["frames"])
    if {k: v for k, v in metrics.items() if k != "hm_cpu_time_seconds"} != {
        k: v for k, v in trace_metrics.items() if k != "hm_cpu_time_seconds"
    }:
        raise RuntimeError("trace pass changed coding metrics")
    if sha256_file(measure_bitstream) != sha256_file(trace_bitstream) or sha256_file(measure_recon) != sha256_file(trace_recon):
        raise RuntimeError("trace pass changed bitstream or reconstruction")
    rows, trace_summary = load_policy_trace(trace_path, policy)
    reference_dir, reference_result = find_reference(config)
    comparison_path = output_dir / "reference-comparison.jsonl"
    reference_comparison = compare_reference(rows, comparison_path, reference_dir)
    decoded = output_dir / "decoded.yuv"
    run_process([str(DECODER), "-b", str(measure_bitstream), "-o", str(decoded)], env, log_dir / "decode.log")
    if sha256_file(decoded) != sha256_file(measure_recon):
        raise RuntimeError("decoder output differs from reconstruction")
    reference_metrics = reference_result["metrics"]
    hm_cpu_time = metrics.pop("hm_cpu_time_seconds")
    metrics.update(trace_summary)
    metrics.update({
        "rdo_reduction_fraction": 1 - metrics["rdo_evaluations"] / reference_metrics["rdo_evaluations"],
        "bitrate_delta_percent": 100 * (metrics["annex_b_kbps"] / reference_metrics["annex_b_kbps"] - 1),
        "psnr_y_delta_db": metrics["psnr_y_db"] - reference_metrics["psnr_y_db"],
        "psnr_u_delta_db": metrics["psnr_u_db"] - reference_metrics["psnr_u_db"],
        "psnr_v_delta_db": metrics["psnr_v_db"] - reference_metrics["psnr_v_db"],
        "psnr_yuv_delta_db": metrics["psnr_yuv_db"] - reference_metrics["psnr_yuv_db"],
        "bd_rate_percent": None,
        **reference_comparison,
    })
    record = {
        "schema_version": "chia-rdo.policy-result.v1", "status": "success",
        "experiment_id": experiment_id, "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "identity": identity, "policy": policy,
        "reference_experiment_id": reference_result["experiment_id"],
        "git_commit": git_output("rev-parse", "HEAD"), "git_worktree_dirty": bool(git_output("status", "--porcelain")),
        "encoder": {"name": "HM", "version": "16.20", "revision": HM_REVISION,
                    "patch_sha256": patch_hashes, "binary_sha256": sha256_file(ENCODER),
                    "preset_sha256": sha256_file(PRESET)},
        "configuration": config, "sequence": {**sequence, "sha256": input_hash},
        "execution": {"host": socket.gethostname(), "platform": platform.platform(),
                      "replicate": args.replicate,
                      "wall_time_seconds": measure_wall, "trace_wall_time_seconds": trace_wall,
                      "hm_cpu_time_seconds": hm_cpu_time, "cloud_backend": os.environ.get("CHIA_RDO_CLOUD_BACKEND"),
                      "cloud_cost_usd": None if os.environ.get("CHIA_RDO_CLOUD_BACKEND") else 0.0},
        "metrics": metrics,
        "artifacts": {"trace": str(trace_path.relative_to(ROOT)),
                      "reference_comparison": str(comparison_path.relative_to(ROOT)),
                      "bitstream_sha256": sha256_file(measure_bitstream),
                      "reconstruction_sha256": sha256_file(measure_recon),
                      "trace_sha256": sha256_file(trace_path)},
    }
    result_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(result_path.relative_to(ROOT))
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
