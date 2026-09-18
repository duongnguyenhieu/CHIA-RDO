#!/usr/bin/env python3
"""Implement unique Phase-7 P-way candidates with Vivado 2024.2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/phase7/vivado"
RESULT_DIR = ROOT / "results/phase7"
RTL_FILES = ("rtl/rdo_pe.sv", "rtl/full_rdo_codec_4x4.sv", "rtl/full_rdo_mvp_4x4.sv",
             "rtl/full_rdo_pway.sv", "rtl/constraints/kv260.xdc", "rtl/synth_phase7_pway_kv260.tcl",
             "build/phase7/generated/full_rdo_codec_4x4.sv")


def vivado() -> str:
    configured = os.environ.get("VIVADO") or shutil.which("vivado")
    default = Path("/tools/Xilinx/Vivado/2024.2/bin/vivado")
    if configured:
        return str(configured)
    if default.is_file():
        return str(default)
    raise RuntimeError("Vivado 2024.2 not found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_metrics(path: Path) -> dict:
    values = {}
    for line in path.read_text().splitlines():
        key, value = line.split("=", 1)
        values[key] = value
    for key in ("p", "lut", "ff", "bram", "uram", "dsp"):
        values[key] = int(values[key])
    for key in ("wns_ns", "fmax_mhz"):
        values[key] = float(values[key]) if values[key] else None
    return values


def device_utilization(path: Path) -> dict:
    """Parse physical resources from report_utilization, not logical cell counts."""
    if not path.is_file():
        return {}
    text = path.read_text(errors="replace")
    patterns = {
        "lut": r"\| CLB LUTs\*?\s*\|\s*(\d+)\s*\|",
        "ff": r"\| CLB Registers\s*\|\s*(\d+)\s*\|",
        "bram": r"\| Block RAM Tile\s*\|\s*(\d+)\s*\|",
        "uram": r"\| URAM\s*\|\s*(\d+)\s*\|",
        "dsp": r"\| DSPs\s*\|\s*(\d+)\s*\|",
    }
    return {
        name: int(match.group(1))
        for name, pattern in patterns.items()
        if (match := re.search(pattern, text))
    }


def timing_tns(path: Path) -> float | None:
    if not path.is_file():
        return None
    match = re.search(r"WNS\(ns\)\s+TNS\(ns\).*?\n\s*-+.*?\n\s*([-0-9.]+)\s+([-0-9.]+)",
                      path.read_text(errors="replace"), re.DOTALL)
    return float(match.group(2)) if match else None


def power(path: Path) -> float | None:
    if not path.is_file():
        return None
    match = re.search(r"Total On-Chip Power \(W\)\s*\|\s*([0-9.]+)", path.read_text(errors="replace"))
    return float(match.group(1)) if match else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p", action="append", type=int, choices=(1, 2, 4, 8), dest="p_values")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    candidates = json.loads((RESULT_DIR / "vivado_candidates.json").read_text())
    selected = set(args.p_values or (1, 2, 4, 8))
    tool = vivado()
    version = subprocess.run([tool, "-version"], text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, check=True).stdout.splitlines()[0]
    BUILD.mkdir(parents=True, exist_ok=True)
    existing_path = RESULT_DIR / "vivado_results.json"
    existing = json.loads(existing_path.read_text())["rows"] if existing_path.is_file() else []
    for row in existing:
        output = ROOT / row["raw_report_directory"]
        report_stage = ("route" if (output / "utilization_route.rpt").is_file()
                        else "place" if (output / "utilization_place.rpt").is_file() else "synth")
        physical = device_utilization(output / f"utilization_{report_stage}.rpt")
        if physical and row.get("resource_accounting") != "Vivado report_utilization physical resources":
            row["logical_cell_counts"] = {
                key: row.get(key) for key in ("lut", "ff", "bram", "uram", "dsp")
            }
            row.update(physical)
            row["resource_accounting"] = "Vivado report_utilization physical resources"
            row["resource_report_stage"] = report_stage
    indexed = {row["build_id"]: row for row in existing}
    if existing_path.is_file():
        normalized = json.loads(existing_path.read_text())
        normalized["rows"] = sorted(indexed.values(), key=lambda item: item["p"])
        existing_path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                stdout=subprocess.PIPE, check=True).stdout.strip()
    for build in candidates["vivado_builds"]:
        if build["p"] not in selected or (build["build_id"] in indexed and not args.force):
            continue
        output = BUILD / build["build_id"]
        output.mkdir(parents=True, exist_ok=True)
        command = [tool, "-mode", "batch", "-nojournal", "-nolog", "-source",
                   "rtl/synth_phase7_pway_kv260.tcl", "-tclargs", str(build["p"]), str(output)]
        started = datetime.now(timezone.utc)
        process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=5400, check=False)
        ended = datetime.now(timezone.utc)
        log = BUILD / f"{build['build_id']}.log"
        log.write_text(process.stdout)
        metrics_path = output / "metrics.txt"
        if metrics_path.is_file():
            metrics = parse_metrics(metrics_path)
        else:
            metrics = {"p": build["p"], "status": "TOOL_FAIL", "implementation_stage": "none",
                       "error_message": process.stdout[-2000:], "lut": None, "ff": None,
                        "bram": None, "uram": None, "dsp": None, "wns_ns": None, "fmax_mhz": None}
        report_stage = ("route" if (output / "utilization_route.rpt").is_file()
                        else "place" if (output / "utilization_place.rpt").is_file() else "synth")
        physical = device_utilization(output / f"utilization_{report_stage}.rpt")
        logical_cell_counts = {key: metrics.get(key) for key in ("lut", "ff", "bram", "uram", "dsp")}
        metrics.update(physical)
        timing_path = output / ("timing_summary.rpt" if (output / "timing_summary.rpt").is_file()
                                else "timing_place.rpt")
        row = {
            **build, **metrics, "experiment_id": f"phase7-vivado-{build['build_id']}",
            "git_commit": git_commit, "git_dirty": True, "target_part": "xck26-sfvc784-2LV-c",
            "clock_constraint_ns": 5.0, "vivado_version": version,
            "started_utc": started.isoformat().replace("+00:00", "Z"),
            "ended_utc": ended.isoformat().replace("+00:00", "Z"),
            "elapsed_seconds": (ended - started).total_seconds(), "tool_returncode": process.returncode,
            "rtl_source_sha256": {path: sha256(ROOT / path) for path in RTL_FILES},
            "configuration_sha256": hashlib.sha256(json.dumps(build, sort_keys=True).encode()).hexdigest(),
            "tns_ns": timing_tns(timing_path), "power_w": power(output / "power.rpt"),
            "timing_status": ("PASS" if metrics.get("status") == "ROUTE_PASS" and metrics.get("wns_ns", -1) >= 0
                              else "FAIL" if metrics.get("wns_ns") is not None else "NOT_AVAILABLE"),
            "raw_report_directory": str(output.relative_to(ROOT)),
            "resource_accounting": "Vivado report_utilization physical resources",
            "resource_report_stage": report_stage,
            "logical_cell_counts": logical_cell_counts,
            "scope": "full_rdo_pway with P implemented; requested pipeline/buffer/width are not RTL parameters of this top",
        }
        indexed[build["build_id"]] = row
        payload = {"schema_version": "chia-rdo.phase7-vivado-results.v1",
                   "updated_utc": ended.isoformat().replace("+00:00", "Z"),
                   "tool": version, "part": "xck26-sfvc784-2LV-c", "clock_constraint_ns": 5.0,
                   "rows": sorted(indexed.values(), key=lambda item: item["p"])}
        existing_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    payload = json.loads(existing_path.read_text())
    fields = ("experiment_id", "build_id", "p", "status", "implementation_stage", "lut", "ff", "bram",
              "uram", "dsp", "wns_ns", "tns_ns", "fmax_mhz", "timing_status", "power_w", "elapsed_seconds")
    with (RESULT_DIR / "vivado_results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in payload["rows"]:
            writer.writerow({key: row.get(key) for key in fields})
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
