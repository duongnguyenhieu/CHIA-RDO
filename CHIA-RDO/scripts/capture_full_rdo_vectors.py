#!/usr/bin/env python3
"""Capture and validate bounded HM vectors for the 4x4 DC Full-RDO MVP."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HM = ROOT / "software/third_party/HM"
BUILD = ROOT / "build/phase5_1/hm"
VECTOR_DIR = ROOT / "tests/full_rdo/vectors"
sys.path.insert(0, str(ROOT))
from tests.full_rdo.model import evaluate  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_edge_sequences() -> dict[str, Path]:
    paths = {name: BUILD / f"{name}-64x64-4f.yuv" for name in ("flat", "high-contrast")}
    flat = bytearray()
    contrast = bytearray()
    for frame in range(4):
        flat.extend(bytes((0, 64, 128, 255)[frame]) * (64 * 64))
        flat.extend(bytes([128]) * (2 * 32 * 32))
        contrast.extend(bytes(255 if (x + y + frame) % 2 else 0 for y in range(64) for x in range(64)))
        contrast.extend(bytes([128]) * (2 * 32 * 32))
    paths["flat"].write_bytes(flat)
    paths["high-contrast"].write_bytes(contrast)
    return paths


def encoder_command(qp: int, source: Path, trace: Path, bitstream: Path, reconstruction: Path) -> tuple[list[str], dict[str, str]]:
    command = [str(HM / "bin/TAppEncoderStatic"), "-c", str(HM / "cfg/encoder_intra_main.cfg"),
               "-i", str(source),
               "-b", str(bitstream), "-o", str(reconstruction), "-wdt", "64", "-hgt", "64",
               "-fr", "30", "-f", "4", "-q", str(qp), "--InputBitDepth=8", "--InputBitDepthC=8",
               "--InternalBitDepth=8", "--InternalBitDepthC=8", "--InputChromaFormat=420",
               "--ConformanceWindowMode=0", "--RateControl=0", "--AdaptiveQP=0", "--DeltaQpRD=0",
               "--MaxDeltaQP=0", "--FEN=0", "--ECU=0", "--FDM=0", "--ESD=0",
               "--FastUDIUseMPMEnabled=0", "--RDOQ=0", "--RDOQTS=0", "--TransformSkip=0",
               "--TransformSkipFast=0", "--SignHideFlag=0", "--ScalingList=0",
               "--TransquantBypassEnable=0", "--CUTransquantBypassFlagForce=0", "--WaveFrontSynchro=0"]
    environment = os.environ.copy()
    environment.update({"CHIA_RDO_EXHAUSTIVE": "1", "CHIA_FULL_RDO_TRACE": str(trace)})
    return command, environment


def load_pairs(trace: Path) -> list[dict]:
    stages: dict[int, dict] = {}
    bits: dict[int, dict] = {}
    for line in trace.read_text().splitlines():
        row = json.loads(line)
        target = stages if row["event"] == "full_rdo_stage" else bits
        target[row["sample_id"]] = row
    pairs = []
    for sample_id in sorted(stages.keys() & bits.keys()):
        if stages[sample_id]["mode"] != 1:
            continue
        row = {**stages[sample_id], **{key: value for key, value in bits[sample_id].items() if key != "event"}}
        if len(row["references"]) == 17:
            row["references"] = [row["references"][0], *row["references"][1:5], *row["references"][9:13]]
        software = evaluate(row["references"], row["original"], row["qp"])
        for field, expected in software.items():
            if row[field] != expected:
                raise RuntimeError(f"HM/software mismatch at sample {sample_id}, stage {field}")
        row["lambda_q16"] = round(row["lambda"] * 65536)
        row["rd_cost_q16"] = (row["distortion"] << 16) + row["rate_bits"] * row["lambda_q16"]
        row["event"] = "full_rdo_vector"
        pairs.append(row)
    return pairs


def main() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)
    sources_by_name = {"tiny": ROOT / "datasets/generated/tiny-64x64-4f-yuv420p8.yuv", **write_edge_sequences()}
    selected_by_name = {"tiny": 32, "flat": 16, "high-contrast": 16}
    vectors = []
    sources = []
    for qp in (22, 27, 32, 37):
        for name, source in sources_by_name.items():
            trace = BUILD / f"{name}-qp{qp}.jsonl"
            bitstream = BUILD / f"{name}-qp{qp}.bin"
            reconstruction = BUILD / f"{name}-qp{qp}.recon.yuv"
            command, environment = encoder_command(qp, source, trace, bitstream, reconstruction)
            subprocess.run(command, cwd=ROOT, env=environment, check=True, stdout=subprocess.DEVNULL)
            pairs = load_pairs(trace)
            selected = selected_by_name[name]
            if len(pairs) < selected:
                raise RuntimeError(f"{name} QP{qp} produced only {len(pairs)} complete vectors")
            selected_pairs = [pairs[round(index * (len(pairs) - 1) / (selected - 1))] for index in range(selected)]
            for pair in selected_pairs:
                pair["source_class"] = name
            vectors.extend(selected_pairs)
            sources.append({"name": name, "qp": qp, "source_sha256": digest(source),
                            "trace_sha256": digest(trace), "bitstream_sha256": digest(bitstream),
                            "complete_pairs": len(pairs), "selected_pairs": selected})

    jsonl = VECTOR_DIR / "full_rdo_4x4_dc.jsonl"
    with jsonl.open("w", encoding="ascii") as stream:
        for vector in vectors:
            stream.write(json.dumps(vector, sort_keys=True, separators=(",", ":")) + "\n")
    flat = VECTOR_DIR / "full_rdo_4x4_dc.txt"
    array_fields = ("prediction", "residual", "transform", "quantized", "dequantized", "inverse_residual", "reconstruction")
    with flat.open("w", encoding="ascii") as stream:
        for vector in vectors:
            fields = [*vector["references"], *vector["original"], vector["qp"], vector["rate_bits"], vector["lambda_q16"]]
            for name in array_fields:
                fields.extend(vector[name])
            fields.extend((vector["distortion"], vector["rd_cost_q16"]))
            stream.write(" ".join(map(str, fields)) + "\n")
    manifest = {
        "schema_version": "chia-rdo.full-rdo-mvp-vectors.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "hm_revision": "22178e370178133438c0339f57b3b3a29f112909",
        "profile": {"block": "4x4", "component": "luma", "bit_depth": 8, "modes": [1],
                    "qps": [22, 27, 32, 37], "rdoq": False, "transform_skip": False,
                    "sign_data_hiding": False, "scaling_lists": False},
        "vector_count": len(vectors), "vectors_per_qp": 64,
        "source_class_counts": {name: sum(row["source_class"] == name for row in vectors) for name in sources_by_name},
        "stage_vector_counts": {name: len(vectors) for name in (*array_fields, "distortion", "rd_cost")},
        "sources": sources, "jsonl_sha256": digest(jsonl), "flat_sha256": digest(flat),
        "software_oracle_validation": "exact match for every captured stage before vector emission",
        "rate_scope": "exact HM xGetIntraBitsQT count supplied to RTL; CABAC estimator not implemented",
    }
    (VECTOR_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
