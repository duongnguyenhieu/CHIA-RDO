#!/usr/bin/env python3
"""Run integrated P-lane RDO array tests over the declared design ranges."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command_output(command: list[str]) -> str:
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=False)
    if process.returncode:
        raise RuntimeError(f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout}")
    return process.stdout


def main() -> None:
    verilator = shutil.which("verilator")
    if verilator is None:
        candidate = Path(os.environ.get("CONDA_PREFIX", "")) / "bin/verilator"
        verilator = str(candidate) if candidate.is_file() else None
    if verilator is None:
        raise RuntimeError("verilator is not available")
    rows = []
    for p in (1, 2, 4, 8):
        for depth in (1, 2, 4):
            build = ROOT / f"build/phase5/rdo_array/p{p}-d{depth}"
            build.mkdir(parents=True, exist_ok=True)
            output = command_output([
                verilator, "--binary", "--timing", "--top-module", "rdo_array_tb",
                f"-GP={p}", f"-GPIPELINE_DEPTH={depth}", "-GCOST_WIDTH=56",
                "--Mdir", str(build), "rtl/rdo_pe.sv", "rtl/rdo_array.sv", "rtl/tb/rdo_array_tb.sv",
            ])
            simulation = command_output([str(build / "Vrdo_array_tb")])
            rows.append(json.loads([line for line in simulation.splitlines() if line.startswith("{")][-1]))
    result = {"schema_version": "chia-rdo.rdo-array-regression.v1",
              "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "status": "pass", "rows": rows, "total_pass": sum(row["pass"] for row in rows),
              "coverage": {"p": [1, 2, 4, 8], "pipeline_depth": [1, 2, 4],
                           "candidate_counts": [3, 35], "tail_batches": True},
              "build_log_last_line": output.strip().splitlines()[-1]}
    path = ROOT / "results/phase5/rdo_array_regression.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
