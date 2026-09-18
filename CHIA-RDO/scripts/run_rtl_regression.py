#!/usr/bin/env python3
"""Build and execute the parameterized scheduler Verilator regression."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/rtl"


def run(command: list[str]) -> str:
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=False)
    if process.returncode:
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout}")
    return process.stdout


def main() -> None:
    run(["python3", "scripts/generate_rtl_vectors.py"])
    runs = []
    for p in (1, 2, 4, 8):
        obj = BUILD / f"p{p}"
        run(["verilator", "--cc", "--exe", "--build", "--top-module", "rdo_scheduler",
             f"-GP={p}", "-GPIPELINE_DEPTH=2", "-GCOST_WIDTH=48", "-GBUFFER_DEPTH=35",
             "--Mdir", str(obj), "rtl/rdo_scheduler.sv", "rtl/tb/rdo_scheduler_tb.cpp"])
        output = run([str(obj / "Vrdo_scheduler"), str(BUILD / "golden_vectors.txt"), str(p)])
        runs.append(json.loads(output.strip().splitlines()[-1]))
    result = {
        "schema_version": "chia-rdo.verilator-regression.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pass" if all(row["fail"] == 0 for row in runs) else "fail",
        "runs": runs, "total_pass": sum(row["pass"] for row in runs),
        "total_fail": sum(row["fail"] for row in runs),
        "coverage": {"parallelism": [1, 2, 4, 8], "k": [2, 4, 8, 16, 35],
                     "hm_vectors": 160, "random_vectors": 340, "tie_cases": True},
    }
    path = ROOT / "results/rtl/verilator-regression.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = ROOT / "reports/rtl_regression.md"
    report.write_text(
        "# RTL Scheduler Regression\n\n"
        f"Status: {result['status'].upper()}\n\n"
        f"Verilator passed {result['total_pass']:,} cases with {result['total_fail']} failures. "
        "Each of P=1/2/4/8 ran 160 HM-derived and 340 deterministic randomized vectors "
        "covering K=2/4/8/16/35 and stable cost ties. The checked kernel covers buffering, "
        "candidate dispatch, ceil(K/P) batch accounting, pipeline drain, and best-candidate "
        "reduction; it is not a complete HEVC transform/quantization datapath.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
