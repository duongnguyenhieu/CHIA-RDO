#!/usr/bin/env python3
"""Bounded online Phase 3 parameter search at synthetic128 QP32."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/nontrivial_local.json"


def main() -> None:
    baseline = ["python3", "software/run_baseline.py", "--config", str(CONFIG)]
    if os.environ.get("CHIA_RDO_CLOUD_BACKEND"):
        baseline += ["--replicate", "phase3-search-gcp"]
    commands = [baseline]
    base = ["python3", "software/run_policy.py", "--config", str(CONFIG)]
    for easy, hard, ks in ((0.04, 0.12, (2, 4, 8)), (0.04, 0.20, (4, 16, 35)),
                           (0.08, 0.20, (4, 8, 16)), (0.12, 0.35, (4, 16, 35))):
        commands.append(base + ["--policy", "adaptive_threshold", "--easy-threshold", str(easy),
                                "--hard-threshold", str(hard), "--easy-k", str(ks[0]),
                                "--medium-k", str(ks[1]), "--hard-k", str(ks[2])])
    for threshold, minimum in ((0.10, 4), (0.25, 4), (0.50, 8), (0.75, 8)):
        commands.append(base + ["--policy", "relative_satd", "--relative-threshold", str(threshold),
                                "--minimum-k", str(minimum), "--maximum-k", "35"])
    for quality, cycle in ((0.6, 0.30), (1.0, 0.30), (1.4, 0.15), (0.6, 0.60)):
        commands.append(base + ["--policy", "adaptive_hw_v1", "--p", "8",
                                "--quality-weight", str(quality), "--cycle-weight", str(cycle)])
    for command in commands:
        process = subprocess.run(command, cwd=ROOT, check=False)
        if process.returncode:
            raise RuntimeError(f"search command failed: {' '.join(command)}")
    manifest = {"schema_version": "chia-rdo.phase3-online-search.v1", "status": "PASS",
                "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "backend": os.environ.get("CHIA_RDO_CLOUD_BACKEND", "local"),
                "online_trials": len(commands) - 1, "commands": commands}
    path = ROOT / "results/experiments/phase3-online-search-manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
