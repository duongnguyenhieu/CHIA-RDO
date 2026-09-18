#!/usr/bin/env python3
"""Run the predeclared Phase-4 held-out, matched multi-QP matrix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "configs/phase4_heldout_corpus.json"
RESULT_ROOT = ROOT / "results/phase4"


def run(command: list[str]) -> None:
    process = subprocess.run(command, cwd=ROOT, check=False)
    if process.returncode:
        raise RuntimeError(f"Phase-4 command failed ({process.returncode}): {' '.join(command)}")


def main() -> None:
    corpus = json.loads(CORPUS_PATH.read_text())
    names = [workload["name"] for workload in corpus["workloads"]]
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", choices=names, action="append")
    parser.add_argument("--qps", type=int, nargs="+", choices=corpus["qps"], default=corpus["qps"])
    args = parser.parse_args()
    selected = set(args.workload or names)
    config_dir = RESULT_ROOT / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    for workload in corpus["workloads"]:
        if workload["name"] not in selected:
            continue
        for qp in args.qps:
            sequence = {key: workload[key] for key in ("name", "generator", "width", "height", "frames", "bit_depth", "chroma_format", "expected_sha256")}
            config = {"schema_version": "chia-rdo.experiment-config.v1",
                      "name": f"{workload['name']}-all-intra-full-rdo-qp{qp}",
                      "policy": "exhaustive", "qp": qp,
                      "frame_rate_hz": workload["frame_rate_hz"], "sequence": sequence,
                      "evaluation_split": corpus["split"]}
            config_path = config_dir / f"{workload['name']}-qp{qp}.json"
            config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n")
            base = [sys.executable, "software/run_policy.py", "--config", str(config_path)]
            commands.append([sys.executable, "software/run_baseline.py", "--config", str(config_path)])
            commands.extend(base + ["--policy", "fixed", "--k", str(k)] for k in (2, 4, 8, 16))
            commands.append(base + ["--policy", "adaptive_v0"])
            commands.append(base + ["--policy", "adaptive_threshold", "--easy-threshold", "0.04",
                                    "--hard-threshold", "0.20", "--easy-k", "4", "--medium-k", "16", "--hard-k", "35"])
            commands.append(base + ["--policy", "relative_satd", "--relative-threshold", "0.50",
                                    "--minimum-k", "8", "--maximum-k", "35"])
            commands.append(base + ["--policy", "adaptive_hw", "--p", "8",
                                    "--high-k", "2", "--medium-k", "4", "--low-k", "8"])
            commands.append(base + ["--policy", "adaptive_hw_v1", "--p", "8"])
    for command in commands:
        run(command)
    manifest = {"schema_version": "chia-rdo.phase4-heldout-matrix.v1", "status": "PASS",
                "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "split": corpus["split"], "corpus": str(CORPUS_PATH.relative_to(ROOT)),
                "workloads": sorted(selected), "qps": args.qps, "commands": commands}
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    (RESULT_ROOT / "matrix-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print((RESULT_ROOT / "matrix-manifest.json").relative_to(ROOT))


if __name__ == "__main__":
    main()
