#!/usr/bin/env python3
"""Post-route characterization of the Phase-5.2 Full-RDO PE on KV260."""

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "phase5_2" / "vivado"
RESULT = ROOT / "results" / "phase5_2" / "vivado_kv260.json"


def vivado() -> str:
    executable = os.environ.get("VIVADO") or shutil.which("vivado")
    if executable:
        return str(executable)
    default = Path("/tools/Xilinx/Vivado/2024.2/bin/vivado")
    if default.is_file():
        return str(default)
    raise RuntimeError("Vivado not found")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    command = [vivado(), "-mode", "batch", "-nojournal", "-nolog", "-source",
               "rtl/synth_full_rdo_pe_kv260.tcl", "-tclargs", str(BUILD)]
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=False)
    (BUILD / "vivado.log").write_text(process.stdout, encoding="utf-8")
    if process.returncode:
        raise RuntimeError(f"Vivado failed; see {BUILD / 'vivado.log'}")
    metrics: dict[str, int | float | bool | None] = {}
    for line in (BUILD / "metrics.txt").read_text().splitlines():
        name, value = line.split("=", 1)
        metrics[name] = float(value) if name in {"wns_ns", "fmax_mhz"} else int(value)
    power_text = (BUILD / "power.rpt").read_text(errors="replace")
    match = re.search(r"Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)", power_text)
    metrics["power_w"] = float(match.group(1)) if match else None
    metrics["timing_met"] = metrics["wns_ns"] >= 0
    result = {
        "schema_version": "chia-rdo.full-rdo-pe-vivado-kv260.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tool": "Vivado 2024.2", "part": "xck26-sfvc784-2LV-c",
        "clock_constraint_ns": 5.0, "implementation": "out_of_context_post_route",
        "metrics": metrics,
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
