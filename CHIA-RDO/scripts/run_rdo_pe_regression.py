#!/usr/bin/env python3
"""Build and run the measured HM-vector RDO cost-formation PE regression."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> str:
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=False)
    if process.returncode:
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout}")
    return process.stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vectors", type=Path, default=ROOT / "results/phase5/rdo_pe_vectors.txt")
    args = parser.parse_args()
    verilator = shutil.which("verilator")
    if verilator is None:
        candidate = Path(os.environ.get("CONDA_PREFIX", "")) / "bin/verilator"
        if candidate.is_file():
            verilator = str(candidate)
    if verilator is None:
        raise RuntimeError("verilator is not available; run this script in chia_env")

    build = ROOT / "build/phase5/rdo_pe"
    build.mkdir(parents=True, exist_ok=True)
    output = run([verilator, "--cc", "--exe", "--build", "--top-module", "rdo_pe",
                  "-GDIST_WIDTH=32", "-GRATE_WIDTH=24", "-GLAMBDA_WIDTH=32",
                  "-GLAMBDA_FRACTION=16", "-GCOST_WIDTH=56", "-GPIPELINE_DEPTH=2",
                  "--Mdir", str(build), "rtl/rdo_pe.sv", "rtl/tb/rdo_pe_tb.cpp"])
    simulator_output = run([str(build / "Vrdo_pe"), str(args.vectors)])
    run_result = json.loads(simulator_output.strip().splitlines()[-1])
    vector_metadata = json.loads(args.vectors.with_suffix(".json").read_text())
    result = {
        "schema_version": "chia-rdo.rdo-pe-regression.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "pass" if run_result["fail"] == 0 else "fail",
        "simulator": run_result,
        "vector_metadata": vector_metadata,
        "configuration": {"pipeline_depth": 2, "cost_width": 56, "lambda_format": "Q16.16"},
        "validated_stages": ["distortion input", "rate input", "lambda-rate product", "RD cost accumulation", "overflow saturation", "ready-valid backpressure"],
        "unsupported_stages": vector_metadata["unsupported_stages"],
        "build_log_last_line": output.strip().splitlines()[-1],
    }
    path = ROOT / "results/phase5/rdo_pe_regression.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
