#!/usr/bin/env python3
"""Extract reproducible Phase-7B metrics from completed Vivado builds."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "results/phase7b/synthesis_results.json"
SOURCES = (
    "rtl/rdo_pe.sv",
    "rtl/phase7b/full_rdo_mvp_4x4_serial.sv",
    "rtl/phase7b/full_rdo_pway_optimized.sv",
    "rtl/phase7b/synth_optimized_pway_kv260.tcl",
)
BASE_BUILDS = (
    ("serial-p1-d2", 1, 2, 115, "build/phase7b/vivado/serial-p1"),
    ("serial-p1-d3", 1, 3, 132, "build/phase7b/vivado/serial-p1-d3"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first(pattern: str, text: str, cast=float):
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    if not match:
        raise RuntimeError(f"missing report field: {pattern}")
    return cast(match.group(1))


def extract(build_id: str, p: int, depth: int, latency: int, relative: str) -> dict:
    directory = ROOT / relative
    utilization = (directory / "utilization_route.rpt").read_text(errors="replace")
    timing = (directory / "timing_summary.rpt").read_text(errors="replace")
    paths = (directory / "timing_paths_detailed.rpt").read_text(errors="replace")
    power = (directory / "power.rpt").read_text(errors="replace")
    wns = first(r"WNS\(ns\)\s+TNS\(ns\).*?\n\s*-+.*?\n\s*([-0-9.]+)", timing)
    tns = first(r"WNS\(ns\)\s+TNS\(ns\).*?\n\s*-+.*?\n\s*[-0-9.]+\s+([-0-9.]+)", timing)
    period = 5.0 - wns
    batch_cycles = latency + 2
    return {
        "build_id": build_id,
        "architecture": "resource_shared_serial",
        "winner_reduction": "balanced_tree" if build_id.endswith("-tree") else "serial_scan",
        "p": p,
        "pipeline_depth": depth,
        "candidate_latency_cycles": latency,
        "batch_cycles": batch_cycles,
        "status": "ROUTE_PASS",
        "timing_status": "PASS" if wns >= 0 else "FAIL",
        "lut": first(r"\| CLB LUTs\*?\s*\|\s*(\d+)\s*\|", utilization, int),
        "ff": first(r"\| CLB Registers\s*\|\s*(\d+)\s*\|", utilization, int),
        "carry8": first(r"\| CARRY8\s*\|\s*(\d+)\s*\|", utilization, int),
        "bram": first(r"\| Block RAM Tile\s*\|\s*(\d+)\s*\|", utilization, int),
        "uram": first(r"\| URAM\s*\|\s*(\d+)\s*\|", utilization, int),
        "dsp": first(r"\| DSPs\s*\|\s*(\d+)\s*\|", utilization, int),
        "wns_ns": wns,
        "tns_ns": tns,
        "fmax_mhz": 1000.0 / period,
        "candidate_throughput_proxy_per_second": p * 1e9 / (period * batch_cycles),
        "power_w": first(r"Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)", power),
        "critical_path": {
            "slack_ns": first(r"Slack \(VIOLATED\)\s*:\s*([-0-9.]+)ns", paths),
            "source": first(r"Source:\s+(\S+)", paths, str),
            "destination": first(r"Destination:\s+(\S+)", paths, str),
            "data_path_delay_ns": first(r"Data Path Delay:\s*([0-9.]+)ns", paths),
            "logic_levels": first(r"Logic Levels:\s*(\d+)", paths, int),
        },
        "raw_report_directory": relative,
        "resource_accounting": "Vivado report_utilization physical resources",
    }


def main() -> None:
    builds = list(BASE_BUILDS)
    for directory in sorted((ROOT / "build/phase7b/vivado").glob("serial-p*-d*-w*")):
        match = re.fullmatch(r"serial-p(\d+)-d(\d+)-w(\d+)(?:-tree)?", directory.name)
        if match and (directory / "utilization_route.rpt").is_file():
            p, depth, width = map(int, match.groups())
            latency = 113 + depth + (16 if depth >= 3 else 0)
            builds.append((directory.name, p, depth, latency, str(directory.relative_to(ROOT))))
    rows = [extract(*build) for build in builds]
    for row in rows:
        width_match = re.search(r"-w(\d+)(?:-tree)?$", row["build_id"])
        row["cost_width"] = int(width_match.group(1)) if width_match else 56
    baseline = json.loads((ROOT / "results/phase7/vivado_results.json").read_text())
    baseline_p1 = next(row for row in baseline["rows"] if row["p"] == 1)
    for row in rows:
        row["relative_to_baseline_p1"] = {
            "lut_reduction_fraction": 1.0 - row["lut"] / baseline_p1["lut"],
            "dsp_reduction_fraction": 1.0 - row["dsp"] / baseline_p1["dsp"],
            "fmax_improvement": row["fmax_mhz"] / baseline_p1["fmax_mhz"],
        }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    git_dirty = bool(subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
        check=True, text=True, stdout=subprocess.PIPE,
    ).stdout.strip())
    payload = {
        "schema_version": "chia-rdo.phase7b-synthesis-results.v1",
        "updated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "target_part": "xck26-sfvc784-2LV-c",
        "clock_constraint_ns": 5.0,
        "scope": "Full-RDO kernel throughput proxy; not encoder throughput",
        "git_commit": commit,
        "git_dirty": git_dirty,
        "current_source_sha256": {path: sha256(ROOT / path) for path in SOURCES},
        "source_hash_qualification": (
            "Hashes describe the current post-build source tree. Exact pre-edit source hashes for the "
            "pre-tree builds were not captured and are unavailable."
        ),
        "baseline_p1": {key: baseline_p1.get(key) for key in (
            "lut", "ff", "bram", "uram", "dsp", "wns_ns", "tns_ns", "fmax_mhz", "power_w"
        )},
        "rows": rows,
    }
    baseline_period = 5.0 - baseline_p1["wns_ns"]
    payload["baseline_p1"]["candidate_cycles"] = 4
    payload["baseline_p1"]["candidate_throughput_proxy_per_second"] = 1e9 / (baseline_period * 4)
    for row in rows:
        row["relative_to_baseline_p1"]["candidate_throughput_fraction"] = (
            row["candidate_throughput_proxy_per_second"]
            / payload["baseline_p1"]["candidate_throughput_proxy_per_second"]
        )
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
