#!/usr/bin/env python3
"""Run one GCP-friendly Phase-7B optimized P-way RTL configuration shard."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR_FILE = ROOT / "tests/full_rdo/vectors/pway_groups.jsonl"
TESTBENCH = ROOT / "rtl/phase7b/tb/full_rdo_pway_optimized_tb.sv"
CONFIGS = tuple((p, depth) for depth in (2, 3) for p in (1, 2, 4, 8))
K_VALUES = (4, 16, 35)
DEFAULT_GROUPS_PER_CONFIG = 32


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def write_memory(build: Path, name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (build / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values),
        encoding="ascii",
    )


def load_groups() -> tuple[bytes, list[dict[str, object]]]:
    corpus = VECTOR_FILE.read_bytes()
    groups = [json.loads(line) for line in corpus.decode("utf-8").splitlines()]
    if len(groups) != 256:
        raise RuntimeError(f"expected 256 P-way groups, found {len(groups)}")
    for index, row in enumerate(groups):
        if len(row["modes"]) != 35 or len(row["rate_bits"]) != 35 or len(row["rd_cost_q16"]) != 35:
            raise RuntimeError(f"group {index} does not contain 35 candidates")
    return corpus, groups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-id", type=int, choices=range(len(CONFIGS)))
    parser.add_argument("--shard-id", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--groups-per-config", type=int, default=DEFAULT_GROUPS_PER_CONFIG)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compile-timeout", type=int, default=1800)
    parser.add_argument("--simulation-timeout", type=int, default=1800)
    parser.add_argument("--list-configs", action="store_true")
    args = parser.parse_args()

    corpus, all_groups = load_groups()
    if args.groups_per_config < 1 or args.groups_per_config * len(CONFIGS) > len(all_groups):
        parser.error(f"groups-per-config must be in 1..{len(all_groups) // len(CONFIGS)}")
    if args.shard_count < 1 or not 0 <= args.shard_id < args.shard_count:
        parser.error("shard-id must be in [0, shard-count)")
    evaluations_per_config = args.groups_per_config * sum(K_VALUES)
    if args.list_configs:
        payload = {
            "configs": [
                {
                    "config_id": config_id,
                    "p": p,
                    "pipeline_depth": depth,
                    "qps": sorted({
                        all_groups[config_id + offset * len(CONFIGS)]["qp"]
                        for offset in range(args.groups_per_config)
                    }),
                }
                for config_id, (p, depth) in enumerate(CONFIGS)
            ],
            "groups_per_config": args.groups_per_config,
            "evaluations_per_config": evaluations_per_config,
            "total_candidate_evaluations": evaluations_per_config * len(CONFIGS),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.config_id is None:
        parser.error("--config-id is required unless --list-configs is used")

    p, pipeline_depth = CONFIGS[args.config_id]
    config_indices = [
        args.config_id + offset * len(CONFIGS)
        for offset in range(args.groups_per_config)
    ]
    config_groups = [all_groups[index] for index in config_indices]
    shard_start = len(config_groups) * args.shard_id // args.shard_count
    shard_end = len(config_groups) * (args.shard_id + 1) // args.shard_count
    groups = config_groups[shard_start:shard_end]
    group_indices = config_indices[shard_start:shard_end]
    if not groups:
        parser.error("shard is empty; reduce shard-count")

    build = (args.build_dir or ROOT / "build/phase7b/pway_optimized"
             / f"config_{args.config_id}_shard_{args.shard_id}").resolve()
    result_path = (args.output or ROOT / "results/phase7b/pway_optimized"
                   / f"config_{args.config_id}_shard_{args.shard_id}.json").resolve()
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    memories = {
        "references": ([pack(row["references"], 8) for row in groups], 136),
        "original": ([pack(row["original"], 8) for row in groups], 128),
        "qp": ([row["qp"] for row in groups], 6),
        "lambda": ([row["lambda_q16"] for row in groups], 32),
        "modes": ([pack(row["modes"], 6) for row in groups], 210),
        "rates": ([pack(row["rate_bits"], 24) for row in groups], 840),
        "costs": ([pack(row["rd_cost_q16"], 56) for row in groups], 1960),
    }
    for name, (values, width) in memories.items():
        write_memory(build, name, values, width)

    verilator = shutil.which("verilator")
    if verilator is None:
        raise RuntimeError("verilator is required on the GCP worker")
    object_dir = build / "obj_dir"
    sources = [
        ROOT / "rtl/rdo_pe.sv",
        ROOT / "rtl/phase7b/full_rdo_mvp_4x4_serial.sv",
        ROOT / "rtl/phase7b/full_rdo_pway_optimized.sv",
        TESTBENCH,
    ]
    compile_started = time.monotonic()
    compile_process = subprocess.run(
        [verilator, "--binary", "--timing", "-Wall", "-Wno-fatal",
         "-Wno-DECLFILENAME", "-Wno-BLKSEQ", "--top-module",
         "full_rdo_pway_optimized_tb", "--Mdir", str(object_dir), f"-GP={p}",
         f"-GPIPELINE_DEPTH={pipeline_depth}", f"-GGROUP_COUNT={len(groups)}",
         *map(str, sources)],
        cwd=build,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.compile_timeout,
        check=False,
    )
    if compile_process.returncode:
        raise RuntimeError(compile_process.stdout)
    compile_seconds = time.monotonic() - compile_started

    simulation_started = time.monotonic()
    simulation = subprocess.run(
        [str(object_dir / "Vfull_rdo_pway_optimized_tb")],
        cwd=build,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.simulation_timeout,
        check=False,
    )
    if simulation.returncode:
        raise RuntimeError(simulation.stdout)
    simulation_seconds = time.monotonic() - simulation_started
    measured = json.loads(next(line for line in simulation.stdout.splitlines() if line.startswith("{")))
    expected_evaluations = len(groups) * sum(K_VALUES)
    if measured["total_fail"] or measured["candidate_evaluations"] != expected_evaluations:
        raise RuntimeError(f"RTL regression failed: {measured}")

    measured.update({
        "schema_version": "chia-rdo.phase7b-pway-optimized-shard.v1",
        "status": "PASS",
        "config_id": args.config_id,
        "shard_id": args.shard_id,
        "shard_count": args.shard_count,
        "corpus_group_indices": group_indices,
        "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
        "k_values": list(K_VALUES),
        "qps": sorted({row["qp"] for row in groups}),
        "compile_seconds": compile_seconds,
        "simulation_seconds": simulation_seconds,
    })
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(measured, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(measured, sort_keys=True))


if __name__ == "__main__":
    main()
