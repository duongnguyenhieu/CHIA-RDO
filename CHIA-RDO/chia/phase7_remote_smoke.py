#!/usr/bin/env python3
"""Native CHIA smoke graph intended to execute on the Phase-7 GCP VM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from chia.base.ChiaFunction import ChiaFunction, get


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from software.analysis import bd_rate  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@ChiaFunction(num_cpus=0)
def inspect_worker() -> dict:
    return {
        "hostname": socket.gethostname(), "platform": platform.platform(),
        "cpu_count": os.cpu_count(), "python": sys.version.split()[0],
        "chia_import": "PASS", "package_qualified_analysis_import": "PASS",
        "bd_rate_identity": bd_rate([(100, 30), (80, 31), (60, 32), (40, 33)],
                                    [(100, 30), (80, 31), (60, 32), (40, 33)]),
        "verilator": subprocess.run(["verilator", "--version"], text=True,
                                    stdout=subprocess.PIPE, check=True).stdout.strip(),
        "vivado": shutil.which("vivado"),
    }


@ChiaFunction(num_cpus=6, max_retries=1)
def run_verilator_regression() -> dict:
    command = [sys.executable, "scripts/run_phase6_klevel_rtl.py"]
    process = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=600, check=False)
    if process.returncode:
        raise RuntimeError(process.stdout[-4000:])
    result_path = ROOT / "results/phase6/rtl_k_levels.json"
    result = json.loads(result_path.read_text())
    return {
        "status": result["status"], "hostname": socket.gethostname(),
        "candidate_evaluations": sum(row["candidate_evaluations"] for row in result["runs"]),
        "failures": sum(row["total_fail"] for row in result["runs"]),
        "p_values": [row["p"] for row in result["runs"]], "k_values": result["k_values"],
        "result_sha256": sha256(result_path), "command": command,
    }


@ChiaFunction(num_cpus=0)
def aggregate(environment: dict, rtl: dict, worker_id: str) -> dict:
    return {
        "schema_version": "chia-rdo.phase7-gcp-smoke.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "execution_backend": "gcp", "gcp_worker_id": worker_id,
        "orchestrator": "native ChiaFunction graph on GCP-hosted Ray runtime",
        "environment": environment, "rtl_regression": rtl,
        "status": "PASS" if environment["chia_import"] == "PASS" and rtl["status"] == "PASS"
                              and rtl["failures"] == 0 else "FAILED",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    environment = inspect_worker.chia_remote()
    rtl = run_verilator_regression.chia_remote()
    result = get(aggregate.chia_remote(environment, rtl, args.worker_id))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
