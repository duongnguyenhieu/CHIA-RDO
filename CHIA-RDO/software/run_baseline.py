#!/usr/bin/env python3
"""Run and validate the exhaustive HM all-intra Phase 1 baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from generate_sequence import TINY64_SHA256, write_tiny_sequence


ROOT = Path(__file__).resolve().parents[1]
HM_DIR = ROOT / "software" / "third_party" / "HM"
ENCODER = HM_DIR / "bin" / "TAppEncoderStatic"
DECODER = HM_DIR / "bin" / "TAppDecoderStatic"
PRESET = HM_DIR / "cfg" / "encoder_intra_main.cfg"
HM_REVISION = "22178e370178133438c0339f57b3b3a29f112909"
SUMMARY_RE = re.compile(
    r"^\s*(\d+)\s+a\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+"
    r"([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s*$",
    re.MULTILINE,
)
BYTES_RE = re.compile(
    r"^Bytes written to file:\s+(\d+)\s+\(([0-9.eE+-]+)\s+kbps\)\s*$",
    re.MULTILINE,
)
TIME_RE = re.compile(r"^\s*Total Time:\s+([0-9.eE+-]+)\s+sec\.\s*$", re.MULTILINE)
POC_RE = re.compile(
    r"^POC\s+(\d+).*?TId:\s*\d+\s*\(\s*([IPB])-SLICE,\s*"
    r"(?:nQP\s+\d+\s+)?QP\s+(\d+)\s*\)\s+"
    r"(\d+) bits \[Y\s+([0-9.]+) dB\s+U\s+([0-9.]+) dB\s+V\s+([0-9.]+) dB\]",
    re.MULTILINE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unique_match(pattern: re.Pattern[str], text: str, label: str) -> re.Match[str]:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"expected one {label} record, found {len(matches)}")
    return matches[0]


def parse_hm_log(text: str, expected_frames: int) -> dict[str, Any]:
    summary = unique_match(SUMMARY_RE, text, "sequence summary")
    byte_record = unique_match(BYTES_RE, text, "bitstream byte")
    cpu_time = unique_match(TIME_RE, text, "total time")
    pictures = [
        {
            "poc": int(match.group(1)),
            "slice_type": match.group(2),
            "qp": int(match.group(3)),
            "bits": int(match.group(4)),
            "psnr_y_db": float(match.group(5)),
            "psnr_u_db": float(match.group(6)),
            "psnr_v_db": float(match.group(7)),
        }
        for match in POC_RE.finditer(text)
    ]
    if len(pictures) != expected_frames or any(row["slice_type"] != "I" for row in pictures):
        raise RuntimeError(f"expected {expected_frames} I pictures, got {pictures}")
    if int(summary.group(1)) != expected_frames:
        raise RuntimeError("summary frame count does not match configuration")
    return {
        "encoded_frames": int(summary.group(1)),
        "hm_summary_kbps": float(summary.group(2)),
        "psnr_y_db": float(summary.group(3)),
        "psnr_u_db": float(summary.group(4)),
        "psnr_v_db": float(summary.group(5)),
        "psnr_yuv_db": float(summary.group(6)),
        "bitstream_bytes": int(byte_record.group(1)),
        "annex_b_kbps": float(byte_record.group(2)),
        "hm_cpu_time_seconds": float(cpu_time.group(1)),
        "pictures": pictures,
    }


def load_trace(path: Path) -> dict[str, Any]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"invalid trace JSON at line {line_number}: {exc}") from exc
            if row.get("event") != "intra_luma_rdo":
                raise RuntimeError(f"unexpected trace event at line {line_number}")
            if row.get("candidate_count") != 35 or len(row.get("ranked_modes", [])) != 35:
                raise RuntimeError(f"non-exhaustive trace event at line {line_number}")
            if sorted(row["ranked_modes"]) != list(range(35)):
                raise RuntimeError(f"invalid ranked mode permutation at line {line_number}")
            rows.append(row)
    if not rows:
        raise RuntimeError("trace contains no intra RDO events")
    counts = [row["candidate_count"] for row in rows]
    return {
        "search_calls": len(rows),
        "rdo_evaluations": sum(row["rdo_candidate_evaluations"] for row in rows),
        "rqt_refinement_evaluations": sum(row["rqt_refinement_evaluations"] for row in rows),
        "average_k": sum(counts) / len(counts),
        "minimum_k": min(counts),
        "maximum_k": max(counts),
        "candidate_modes": 35,
    }


def run_process(argv: list[str], env: dict[str, str], log_path: Path) -> tuple[float, str]:
    started = time.perf_counter_ns()
    process = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    wall_seconds = (time.perf_counter_ns() - started) / 1e9
    log_path.write_text(process.stdout, encoding="utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"command failed ({process.returncode}); see {log_path}")
    return wall_seconds, process.stdout


def git_output(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, check=True,
    ).stdout.strip()


def encoder_argv(config: dict[str, Any], input_path: Path, bitstream: Path, recon: Path) -> list[str]:
    sequence = config["sequence"]
    return [
        str(ENCODER), "-c", str(PRESET), "-i", str(input_path),
        "-b", str(bitstream), "-o", str(recon),
        "-wdt", str(sequence["width"]), "-hgt", str(sequence["height"]),
        "-fr", str(config["frame_rate_hz"]), "-f", str(sequence["frames"]),
        "-q", str(config["qp"]), "--InputBitDepth=8", "--InputBitDepthC=8",
        "--InputChromaFormat=420", "--ConformanceWindowMode=0", "--RateControl=0",
        "--AdaptiveQP=0", "--FEN=0", "--ECU=0", "--FDM=0", "--ESD=0",
        "--TransformSkipFast=0", "--FastUDIUseMPMEnabled=0",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "baseline_smoke.json")
    parser.add_argument("--replicate", default="")
    args = parser.parse_args()
    if args.replicate and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", args.replicate):
        raise RuntimeError("replicate must contain only letters, digits, underscores, or hyphens")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("policy") != "exhaustive":
        raise RuntimeError("Phase 1 baseline requires the exhaustive policy")
    for binary in (ENCODER, DECODER):
        if not binary.is_file():
            raise RuntimeError(f"missing {binary}; run scripts/setup_hm.sh")

    config_digest = hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    experiment_id = f"{config['name']}-{config_digest[:12]}"
    if args.replicate:
        experiment_id += f"-{args.replicate}"
    output_dir = ROOT / "results" / "baseline" / experiment_id
    log_dir = ROOT / "logs" / "baseline" / experiment_id
    result_path = output_dir / "result.json"
    if result_path.exists():
        existing = json.loads(result_path.read_text(encoding="utf-8"))
        if existing.get("status") == "success":
            print(f"cache hit: {experiment_id}")
            return
        raise RuntimeError(f"existing non-success result requires a new --replicate: {result_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    sequence = config["sequence"]
    input_path = ROOT / "datasets" / "generated" / f"{sequence['name']}.yuv"
    sequence_hash = write_tiny_sequence(
        input_path, sequence["width"], sequence["height"], sequence["frames"]
    )
    is_tiny64_fixture = (
        sequence["width"] == 64
        and sequence["height"] == 64
        and sequence["frames"] == 4
        and sequence["generator"] == "tiny-yuv-v1"
    )
    if is_tiny64_fixture and sequence_hash != TINY64_SHA256:
        raise RuntimeError(f"unexpected generated sequence hash: {sequence_hash}")

    base_env = dict(os.environ)
    base_env.update({"LC_ALL": "C", "CHIA_RDO_EXHAUSTIVE": "1"})
    measure_bitstream = output_dir / "measure.bin"
    measure_recon = output_dir / "measure-recon.yuv"
    measure_argv = encoder_argv(config, input_path, measure_bitstream, measure_recon)
    measure_wall, measure_log = run_process(
        measure_argv, base_env, log_dir / "measure.log"
    )
    metrics = parse_hm_log(measure_log, sequence["frames"])

    trace_path = output_dir / "intra-rdo.jsonl"
    trace_bitstream = output_dir / "trace.bin"
    trace_recon = output_dir / "trace-recon.yuv"
    trace_env = dict(base_env)
    trace_env["CHIA_RDO_TRACE"] = str(trace_path)
    trace_argv = encoder_argv(config, input_path, trace_bitstream, trace_recon)
    trace_wall, trace_log = run_process(trace_argv, trace_env, log_dir / "trace.log")
    trace_metrics = parse_hm_log(trace_log, sequence["frames"])
    if {key: metrics[key] for key in metrics if key != "hm_cpu_time_seconds"} != {
        key: trace_metrics[key] for key in trace_metrics if key != "hm_cpu_time_seconds"
    }:
        raise RuntimeError("trace pass changed coding metrics")
    if sha256_file(measure_bitstream) != sha256_file(trace_bitstream):
        raise RuntimeError("trace pass changed bitstream")
    if sha256_file(measure_recon) != sha256_file(trace_recon):
        raise RuntimeError("trace pass changed reconstruction")
    trace_summary = load_trace(trace_path)

    decoded = output_dir / "decoded.yuv"
    decode_log = log_dir / "decode.log"
    run_process([str(DECODER), "-b", str(measure_bitstream), "-o", str(decoded)], base_env, decode_log)
    if sha256_file(decoded) != sha256_file(measure_recon):
        raise RuntimeError("decoder output differs from encoder reconstruction")
    if metrics["bitstream_bytes"] != measure_bitstream.stat().st_size:
        raise RuntimeError("reported bitstream size differs from file size")
    expected_rate = metrics["bitstream_bytes"] * 8 * config["frame_rate_hz"] / sequence["frames"] / 1000
    if abs(expected_rate - metrics["annex_b_kbps"]) > 0.001:
        raise RuntimeError("Annex-B bitrate is inconsistent with file size")

    patch_path = ROOT / "software" / "patches" / "hm-16.20-chia-rdo.patch"
    record = {
        "schema_version": "chia-rdo.baseline.v1",
        "experiment_id": experiment_id,
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "success",
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_worktree_dirty": bool(git_output("status", "--porcelain")),
        "policy": {
            "name": "exhaustive-full-rdo",
            "exhaustive_intra_modes": True,
            "candidate_modes": 35,
            "hm_rqt_speedup_enabled": True,
            "qualification": "All 35 luma modes enter HM's candidate RD loop; stock HHI_RQT_INTRA_SPEEDUP remains enabled.",
        },
        "encoder": {
            "name": "HM",
            "version": "16.20",
            "repository": "https://vcgit.hhi.fraunhofer.de/jvet/HM.git",
            "tag": "HM-16.20",
            "revision": HM_REVISION,
            "patch_sha256": sha256_file(patch_path),
            "binary_sha256": sha256_file(ENCODER),
            "preset_sha256": sha256_file(PRESET),
            "build_flags": "RELEASE_CPPFLAGS=-O3 -Wuninitialized -Wno-error",
        },
        "configuration": {**config, "argv": measure_argv},
        "sequence": {**sequence, "bytes": input_path.stat().st_size, "sha256": sequence_hash},
        "execution": {
            "host": socket.gethostname(),
            "platform": platform.platform(),
            "wall_time_seconds": measure_wall,
            "trace_wall_time_seconds": trace_wall,
            "hm_cpu_time_seconds": metrics.pop("hm_cpu_time_seconds"),
            "cloud_backend": None,
            "cloud_cost_usd": 0.0,
            "replicate": args.replicate or None,
        },
        "metrics": {**metrics, **trace_summary, "bd_rate_percent": None},
        "artifacts": {
            "raw_log": str((log_dir / "measure.log").relative_to(ROOT)),
            "trace": str(trace_path.relative_to(ROOT)),
            "bitstream": str(measure_bitstream.relative_to(ROOT)),
            "reconstruction": str(measure_recon.relative_to(ROOT)),
            "decoded": str(decoded.relative_to(ROOT)),
            "bitstream_sha256": sha256_file(measure_bitstream),
            "reconstruction_sha256": sha256_file(measure_recon),
        },
    }
    result_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result_path.relative_to(ROOT))
    print(json.dumps(record["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
