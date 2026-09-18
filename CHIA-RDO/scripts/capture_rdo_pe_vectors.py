#!/usr/bin/env python3
"""Reproduce Phase-5 HM traces and golden vectors without changing coding output."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HM = ROOT / "software/third_party/HM"
BUILD = ROOT / "build/phase5/hm_vectors"
BASELINES = {
    22: "tiny64-all-intra-full-rdo-qp22-c65713cdea8f",
    27: "tiny64-all-intra-full-rdo-qp27-3f638e02c14a",
    32: "tiny64-all-intra-full-rdo-qp32-faed5f414b11",
    37: "tiny64-all-intra-full-rdo-qp37-4ecb16d8e573",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    traces = []
    checks = []
    for qp, baseline_id in BASELINES.items():
        trace = BUILD / f"qp{qp}.jsonl"
        bitstream = BUILD / f"qp{qp}.bin"
        reconstruction = BUILD / f"qp{qp}.yuv"
        command = [str(HM / "bin/TAppEncoderStatic"), "-c", str(HM / "cfg/encoder_intra_main.cfg"),
                   "-i", str(ROOT / "datasets/generated/tiny-64x64-4f-yuv420p8.yuv"),
                   "-b", str(bitstream), "-o", str(reconstruction), "-wdt", "64", "-hgt", "64",
                   "-fr", "30", "-f", "4", "-q", str(qp), "--InputBitDepth=8", "--InputBitDepthC=8",
                   "--InputChromaFormat=420", "--ConformanceWindowMode=0", "--RateControl=0",
                   "--AdaptiveQP=0", "--FEN=0", "--ECU=0", "--FDM=0", "--ESD=0",
                   "--TransformSkipFast=0", "--FastUDIUseMPMEnabled=0"]
        environment = os.environ.copy()
        environment.update({"CHIA_RDO_EXHAUSTIVE": "1", "CHIA_RDO_TRACE": str(trace)})
        subprocess.run(command, cwd=ROOT, env=environment, check=True, stdout=subprocess.DEVNULL)
        baseline = ROOT / "results/baseline" / baseline_id / "measure.bin"
        if digest(bitstream) != digest(baseline):
            raise RuntimeError(f"Phase-5 instrumentation changed the QP{qp} bitstream")
        traces.append(trace)
        checks.append({"qp": qp, "bitstream_sha256": digest(bitstream), "baseline_match": True})
    subprocess.run(["python3", "scripts/generate_rdo_pe_vectors.py", *map(str, traces)], cwd=ROOT, check=True)
    path = ROOT / "results/phase5/hm_capture.json"
    path.write_text(json.dumps({"schema_version": "chia-rdo.hm-capture.v1", "status": "pass",
                                "checks": checks}, indent=2, sort_keys=True) + "\n")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
