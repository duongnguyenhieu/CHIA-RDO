#!/usr/bin/env python3
"""Capture grouped HM vectors for the Phase-5.2 four-mode Full-RDO PE."""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HM = ROOT / "software" / "third_party" / "HM"
BUILD = ROOT / "build" / "phase5_2" / "hm"
VECTOR_DIR = ROOT / "tests" / "full_rdo" / "vectors"
MODES = (0, 1, 10, 26)
QPS = (22, 27, 32, 37)
GROUPS_PER_SOURCE_QP = {"smooth": 129, "edge-heavy": 128, "texture-heavy": 128,
                        "random": 128, "worst-case-signed": 112}
sys.path.insert(0, str(ROOT))
from tests.full_rdo.model import evaluate_candidate  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_sources() -> dict[str, Path]:
    randomizer = random.Random(0xC41A5E52)
    luma_by_name: dict[str, list[int]] = {name: [] for name in (
        "smooth", "edge-heavy", "texture-heavy", "random", "worst-case-signed")}
    for frame in range(4):
        for y in range(64):
            for x in range(64):
                luma_by_name["smooth"].append((2*x + y + 17*frame) & 255)
                luma_by_name["edge-heavy"].append(
                    16 if ((x // 2) + (y // 2) + frame) % 2 == 0 else 240)
                luma_by_name["texture-heavy"].append(
                    (17*x + 29*y + 13*(x ^ y) + 31*frame) & 255)
                luma_by_name["random"].append(randomizer.randrange(256))
                luma_by_name["worst-case-signed"].append(255 if (x + y + frame) & 1 else 0)
    paths = {}
    for name, luma in luma_by_name.items():
        path = BUILD / f"{name}-64x64-4f.yuv"
        payload = bytearray()
        frame_pixels = 64 * 64
        for frame in range(4):
            payload.extend(luma[frame*frame_pixels:(frame+1)*frame_pixels])
            payload.extend(bytes([128]) * (2 * 32 * 32))
        path.write_bytes(payload)
        paths[name] = path
    return paths


def encoder_command(qp: int, source: Path, trace: Path, bitstream: Path) -> tuple[list[str], dict[str, str]]:
    command = [str(HM / "bin" / "TAppEncoderStatic"), "-c", str(HM / "cfg/encoder_intra_main.cfg"),
               "-i", str(source), "-b", str(bitstream), "-o", str(BUILD / "reconstruction.yuv"),
               "-wdt", "64", "-hgt", "64", "-fr", "30", "-f", "4", "-q", str(qp),
               "--InputBitDepth=8", "--InputBitDepthC=8", "--InternalBitDepth=8", "--InternalBitDepthC=8",
               "--InputChromaFormat=420", "--ConformanceWindowMode=0", "--RateControl=0", "--AdaptiveQP=0",
               "--DeltaQpRD=0", "--MaxDeltaQP=0", "--FEN=0", "--ECU=0", "--FDM=0", "--ESD=0",
               "--FastUDIUseMPMEnabled=0", "--RDOQ=0", "--RDOQTS=0", "--TransformSkip=0",
               "--TransformSkipFast=0", "--SignHideFlag=0", "--ScalingList=0",
               "--TransquantBypassEnable=0", "--CUTransquantBypassFlagForce=0", "--WaveFrontSynchro=0"]
    environment = os.environ.copy()
    environment.update({"CHIA_RDO_EXHAUSTIVE": "1", "CHIA_FULL_RDO_TRACE": str(trace)})
    return command, environment


def load_groups(trace: Path) -> list[list[dict]]:
    stages: dict[int, dict] = {}
    bits: dict[int, dict] = {}
    for line in trace.read_text().splitlines():
        row = json.loads(line)
        (stages if row["event"] == "full_rdo_stage" else bits)[row["sample_id"]] = row
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for sample_id in sorted(stages.keys() & bits.keys()):
        row = {**stages[sample_id], **{key: value for key, value in bits[sample_id].items() if key != "event"}}
        modeled = evaluate_candidate(row["references"], row["original"], row["mode"], row["qp"])
        for field, expected in modeled.items():
            if row[field] != expected:
                raise RuntimeError(f"HM/software mismatch at sample {sample_id}, stage {field}")
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
        if seen == set(MODES):
            complete.append(selected)
    return complete


def evenly_select(rows: list[list[dict]], count: int) -> list[list[dict]]:
    if len(rows) < count:
        raise RuntimeError(f"only {len(rows)} complete groups available; {count} required")
    return [rows[round(index * (len(rows) - 1) / (count - 1))] for index in range(count)]


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    sources = write_sources()
    candidates = []
    groups = []
    trace_metadata = []
    group_id = 0
    hm_q16_winner_disagreements = 0
    for qp in QPS:
        for source_class, source in sources.items():
            trace = BUILD / f"{source_class}-qp{qp}.jsonl"
            bitstream = BUILD / f"{source_class}-qp{qp}.bin"
            command, environment = encoder_command(qp, source, trace, bitstream)
            subprocess.run(command, cwd=ROOT, env=environment, check=True, stdout=subprocess.DEVNULL)
            available = load_groups(trace)
            selected = evenly_select(available, GROUPS_PER_SOURCE_QP[source_class])
            for candidate_group in selected:
                q16_winner = min(range(len(candidate_group)), key=lambda rank: candidate_group[rank]["rd_cost_q16"])
                hm_winner = min(range(len(candidate_group)), key=lambda rank: candidate_group[rank]["rd_cost"])
                hm_q16_winner_disagreements += q16_winner != hm_winner
                group_row = {
                    "group_id": group_id,
                    "source_class": source_class,
                    "block_size": 4,
                    "qp": qp,
                    "lambda_q16": candidate_group[0]["lambda_q16"],
                    "references": candidate_group[0]["references"],
                    "original": candidate_group[0]["original"],
                    "modes": [row["mode"] for row in candidate_group],
                    "rate_bits": [row["rate_bits"] for row in candidate_group],
                    "rd_cost_q16": [row["rd_cost_q16"] for row in candidate_group],
                    "winner_rank": q16_winner,
                    "winner_mode": candidate_group[q16_winner]["mode"],
                    "winner_cost_q16": candidate_group[q16_winner]["rd_cost_q16"],
                    "hm_double_winner_mode": candidate_group[hm_winner]["mode"],
                }
                groups.append(group_row)
                for rank, row in enumerate(candidate_group):
                    row.update({"event": "full_rdo_pe_candidate", "group_id": group_id,
                                "candidate_rank": rank, "source_class": source_class})
                    candidates.append(row)
                group_id += 1
            trace_metadata.append({"source_class": source_class, "qp": qp,
                                   "source_sha256": digest(source), "trace_sha256": digest(trace),
                                   "bitstream_sha256": digest(bitstream), "available_groups": len(available),
                                   "selected_groups": len(selected)})

    candidate_path = VECTOR_DIR / "full_rdo_pe_candidates.jsonl"
    group_path = VECTOR_DIR / "full_rdo_pe_groups.jsonl"
    candidate_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                      for row in candidates), encoding="ascii")
    group_path.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                                  for row in groups), encoding="ascii")
    transformed = [value for row in candidates for value in row["transform"]]
    quantized = [value for row in candidates for value in row["quantized"]]
    manifest = {
        "schema_version": "chia-rdo.full-rdo-pe-vectors.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hm_revision": "22178e370178133438c0339f57b3b3a29f112909",
        "candidate_count": len(candidates), "group_count": len(groups),
        "candidate_set": list(MODES), "qps": list(QPS), "supported_block_sizes": [4],
        "source_class_counts": Counter(row["source_class"] for row in candidates),
        "mode_counts": Counter(row["mode"] for row in candidates),
        "qp_counts": Counter(row["qp"] for row in candidates),
        "transform_range": [min(transformed), max(transformed)],
        "quantized_range": [min(quantized), max(quantized)],
        "hm_double_vs_q16_winner_disagreements": hm_q16_winner_disagreements,
        "candidate_jsonl_sha256": digest(candidate_path), "group_jsonl_sha256": digest(group_path),
        "traces": trace_metadata,
        "oracle_validation": "exact integer match at every codec stage before emission",
        "rate_scope": "exact HM xGetIntraBitsQT count supplied to RTL; no hardware CABAC estimator",
    }
    manifest_path = VECTOR_DIR / "full_rdo_pe_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
