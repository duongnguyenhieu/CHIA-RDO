#!/usr/bin/env python3
"""Capture complete 35-mode HM groups for Phase-5.3 P-way verification."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HM = ROOT / "software" / "third_party" / "HM"
BUILD = ROOT / "build" / "phase5_3" / "hm"
VECTOR_DIR = ROOT / "tests" / "full_rdo" / "vectors"
SOURCE = ROOT / "datasets" / "generated" / "tiny-64x64-4f-yuv420p8.yuv"
QPS = (22, 27, 32, 37)
K_VALUES = (4, 16, 35)
GROUPS_PER_QP = 64
sys.path.insert(0, str(ROOT))
from tests.full_rdo.model import evaluate_candidate  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(qp: int, trace: Path, bitstream: Path) -> tuple[list[str], dict[str, str]]:
    args = [str(HM / "bin" / "TAppEncoderStatic"), "-c", str(HM / "cfg/encoder_intra_main.cfg"),
            "-i", str(SOURCE), "-b", str(bitstream), "-o", str(BUILD / "reconstruction.yuv"),
            "-wdt", "64", "-hgt", "64", "-fr", "30", "-f", "4", "-q", str(qp),
            "--InputBitDepth=8", "--InputBitDepthC=8", "--InternalBitDepth=8", "--InternalBitDepthC=8",
            "--InputChromaFormat=420", "--ConformanceWindowMode=0", "--RateControl=0", "--AdaptiveQP=0",
            "--DeltaQpRD=0", "--MaxDeltaQP=0", "--FEN=0", "--ECU=0", "--FDM=0", "--ESD=0",
            "--FastUDIUseMPMEnabled=0", "--RDOQ=0", "--RDOQTS=0", "--TransformSkip=0",
            "--TransformSkipFast=0", "--SignHideFlag=0", "--ScalingList=0",
            "--TransquantBypassEnable=0", "--CUTransquantBypassFlagForce=0", "--WaveFrontSynchro=0"]
    environment = os.environ.copy()
    environment.update({"CHIA_RDO_EXHAUSTIVE": "1", "CHIA_FULL_RDO_TRACE": str(trace)})
    return args, environment


def complete_groups(trace: Path) -> list[list[dict]]:
    stages = {}
    bits = {}
    for line in trace.read_text().splitlines():
        row = json.loads(line)
        (stages if row["event"] == "full_rdo_stage" else bits)[row["sample_id"]] = row
    grouped = defaultdict(list)
    for sample_id in sorted(stages.keys() & bits.keys()):
        row = {**stages[sample_id], **{key: value for key, value in bits[sample_id].items() if key != "event"}}
        modeled = evaluate_candidate(row["references"], row["original"], row["mode"], row["qp"])
        for stage, expected in modeled.items():
            if row[stage] != expected:
                raise RuntimeError(f"HM/software mismatch sample={sample_id} mode={row['mode']} stage={stage}")
        row["lambda_q16"] = round(row["lambda"] * 65536)
        row["rd_cost_q16"] = (row["distortion"] << 16) + row["rate_bits"] * row["lambda_q16"]
        key = (row["poc"], row["ctu_rs_addr"], row["abs_part_idx"],
               tuple(row["references"]), tuple(row["original"]))
        grouped[key].append(row)
    complete = []
    for rows in grouped.values():
        selected = []
        seen = set()
        for row in rows:
            if row["mode"] not in seen:
                selected.append(row)
                seen.add(row["mode"])
        if seen == set(range(35)):
            complete.append(selected)
    return complete


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    all_candidates = []
    all_groups = []
    traces = []
    group_id = 0
    for qp in QPS:
        trace = BUILD / f"qp{qp}.jsonl"
        bitstream = BUILD / f"qp{qp}.bin"
        args, environment = command(qp, trace, bitstream)
        subprocess.run(args, cwd=ROOT, env=environment, check=True, stdout=subprocess.DEVNULL)
        available = complete_groups(trace)
        if len(available) < GROUPS_PER_QP:
            raise RuntimeError(f"QP {qp}: only {len(available)} complete groups")
        selected = [available[round(index * (len(available) - 1) / (GROUPS_PER_QP - 1))]
                    for index in range(GROUPS_PER_QP)]
        for rows in selected:
            group = {"group_id": group_id, "qp": qp, "lambda_q16": rows[0]["lambda_q16"],
                     "references": rows[0]["references"], "original": rows[0]["original"],
                     "modes": [row["mode"] for row in rows],
                     "rate_bits": [row["rate_bits"] for row in rows],
                     "rd_cost_q16": [row["rd_cost_q16"] for row in rows], "winners": {}}
            for k in K_VALUES:
                winner_rank = min(range(k), key=lambda rank: rows[rank]["rd_cost_q16"])
                group["winners"][str(k)] = {"rank": winner_rank, "mode": rows[winner_rank]["mode"],
                                             "cost_q16": rows[winner_rank]["rd_cost_q16"]}
            all_groups.append(group)
            for rank, row in enumerate(rows):
                row.update({"event": "pway_candidate", "group_id": group_id, "candidate_rank": rank})
                all_candidates.append(row)
            group_id += 1
        traces.append({"qp": qp, "available_groups": len(available), "selected_groups": len(selected),
                       "trace_sha256": digest(trace), "bitstream_sha256": digest(bitstream)})

    candidate_path = VECTOR_DIR / "pway_candidates.jsonl"
    group_path = VECTOR_DIR / "pway_groups.jsonl"
    candidate_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                      for row in all_candidates), encoding="ascii")
    group_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                  for row in all_groups), encoding="ascii")
    manifest = {
        "schema_version": "chia-rdo.pway-vectors.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hm_revision": "22178e370178133438c0339f57b3b3a29f112909",
        "groups": len(all_groups), "candidates": len(all_candidates),
        "mode_counts": Counter(row["mode"] for row in all_candidates),
        "qp_counts": Counter(row["qp"] for row in all_candidates),
        "k_values": list(K_VALUES), "p_values": [1, 2, 4, 8],
        "source_sha256": digest(SOURCE), "traces": traces,
        "candidate_sha256": digest(candidate_path), "group_sha256": digest(group_path),
        "oracle_validation": "all 35 modes exact at every candidate stage before emission",
    }
    manifest_path = VECTOR_DIR / "pway_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
