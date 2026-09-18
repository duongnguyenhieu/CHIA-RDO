#!/usr/bin/env python3
"""Execute the locked matched Phase 3 tiny-sequence/QP matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TINY_CONFIGS = {
    22: ROOT / "configs/phase3_qp22.json",
    27: ROOT / "configs/phase3_qp27.json",
    32: ROOT / "configs/baseline_smoke.json",
    37: ROOT / "configs/phase3_qp37.json",
}
CONFIGS_128 = {
    22: ROOT / "configs/phase3_128_qp22.json",
    27: ROOT / "configs/phase3_128_qp27.json",
    32: ROOT / "configs/nontrivial_local.json",
    37: ROOT / "configs/phase3_128_qp37.json",
}


def run(command: list[str]) -> None:
    process = subprocess.run(command, cwd=ROOT, env=os.environ, check=False)
    if process.returncode:
        raise RuntimeError(f"matrix command failed ({process.returncode}): {' '.join(command)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qps", type=int, nargs="+", choices=TINY_CONFIGS, default=list(TINY_CONFIGS))
    parser.add_argument("--workload", choices=("tiny64", "synthetic128"), default="tiny64")
    args = parser.parse_args()
    configs = TINY_CONFIGS if args.workload == "tiny64" else CONFIGS_128
    commands: list[list[str]] = []
    for qp in args.qps:
        config = str(configs[qp])
        baseline_command = ["python3", "software/run_baseline.py", "--config", config]
        if os.environ.get("CHIA_RDO_CLOUD_BACKEND"):
            baseline_command.extend(["--replicate", "phase3-gcp"])
        commands.append(baseline_command)
        base = ["python3", "software/run_policy.py", "--config", config]
        commands.extend([base + ["--policy", "fixed", "--k", str(k)] for k in (8, 16)])
        commands.append(base + ["--policy", "adaptive_v0"])
        commands.append(base + ["--policy", "adaptive_v0", "--high-k", "2", "--medium-k", "4", "--low-k", "8"])
        commands.append(base + ["--policy", "adaptive_threshold", "--easy-threshold", "0.04",
                                "--hard-threshold", "0.20", "--easy-k", "4", "--medium-k", "16", "--hard-k", "35"])
        commands.append(base + ["--policy", "relative_satd", "--relative-threshold", "0.50",
                                "--minimum-k", "8", "--maximum-k", "35"])
        for p in (1, 2, 4, 8):
            commands.append(base + ["--policy", "adaptive_hw", "--p", str(p),
                                    "--high-k", "2", "--medium-k", "4", "--low-k", "8"])
            commands.append(base + ["--policy", "adaptive_hw_v1", "--p", str(p)])
    for command in commands:
        run(command)
    manifest = {
        "schema_version": "chia-rdo.phase3-matched-matrix.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "qps": args.qps, "sequence": json.loads(configs[args.qps[0]].read_text())["sequence"]["name"], "commands": commands,
        "backend": os.environ.get("CHIA_RDO_CLOUD_BACKEND", "local"), "status": "PASS",
    }
    path = ROOT / f"results/experiments/phase3-matrix-{args.workload}-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
