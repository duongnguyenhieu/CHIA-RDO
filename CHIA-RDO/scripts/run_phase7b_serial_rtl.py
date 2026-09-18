#!/usr/bin/env python3
"""Run one disjoint Phase-7B serial Full-RDO RTL vector shard."""

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR_FILE = ROOT / "tests" / "full_rdo" / "vectors" / "pway_candidates.jsonl"
DEFAULT_BUILD = ROOT / "build" / "phase7b" / "serial_verilator"
DEFAULT_RESULT = ROOT / "results" / "phase7b" / "serial_rtl_gate.json"


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def write_memory(build: Path, name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (build / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values),
        encoding="ascii",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--compile-timeout", type=int, default=600)
    parser.add_argument("--simulation-timeout", type=int, default=600)
    parser.add_argument("--pipeline-depth", type=int, default=2)
    args = parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_id < args.shard_count:
        parser.error("shard-id must be in [0, shard-count)")

    corpus = VECTOR_FILE.read_bytes()
    all_vectors = [json.loads(line) for line in corpus.decode("utf-8").splitlines()]
    if len(all_vectors) != 8960:
        raise RuntimeError(f"expected 8960 vectors, found {len(all_vectors)}")
    start = len(all_vectors) * args.shard_id // args.shard_count
    end = len(all_vectors) * (args.shard_id + 1) // args.shard_count
    vectors = all_vectors[start:end]
    if {row["mode"] for row in vectors} != set(range(35)):
        raise RuntimeError("vectors do not cover modes 0..34")

    build = args.build_dir.resolve()
    result_path = args.output.resolve()
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    memories = {
        "mode": ([row["mode"] for row in vectors], 6),
        "qp": ([row["qp"] for row in vectors], 6),
        "references": ([pack(row["references"], 8) for row in vectors], 136),
        "original": ([pack(row["original"], 8) for row in vectors], 128),
        "rate": ([row["rate_bits"] for row in vectors], 24),
        "lambda": ([row["lambda_q16"] for row in vectors], 32),
        "prediction": ([pack(row["prediction"], 8) for row in vectors], 128),
        "residual": ([pack(row["residual"], 9) for row in vectors], 144),
        "transform": ([pack(row["transform"], 32) for row in vectors], 512),
        "quantized": ([pack(row["quantized"], 16) for row in vectors], 256),
        "dequantized": ([pack(row["dequantized"], 16) for row in vectors], 256),
        "inverse": ([pack(row["inverse_residual"], 16) for row in vectors], 256),
        "reconstruction": ([pack(row["reconstruction"], 8) for row in vectors], 128),
        "distortion": ([row["distortion"] for row in vectors], 32),
        "cost": ([row["rd_cost_q16"] for row in vectors], 56),
    }
    for name, (values, width) in memories.items():
        write_memory(build, name, values, width)

    verilator = shutil.which("verilator")
    if verilator is None:
        raise RuntimeError("verilator is required")
    sources = [
        ROOT / "rtl" / "rdo_pe.sv",
        ROOT / "rtl" / "phase7b" / "full_rdo_mvp_4x4_serial.sv",
        ROOT / "rtl" / "phase7b" / "tb" / "full_rdo_mvp_4x4_serial_tb.sv",
    ]
    object_dir = build / "obj_dir"
    compile_started = time.monotonic()
    subprocess.run(
        [verilator, "--binary", "--timing", "-Wall", "-Wno-fatal", "-Wno-DECLFILENAME",
         "-Wno-BLKSEQ",
         "--top-module", "full_rdo_mvp_4x4_serial_tb", "--Mdir", str(object_dir),
         f"-GVECTOR_COUNT={len(vectors)}",
         f"-GPIPELINE_DEPTH={args.pipeline_depth}",
         *map(str, sources)],
        check=True,
        cwd=build,
        timeout=args.compile_timeout,
    )
    compile_seconds = time.monotonic() - compile_started
    simulation_started = time.monotonic()
    process = subprocess.run(
        [str(object_dir / "Vfull_rdo_mvp_4x4_serial_tb")],
        check=True,
        cwd=build,
        text=True,
        capture_output=True,
        timeout=args.simulation_timeout,
    )
    simulation_seconds = time.monotonic() - simulation_started
    result = json.loads(next(line for line in process.stdout.splitlines() if line.startswith("{")))
    result["status"] = "PASS" if result["total_fail"] == 0 else "FAIL"
    result.update({
        "schema_version": "chia-rdo.phase7b-serial-shard.v1",
        "shard_id": args.shard_id,
        "shard_count": args.shard_count,
        "start_index": start,
        "end_index_exclusive": end,
        "qps": sorted({row["qp"] for row in vectors}),
        "modes": len({row["mode"] for row in vectors}),
        "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
        "compile_seconds": compile_seconds,
        "simulation_seconds": simulation_seconds,
        "pipeline_depth": args.pipeline_depth,
    })
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
