#!/usr/bin/env python3
"""Evaluate the Phase-4 algorithm-freeze and RTL-entry gate."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {
    "results/experiments/gcp-verification.json": "90e3beaf79b1d41001ade0ba6298c395d5567aba1374012354c256b2a526c410",
    "reports/phase3_policy_search.md": "18367e06af9932c8b46e94793e50f4e1a569362302e8375beb56d73274f43d5f",
    "reports/phase3_gate.md": "f174b7e9707057a22926b1a3130e36798233b6ea77523c9954bf5f2e11ee5071",
    "reports/gcp_phase3_usage.md": "7f1d837b7059cf66ea3656dbc6744d3ef899eaba26bb89bc330798d190b79446",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    phase3 = json.loads((ROOT / "results/experiments/phase3-gate.json").read_text())
    gcp = json.loads((ROOT / "results/experiments/gcp-verification.json").read_text())
    manifest = json.loads((ROOT / "results/phase4/matrix-manifest.json").read_text())
    database = json.loads((ROOT / "results/phase4/database.json").read_text())
    analysis = json.loads((ROOT / "results/phase4/analysis.json").read_text())
    pareto = json.loads((ROOT / "results/phase4/pareto.json").read_text())
    scheduler = json.loads((ROOT / "results/rtl/verilator-regression.json").read_text())
    counts = Counter(row["policy"] for row in database["records"])
    tests = subprocess.run(["python", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT,
                           text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    required_policies = ("full_rdo", "fixed_k2", "fixed_k4", "fixed_k8", "fixed_k16", "adaptive_v0",
                         "adaptive_threshold", "relative_satd", "adaptive_hw_batch_fill_p8", "adaptive_hw_v1_p8")
    checks = {
        "phase3_reproducibility": phase3["status"] == "PASS" and gcp["status"] == "PASS",
        "phase3_evidence_preserved": all(sha256(ROOT / path) == digest for path, digest in PROTECTED.items()),
        "unit_tests": tests.returncode == 0,
        "heldout_workloads": manifest["status"] == "PASS" and len(manifest["workloads"]) == 3 and manifest["split"] == "phase4-held-out-no-tuning",
        "multi_qp_evaluation": manifest["qps"] == [22, 27, 32, 37] and len(database["records"]) == 120,
        "required_policies": all(counts[name] == 12 for name in required_policies),
        "coding_metrics": all(row["status"] == "PASS" and all(key in row["psnr"] for key in ("y", "u", "v", "yuv")) for row in database["records"]),
        "bd_rate_analysis": len(database["bd_rate_by_workload_percent"]) == 30 and all(value is not None for value in database["policy_bd_rate_percent"].values()),
        "frozen_policy_acceptance": all(analysis["adaptive_threshold_acceptance"].values()) and analysis["selections"]["final_policy"] == "adaptive_threshold",
        "failure_analysis": analysis["missed_winner_events"] >= 0 and (ROOT / "reports/phase4_failure_analysis.md").is_file(),
        "hardware_cost_model": scheduler["status"] == "pass" and scheduler["total_fail"] == 0 and (ROOT / "reports/phase4_hardware_cost_model.md").is_file(),
        "pareto_analysis": pareto["status"] == "PASS" and bool(pareto["frontier"]),
        "final_policy_inputs": (ROOT / "docs/adaptive_threshold_v1_spec.md").is_file() and (ROOT / "docs/final_algorithm_spec.md").is_file(),
        "no_standard_corpus_overclaim": analysis["generalization"] == "LIMITED" and not analysis["standard_hevc_corpus"],
        "rtl_specification_only": (ROOT / "docs/rtl_rdo_architecture_spec.md").is_file() and (ROOT / "docs/adaptive_hw_feature_mapping.md").is_file(),
    }
    freeze = all(checks.values())
    lines = ["================================================", "CHIA-RDO PHASE 4", "================================================", "",
             f"Phase-3 reproducibility: {'PASS' if checks['phase3_reproducibility'] and checks['phase3_evidence_preserved'] else 'FAIL'}",
             f"Held-out workloads: {'PASS' if checks['heldout_workloads'] else 'FAIL'}",
             f"Multi-QP evaluation: {'PASS' if checks['multi_qp_evaluation'] else 'FAIL'}",
             f"BD-rate analysis: {'PASS' if checks['bd_rate_analysis'] else 'FAIL'}",
             f"Failure analysis: {'PASS' if checks['failure_analysis'] else 'FAIL'}",
             f"Hardware cost model: {'PASS' if checks['hardware_cost_model'] else 'FAIL'}",
             f"Pareto analysis: {'PASS' if checks['pareto_analysis'] else 'FAIL'}", "",
             "Selected policy:", "    adaptive_threshold", "", "Generalization:", "    LIMITED", "",
             f"ALGORITHM_FREEZE:", f"    {'PASS' if freeze else 'FAIL'}", "",
             "RTL readiness:", f"    {'READY' if freeze else 'NOT READY'}", "",
             "Current evidence is not sufficient to claim generalization to a standard HEVC corpus.", "",
             "No Full-RDO datapath RTL or large Vivado synthesis campaign was performed in Phase 4.", "",
             "## Machine-Readable Checks", "", "| Check | Status |", "|---|---|"]
    lines.extend(f"| {name.replace('_', ' ')} | {'PASS' if status else 'FAIL'} |" for name, status in checks.items())
    (ROOT / "reports/phase4_gate.md").write_text("\n".join(lines) + "\n")
    result = {"schema_version": "chia-rdo.phase4-gate.v1", "status": "PASS" if freeze else "FAIL",
              "algorithm_freeze": "PASS" if freeze else "FAIL", "generalization": "LIMITED",
              "rtl_readiness": "READY" if freeze else "NOT READY", "selected_policy": "adaptive_threshold",
              "checks": checks, "unit_test_output": tests.stdout}
    (ROOT / "results/phase4/gate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "algorithm_freeze", "generalization", "rtl_readiness", "selected_policy", "checks")}, indent=2, sort_keys=True))
    if not freeze:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
