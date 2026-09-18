#!/usr/bin/env python3
"""Measure the Phase-5 Pareto RDO arrays on the KV260 target."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/phase5/vivado"


def vivado() -> str:
    configured = os.environ.get("VIVADO") or shutil.which("vivado")
    if configured:
        return str(configured)
    default = Path("/tools/Xilinx/Vivado/2024.2/bin/vivado")
    if default.is_file():
        return str(default)
    raise RuntimeError("Vivado not found")


def power_watts(report: Path) -> float | None:
    match = re.search(r"Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)", report.read_text(errors="replace"))
    return float(match.group(1)) if match else None


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    rows = []
    for p, depth in ((1, 1), (2, 1), (4, 1), (4, 2), (8, 1), (8, 2)):
        key = f"p{p}-d{depth}-b35-w56"
        output = BUILD / key
        command = [vivado(), "-mode", "batch", "-nojournal", "-nolog", "-source",
                   "rtl/synth_phase5_kv260.tcl", "-tclargs", str(p), str(depth), "56", str(output)]
        process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
        (BUILD / f"{key}.log").write_text(process.stdout)
        if process.returncode:
            raise RuntimeError(f"Vivado failed for {key}; see {BUILD / f'{key}.log'}")
        metrics: dict[str, int | float | str | None] = {"key": key}
        for line in (output / "metrics.txt").read_text().splitlines():
            name, value = line.split("=", 1)
            metrics[name] = float(value) if name in {"wns_ns", "fmax_mhz"} else int(value)
        metrics["power_w"] = power_watts(output / "power.rpt")
        metrics["timing_met"] = metrics["wns_ns"] >= 0
        metrics["max_candidates_per_second"] = metrics["fmax_mhz"] * 1_000_000 * p
        rows.append(metrics)
    result = {"schema_version": "chia-rdo.phase5-vivado-kv260.v1",
              "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "tool": "Vivado 2024.2", "part": "xck26-sfvc784-2LV-c",
              "clock_constraint_ns": 5.0, "implementation": "out_of_context_post_route",
              "scope": "P fixed-point RD cost lanes, streaming control, and best-candidate reduction",
              "rows": rows}
    path = ROOT / "results/phase5/vivado_kv260.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
