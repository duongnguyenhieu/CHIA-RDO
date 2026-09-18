#!/usr/bin/env python3
"""Lock Phase-6 evidence and derive Phase-7 Vivado candidates."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(path: Path) -> tuple[str, int]:
    rows = [(str(item.relative_to(ROOT)), sha256(item)) for item in sorted(path.glob("*.json"))]
    encoded = json.dumps(rows, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest(), len(rows)


def main() -> None:
    output = ROOT / "results/phase7"
    output.mkdir(parents=True, exist_ok=True)
    pareto_path = ROOT / "results/phase6/pareto/policy_pareto.json"
    pareto = json.loads(pareto_path.read_text())["points"]
    experiment_digest, experiment_count = tree_digest(ROOT / "results/phase6/experiments")
    hm_digest, hm_count = tree_digest(ROOT / "results/phase6/hm_experiments")
    paths = [
        "experiments/phase6_manifest.json",
        "results/phase6/summaries/local_dse.json",
        "results/phase6/pareto/policy_pareto.json",
        "results/phase6/rtl_k_levels.json",
        "reports/phase6_gate.md",
        "reports/phase6_dse.md",
        "reports/phase6_pareto.md",
        "reports/phase6_model_correlation.md",
    ]
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lock = {
        "schema_version": "chia-rdo.phase7-state-lock.v1", "created_utc": now,
        "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                     stdout=subprocess.PIPE, check=True).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True,
                                         stdout=subprocess.PIPE, check=True).stdout.strip()),
        "phase6_artifacts": {path: sha256(ROOT / path) for path in paths},
        "phase6_experiments_tree_sha256": experiment_digest,
        "phase6_experiment_file_count": experiment_count,
        "phase6_hm_tree_sha256": hm_digest,
        "phase6_hm_file_count": hm_count,
    }
    (output / "state_lock.json").write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")

    builds = {}
    candidates = []
    for row in pareto:
        hardware = row["hardware_configuration"]
        build_id = f"p{hardware['p']}-d{hardware['pipeline_depth']}-b{hardware['buffer_depth']}-w{hardware['cost_width']}"
        builds.setdefault(build_id, {
            "build_id": build_id, "p": hardware["p"], "pipeline_depth": hardware["pipeline_depth"],
            "buffer_depth": hardware["buffer_depth"], "cost_width": hardware["cost_width"],
            "scheduler_architecture": hardware["scheduler_architecture"],
            "source_experiment_ids": [],
        })["source_experiment_ids"].append(row["experiment_id"])
        candidates.append({
            "experiment_id": row["experiment_id"], "policy_id": row["policy_id"],
            "policy_version": row["policy_version"], "build_id": build_id,
            "hardware_configuration": hardware, "k": "adaptive_or_fixed_policy_distribution",
            "average_k": row["average_k"], "rtl_cycles_per_event": row["rtl_cycles_per_event"],
            "rtl_metrics_status": row["rtl_metrics_status"], "bd_rate_percent": row["bd_rate_percent"],
            "rdo_reduction": row["rdo_reduction"], "winner_retention": row["winner_retention"],
            "resource_proxy": row["resource_proxy"], "balanced_score": row["balanced_score"],
        })
    payload = {
        "schema_version": "chia-rdo.phase7-vivado-candidates.v1", "created_utc": now,
        "source_pareto": str(pareto_path.relative_to(ROOT)), "source_pareto_sha256": sha256(pareto_path),
        "candidate_count": len(candidates), "unique_vivado_build_count": len(builds),
        "candidates": candidates, "vivado_builds": sorted(builds.values(), key=lambda row: row["p"]),
        "selection_reason": "All non-dominated Phase-6 policy points; identical hardware configurations share one Vivado implementation.",
    }
    (output / "vivado_candidates.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    report = f"""# Phase 7 Initial State

- Phase-6 state lock: `results/phase7/state_lock.json`
- Phase-6 experiment checkpoints: **{experiment_count}** hardware + **{hm_count}** HM curves
- Phase-6 Pareto points: **{len(candidates)}**
- Unique selected hardware builds: **{len(builds)}**
- Git worktree dirty at lock: **{lock['git_dirty']}**
- Target: `xck26-sfvc784-2LV-c`, 5 ns, Vivado 2024.2

Phase-6 files are inputs only and must not be overwritten by Phase 7.
"""
    (ROOT / "reports/phase7_initial_state.md").write_text(report)
    selection = "# Phase 7 Candidate Selection\n\n"
    selection += f"Selected all **{len(candidates)}** non-dominated policy points from the actual Phase-6 database. "
    selection += f"They map to **{len(builds)}** unique hardware implementations.\n\n"
    selection += "| Build | P | Pipeline | Buffer | Width | Source points |\n|---|---:|---:|---:|---:|---:|\n"
    for build in sorted(builds.values(), key=lambda row: row["p"]):
        selection += (f"| `{build['build_id']}` | {build['p']} | {build['pipeline_depth']} | "
                      f"{build['buffer_depth']} | {build['cost_width']} | {len(build['source_experiment_ids'])} |\n")
    selection += "\nNo dominated hardware configuration was added. Resource proxies remain estimated until implementation.\n"
    (ROOT / "reports/phase7_candidate_selection.md").write_text(selection)
    print(json.dumps({"state_lock": "results/phase7/state_lock.json", "pareto_candidates": len(candidates),
                      "unique_vivado_builds": len(builds)}, indent=2))


if __name__ == "__main__":
    main()
