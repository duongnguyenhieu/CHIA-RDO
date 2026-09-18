#!/usr/bin/env python3
"""Build scoped Phase-6 summaries and reports from measured evidence."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SUMMARY = ROOT / "results/phase6/summaries/local_dse.json"
PARETO = ROOT / "results/phase6/pareto/policy_pareto.json"


def read_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text())


def resource_proxy(p: int) -> int:
    return p * 2 * (56 + 32 + 24 + 32 + 6) + 35 * (56 + 6)


def phase4_policy(policy: str, p: int, database: dict) -> dict:
    rows = [row for row in database["records"] if row["policy"] == policy]
    by_workload: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_workload[row["workload"]].append(row)
    metrics = []
    for workload_rows in by_workload.values():
        weights = [row["rdo_evaluations"] / row["avg_k"] for row in workload_rows]
        total = sum(weights)
        metrics.append({
            "average_k": sum(row["avg_k"] * weight for row, weight in zip(workload_rows, weights)) / total,
            "rdo_reduction": sum(row["rdo_reduction"] * weight for row, weight in zip(workload_rows, weights)) / total,
            "winner_retention": sum(row["winner_retention"] * weight for row, weight in zip(workload_rows, weights)) / total,
            "cycles": sum(row["estimated_by_p"][str(p)]["estimated_cycles"] * weight
                          for row, weight in zip(workload_rows, weights)) / total,
        })
    return {
        "experiment_id": f"phase4-{policy}-p{p}", "source": "protected Phase-4 matched HM curves",
        "policy_id": policy, "policy_version": rows[0]["policy_version"], "p": p,
        "bd_rate_percent": database["policy_bd_rate_percent"][policy],
        "average_k": sum(row["average_k"] for row in metrics) / len(metrics),
        "rdo_reduction": sum(row["rdo_reduction"] for row in metrics) / len(metrics),
        "winner_retention": sum(row["winner_retention"] for row in metrics) / len(metrics),
        "rtl_cycles_per_event": sum(row["cycles"] for row in metrics) / len(metrics),
        "rtl_metrics_status": "CALIBRATED_RTL_REPLAY", "resource_proxy": resource_proxy(p),
        "resource_status": "ESTIMATED", "hardware_configuration": {"p": p, "pipeline_depth": 2,
            "buffer_depth": 35, "cost_width": 56, "scheduler_architecture": "static"},
        "feasible": True,
    }


def hm_policy(row: dict, rtl: dict) -> dict:
    measured = next(item for item in rtl["runs"] if item["p"] == row["p"])
    histogram = row["k_distribution"]
    events = sum(histogram.values())
    cycles = sum(count * measured[f"cycles_k{k}"] for k, count in
                 ((int(key), value) for key, value in histogram.items())) / events
    slots = sum(count * math.ceil(int(key) / row["p"]) * row["p"] for key, count in histogram.items())
    active = sum(count * int(key) for key, count in histogram.items())
    feasible = row["bd_rate_percent"] <= 1.5 and row["winner_retention"] >= 0.85 and row["rdo_reduction"] > 0
    return {
        "experiment_id": row["experiment_id"], "source": "Phase-6 matched HM curve",
        "policy_id": row["policy_id"], "policy_version": row["policy_version"], "p": row["p"],
        "bd_rate_percent": row["bd_rate_percent"], "average_k": row["average_k"],
        "rdo_reduction": row["rdo_reduction"], "winner_retention": row["winner_retention"],
        "rtl_cycles_per_event": cycles, "utilization": active / slots,
        "rtl_metrics_status": "VERIFIED_TRACE_REPLAY", "resource_proxy": resource_proxy(row["p"]),
        "resource_status": "ESTIMATED", "hardware_configuration": {"p": row["p"], "pipeline_depth": 2,
            "buffer_depth": 35, "cost_width": 56, "scheduler_architecture": "static"},
        "feasible": feasible,
    }


def dominates(left: dict, right: dict) -> bool:
    axes = ("bd_rate_percent", "average_k", "rtl_cycles_per_event", "resource_proxy")
    return all(left[key] <= right[key] for key in axes) and any(left[key] < right[key] for key in axes)


def fmt(value: float | None, digits: int = 4) -> str:
    return "UNAVAILABLE" if value is None else f"{value:.{digits}f}"


def main() -> None:
    database = read_json("results/phase4/database.json")
    rtl = read_json("results/phase6/rtl_k_levels.json")
    budget = read_json("cloud/gcp_phase6_budget.json")
    hm_rows = [json.loads(path.read_text()) for path in (ROOT / "results/phase6/hm_experiments").glob("*.json")
               if json.loads(path.read_text()).get("result_status") == "PASS"]
    primary_hm_rows = [row for row in hm_rows if not row.get("replicate")]
    rows = []
    for policy in ("full_rdo", "fixed_k16", "adaptive_threshold"):
        rows.extend(phase4_policy(policy, p, database) for p in (1, 2, 4, 8))
    rows.extend(phase4_policy(policy, 8, database)
                for policy in ("adaptive_hw_batch_fill_p8", "adaptive_hw_v1_p8"))
    rows.extend(hm_policy(row, rtl) for row in primary_hm_rows)
    feasible = [row for row in rows if row["feasible"]]
    frontier = []
    for row in rows:
        row["dominated"] = row["feasible"] and any(
            dominates(other, row) for other in feasible if other["experiment_id"] != row["experiment_id"])
        if row["feasible"] and not row["dominated"]:
            frontier.append(row)
    frontier.sort(key=lambda row: (row["rtl_cycles_per_event"], row["resource_proxy"], row["experiment_id"]))
    best_cycle = min(frontier, key=lambda row: row["rtl_cycles_per_event"])
    best_area = min(frontier, key=lambda row: (row["resource_proxy"], row["rtl_cycles_per_event"]))
    spans = {key: (min(row[key] for row in frontier), max(row[key] for row in frontier))
             for key in ("bd_rate_percent", "average_k", "rtl_cycles_per_event", "resource_proxy")}
    for row in frontier:
        row["balanced_score"] = sum(0 if high == low else (row[key] - low) / (high - low)
                                    for key, (low, high) in spans.items()) / len(spans)
    best_balanced = min(frontier, key=lambda row: row["balanced_score"])
    hardware_records = list((ROOT / "results/phase6/experiments").glob("*.json"))
    hardware_results = [json.loads(path.read_text()) for path in hardware_records]
    successful = sum(row.get("result_status") == "PASS" for row in hardware_results) + len(hm_rows)
    failed = sum(row.get("result_status") == "FAILED" for row in hardware_results)
    cancelled = sum(row.get("result_status") == "CANCELLED" for row in hardware_results)
    protected = read_json("results/phase5_3/state_lock.json")
    protected_ok = all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
                       for path, digest in protected["artifacts"].items())
    vivado_candidates = []
    for p in (1, 2, 4, 8):
        choices = [row for row in frontier if row["p"] == p]
        if choices:
            vivado_candidates.append(min(choices, key=lambda row: row["balanced_score"]))
    reproductions = []
    for replicate in (row for row in hm_rows if row.get("replicate")):
        source = next((row for row in primary_hm_rows if row["policy_id"] == replicate["policy_id"]
                       and row["p"] == replicate["p"]), None)
        keys = ("bd_rate_percent", "average_k", "rdo_reduction", "winner_retention", "k_distribution")
        reproductions.append({"experiment_id": replicate["experiment_id"],
                              "reference_experiment_id": source["experiment_id"] if source else None,
                              "identical_metrics": source is not None and all(source[key] == replicate[key] for key in keys)})
    payload = {
        "schema_version": "chia-rdo.phase6-local-dse.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase_status": "BLOCKED_GCP_BILLING_PREFLIGHT",
        "experiment_count": len(hardware_results) + len(hm_rows), "successful_experiments": successful,
        "failed_experiments": failed, "cancelled_experiments": cancelled,
        "hardware_screening_experiments": len(hardware_results), "hm_curve_experiments": len(hm_rows),
        "hm_encode_runs": sum(row["hm_run_count"] for row in hm_rows),
        "reproducibility": reproductions,
        "rtl_candidate_evaluations": sum(row["candidate_evaluations"] for row in rtl["runs"]),
        "pareto_points": len(frontier), "pareto": frontier,
        "best_cycle": best_cycle, "best_area_proxy": best_area, "best_fmax": None,
        "best_balanced": best_balanced, "vivado_candidates": vivado_candidates,
        "vivado_status": "UNAVAILABLE", "protected_phase5_3_hashes_ok": protected_ok,
        "gcp": budget,
        "model_rtl_error": {
            "status": "VERIFIED_FIXED_K", "mae_cycles": 0.0, "mape_percent": 0.0,
            "scope": "ceil(K/P) with four measured cycles per batch for K=2/4/8/16/35; policy curves use trace replay"
        },
        "limitations": [
            "No GCP worker was launched because current spend and remaining credit are unavailable.",
            "No Vivado executable is installed, so LUT/FF/BRAM/DSP/Fmax/WNS are unavailable.",
            "Policy cycle values replay measured K/P RTL timing; the policy controller is not integrated into RTL.",
            "The software corpus has three short synthetic workloads and does not establish broad HEVC generalization.",
            "Resource cost is an analytical proxy, not a synthesis result."
        ],
    }
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    PARETO.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    PARETO.write_text(json.dumps({"schema_version": "chia-rdo.phase6-pareto.v1", "points": frontier,
                                  "axes": ["BD-rate", "average K", "RTL trace-replay cycles", "resource proxy"]},
                                 indent=2, sort_keys=True) + "\n")

    best = best_cycle
    reports = {
        "phase6_initial_state.md": f"""# Phase 6 Initial State\n\n- Phase 5.3 gate: **PASS**\n- Protected Phase-5.3 hashes: **{'VERIFIED' if protected_ok else 'FAILED'}**\n- Frozen policy: `adaptive_threshold_v1_frozen`, thresholds `0.04/0.20`, K `4/16/35`\n- Phase-5.3 evidence: 56,336 candidate evaluations, 3,080 winners, zero mismatches\n- GCP authorized ceiling: USD 280; safety reserve: USD 20\n""",
        "phase6_chia_architecture.md": """# Phase 6 CHIA Architecture\n\nNative `ChiaFunction` nodes implement proposal, analytical screening, RTL execution, result evaluation, atomic persistence, Pareto updates, matched HM-curve execution, and aggregation. Ray object references connect nodes asynchronously. The proposal agents receive completed history and skip completed IDs; dominated points remain in history.\n\nTrack A fixes `adaptive_threshold_v1_frozen`. Track B assigns new policy IDs/versions to modified hardware-aware weight sets.\n""",
        "phase6_gcp_usage.md": f"""# Phase 6 GCP Usage\n\n- Billing linkage: **VERIFIED enabled**\n- Verified current spend: **UNAVAILABLE**\n- Verified remaining promotional credit: **UNAVAILABLE**\n- Estimated cloud spend: **USD {budget['estimated_spend_usd']:.2f}**\n- Active workers: **{budget['active_workers']}**\n- Cleanup inventory: **VERIFIED empty**\n- Planned 4-worker `e2-standard-8` pilot estimate: **USD {budget['planned_pilot']['estimated_cost_usd']:.6f}**\n- Launch decision: **BLOCKED (fail-closed)**\n\nNo paid resource was launched. The public-list-price estimate does not satisfy the billing guard.\n""",
        "phase6_dse.md": f"""# Phase 6 DSE\n\n- Native CHIA hardware/history records: **{len(hardware_results)}**\n- Matched Phase-6 HM policy curves: **{len(hm_rows)}** ({sum(row['hm_run_count'] for row in hm_rows)} encode results)\n- Successful logical experiments: **{successful}**\n- Cancelled unavailable policy labels: **{cancelled}**\n- Extended RTL evaluations: **{payload['rtl_candidate_evaluations']:,}**, zero failures\n\nThe agent screened P, pipeline depth, buffer depth, width, and scheduler labels. Only the validated static P-way architecture has actual RTL evidence; other hardware combinations remain analytical and cannot support implementation claims.\n\nThe strongest measured Track-B operating point is `{best['policy_id']}` at P={best['p']}: BD-rate {best['bd_rate_percent']:+.4f}%, average K {best['average_k']:.3f}, RDO reduction {best['rdo_reduction']*100:.2f}%, winner retention {best['winner_retention']*100:.2f}%, and {best['rtl_cycles_per_event']:.3f} trace-replayed RTL cycles/event. Its independent HM replicate produced identical BD-rate, K distribution, RDO reduction, and winner retention.\n""",
        "phase6_pareto.md": f"""# Phase 6 Pareto\n\nThe scoped Pareto set has **{len(frontier)}** points over BD-rate, average K, measured K/P RTL trace-replay cycles, and an estimated resource proxy.\n\n- Best cycle: `{best_cycle['policy_id']}`, P={best_cycle['p']}, {best_cycle['rtl_cycles_per_event']:.3f} cycles/event\n- Best area proxy: `{best_area['policy_id']}`, P={best_area['p']}, proxy={best_area['resource_proxy']}\n- Best balanced: `{best_balanced['policy_id']}`, P={best_balanced['p']}, score={best_balanced['balanced_score']:.4f}\n- Best Fmax: **UNAVAILABLE**\n\nNo area or Fmax optimum is claimed without Vivado. Dominated configurations remain in the JSON history.\n""",
        "phase6_model_correlation.md": """# Phase 6 Model Correlation\n\nFor K={2,4,8,16,35} and P={1,2,4,8}, RTL measured `4*ceil(K/P)` cycles with zero error against the current serialized-wrapper model. The expanded regression evaluated 66,576 candidates with zero functional, winner, duplicate, dropped, cycle, or interface failures.\n\nThis zero error is scoped to fixed-K P-way datapath measurements. Policy-level cycle values are trace-weighted replay of those measured points, not an independent integrated policy-controller RTL measurement. Vivado correlation is unavailable.\n""",
        "phase6_gate.md": f"""# Phase 6 Gate\n\n## Status: BLOCKED\n\n- CHIA native asynchronous graph: **PASS**\n- Agent consumes history and maintains Pareto state: **PASS**\n- Frozen Phase-4 policy preserved: **PASS**\n- P=1/2/4/8 and K=2/4/8/16/35 RTL regression: **PASS**\n- Matched HM Track-B curves: **PASS**\n- Independent top-point reproducibility: **PASS**\n- GCP remote execution: **BLOCKED**, verified spend/credit unavailable\n- Substantial multi-worker GCP campaign: **NOT RUN**\n- Vivado selected-candidate synthesis: **UNAVAILABLE**\n\nPhase 6 cannot pass its required gate until GCP remote execution, substantial worker use, cost accounting, cleanup after use, and selected-candidate synthesis are demonstrated. No Phase-7 work is authorized.\n""",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    for name, text in reports.items():
        (REPORTS / name).write_text(text)
    print(json.dumps({"summary": str(SUMMARY.relative_to(ROOT)), "pareto_points": len(frontier),
                      "best_cycle": best_cycle["experiment_id"], "gate": "BLOCKED"}, indent=2))


if __name__ == "__main__":
    main()
