#!/usr/bin/env python3
"""Run reproducible post-route KV260 measurements for scheduler variants."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/synth"


def vivado_binary() -> str:
    configured = os.environ.get("VIVADO")
    if configured:
        return configured
    discovered = shutil.which("vivado")
    if discovered:
        return discovered
    default = Path("/tools/Xilinx/Vivado/2024.2/bin/vivado")
    if default.exists():
        return str(default)
    raise RuntimeError("Vivado not found; set VIVADO to its executable")


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in (1, 2, 4, 8):
        output = BUILD / f"p{p}"
        command = [vivado_binary(), "-mode", "batch", "-nojournal", "-nolog", "-source",
                   "rtl/synth_kv260.tcl", "-tclargs", str(p), str(output)]
        process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, check=False)
        (BUILD / f"p{p}.log").write_text(process.stdout)
        if process.returncode:
            raise RuntimeError(f"Vivado failed for P={p}; see {BUILD / f'p{p}.log'}")
        metrics = {}
        for line in (output / "metrics.txt").read_text().splitlines():
            key, value = line.split("=", 1)
            metrics[key] = int(value) if key in {"p", "lut", "ff"} else float(value)
        rows.append(metrics)
    result = {
        "schema_version": "chia-rdo.vivado-kv260.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "part": "xck26-sfvc784-2LV-c", "clock_constraint_ns": 5.0,
        "tool": "Vivado 2024.2", "implementation": "out_of_context_post_route",
        "rows": rows,
        "scope": "scheduler buffers, P-way dispatch/minimum reduction, control, and batch accounting only",
    }
    path = ROOT / "results/rtl/vivado-kv260.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    table = "\n".join(
        f"| {row['p']} | {row['lut']} | {row['ff']} | {row['wns_ns']:.3f} | {row['fmax_mhz']:.1f} |"
        for row in rows
    )
    (ROOT / "reports/rtl_synthesis.md").write_text(
        "# KV260 Scheduler Synthesis\n\n"
        "Vivado 2024.2 out-of-context post-route results for `xck26-sfvc784-2LV-c` at a 5 ns constraint.\n\n"
        "| P | LUT | FF | WNS (ns) | Derived Fmax (MHz) |\n|---:|---:|---:|---:|---:|\n" + table + "\n\n"
        "Fmax is derived as `1000 / (constraint - WNS)` from the worst post-route setup path. "
        "These figures cover only scheduler buffering, dispatch, minimum reduction, control, and batch accounting; "
        "they do not represent a complete HEVC RDO datapath or board-level implementation.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
