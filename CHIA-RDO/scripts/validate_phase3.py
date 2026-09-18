#!/usr/bin/env python3
"""Evaluate the blocking CHIA-RDO software algorithm gate."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    checks = {}
    unit = subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
                          cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    checks["unit_tests"] = unit.returncode == 0
    phase1 = json.loads((ROOT / "results/quality_gate/latest.json").read_text())
    checks["full_rdo_regression"] = phase1["status"] == "PASS" and phase1["repeat_trace_summary"]["rdo_evaluations"] == 47740
    database = json.loads((ROOT / "results/experiments/database.json").read_text())
    counts = Counter(row["policy"] for row in database["records"])
    required = ("adaptive_v0", "adaptive_threshold", "relative_satd", "adaptive_hw_batch_fill_p1",
                "adaptive_hw_batch_fill_p2", "adaptive_hw_batch_fill_p4", "adaptive_hw_batch_fill_p8",
                "adaptive_hw_v1_p1", "adaptive_hw_v1_p2", "adaptive_hw_v1_p4", "adaptive_hw_v1_p8")
    checks["required_policies"] = all(counts[name] == 8 for name in required)
    checks["matched_evaluation"] = len(database["records"]) == 120 and all(row["status"] == "PASS" for row in database["records"])
    checks["multi_qp"] = all({row["qp"] for row in database["records"] if row["policy"] == name} == {22, 27, 32, 37}
                             for name in required)
    checks["bd_rate"] = all(value is not None for value in database["policy_bd_rate_percent"].values())
    checks["hardware_evidence"] = database["policy_bd_rate_percent"]["adaptive_hw_v1_p8"] < 1.0
    checks["policy_search"] = json.loads((ROOT / "results/analysis/phase3-policy-search.json").read_text())["trial_count"] >= 100
    gcp = json.loads((ROOT / "results/experiments/gcp-verification.json").read_text())
    checks["gcp_sweep"] = gcp["status"] == "PASS" and gcp["matrix_policy_records"] == 56 and gcp["matrix_baseline_records"] == 4
    checks["online_gcp_search"] = (gcp["online_search_trials_per_run"] == 12
                                    and gcp["online_search_machine_types"] == ["e2-standard-2", "e2-standard-8"])
    checks["experiment_database"] = (ROOT / "results/experiments/database.csv").is_file()
    checks["pareto"] = json.loads((ROOT / "results/experiments/pareto.json").read_text())["selections"]["selected_for_rtl"] == "adaptive_threshold"
    checks["chia_loop"] = json.loads((ROOT / "results/experiments/chia-loop.json").read_text())["status"] == "PASS"
    checks["measurement_labels"] = all(row["measurement_type"] == "software_measured_with_analytical_hardware_estimate"
                                       for row in database["records"])
    passed = all(checks.values())
    lines = ["# Phase 3 Algorithm Gate", "", f"ALGORITHM_GATE = {'PASS' if passed else 'FAIL'}", "",
             "| Gate | Status |", "|---|---|"]
    lines.extend(f"| {name.replace('_', ' ')} | {'PASS' if status else 'FAIL'} |" for name, status in checks.items())
    lines += ["", "The gate covers two deterministic synthetic All-Intra workloads at matched QP 22/27/32/37. "
              "This is sufficient to choose the next prototype controller under the project gate, but it is not evidence of generalization to a standard HEVC corpus.", "",
              "Measured software coding results, analytical cycle estimates, prior Verilator scheduler results, and incomplete Vivado artifacts remain explicitly separate.", "",
              "Selected policy for the next RTL specification: `adaptive_threshold` with normalized best rough-cost thresholds 0.04/0.20 and K levels 4/16/35. No Full-RDO datapath RTL was added in Phase 3."]
    (ROOT / "reports/phase3_gate.md").write_text("\n".join(lines) + "\n")
    result = {"schema_version": "chia-rdo.phase3-gate.v1", "status": "PASS" if passed else "FAIL", "checks": checks}
    (ROOT / "results/experiments/phase3-gate.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
