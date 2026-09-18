#!/usr/bin/env python3
"""Run the selected Phase-7B Vivado calibration set with resume support."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIVADO = "/tools/Xilinx/Vivado/2024.2/bin/vivado"
SELECTED = (
    "serial-p1-d2-w31", "serial-p1-d3-w31",
    "serial-p2-d2-w31", "serial-p2-d3-w31",
    "serial-p3-d3-w31",
    "serial-p4-d2-w31", "serial-p4-d3-w31",
    "serial-p6-d3-w31",
    "serial-p8-d2-w31", "serial-p8-d3-w31",
)


def main() -> None:
    candidates = json.loads((ROOT / "results/phase7b/vivado_candidates.json").read_text())["builds"]
    indexed = {row["build_id"]: row for row in candidates}
    records = []
    for build_id in SELECTED:
        candidate = indexed[build_id]
        output = ROOT / "build/phase7b/vivado" / build_id
        if (output / "utilization_route.rpt").is_file():
            records.append({"build_id": build_id, "status": "CACHE_HIT"})
            continue
        output.mkdir(parents=True, exist_ok=True)
        command = [
            VIVADO, "-mode", "batch", "-nojournal", "-nolog", "-source",
            "rtl/phase7b/synth_optimized_pway_kv260.tcl", "-tclargs",
            str(candidate["p"]), str(output), str(candidate["pipeline_depth"]),
            str(candidate["cost_width"]), str(candidate["max_candidates"]),
        ]
        started = datetime.now(timezone.utc)
        process = subprocess.run(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=1800, check=False,
        )
        ended = datetime.now(timezone.utc)
        (ROOT / "build/phase7b/vivado" / f"{build_id}.log").write_text(
            process.stdout, encoding="utf-8"
        )
        record = {
            "build_id": build_id,
            "status": "ROUTE_PASS" if (output / "utilization_route.rpt").is_file() else "TOOL_FAIL",
            "returncode": process.returncode,
            "started_utc": started.isoformat().replace("+00:00", "Z"),
            "ended_utc": ended.isoformat().replace("+00:00", "Z"),
            "elapsed_seconds": (ended - started).total_seconds(),
        }
        records.append(record)
        state = {"schema_version": "chia-rdo.phase7b-vivado-run.v1", "records": records}
        (ROOT / "results/phase7b/vivado_run.json").write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        if record["status"] != "ROUTE_PASS":
            raise RuntimeError(f"Vivado failed for {build_id}; see build log")
    subprocess.run(["python", "scripts/build_phase7b_synthesis_results.py"], cwd=ROOT, check=True)
    print(json.dumps({"selected": len(SELECTED), "records": records}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
