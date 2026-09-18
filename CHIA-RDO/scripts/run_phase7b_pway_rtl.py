#!/usr/bin/env python3
"""Run optimized P-way Full-RDO RTL configurations with Verilator."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROUP_FILE = ROOT / "tests/full_rdo/vectors/pway_groups.jsonl"
OUTPUT = ROOT / "results/phase7b/pway_rtl_gate.json"


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def write_memory(directory: Path, name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (directory / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values),
        encoding="ascii",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p", action="append", type=int, choices=range(1, 17), dest="p_values")
    parser.add_argument("--pipeline-depth", action="append", type=int, choices=(2, 3), dest="depths")
    parser.add_argument("--cost-width", action="append", type=int, dest="cost_widths")
    parser.add_argument("--groups", type=int, default=64)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if not 1 <= args.groups <= 256:
        parser.error("groups must be in 1..256")
    if any(not 31 <= width <= 56 for width in (args.cost_widths or (56,))):
        parser.error("cost-width must be in 31..56")
    corpus = GROUP_FILE.read_bytes()
    groups = [json.loads(line) for line in corpus.decode("utf-8").splitlines()][:args.groups]
    sources = (
        ROOT / "rtl/rdo_pe.sv",
        ROOT / "rtl/phase7b/full_rdo_mvp_4x4_serial.sv",
        ROOT / "rtl/phase7b/full_rdo_pway_optimized.sv",
        ROOT / "rtl/phase7b/tb/full_rdo_pway_optimized_tb.sv",
    )
    runs = []
    with tempfile.TemporaryDirectory(prefix="phase7b-pway-") as temporary:
        build = Path(temporary)
        memories = {
            "references": ([pack(row["references"], 8) for row in groups], 136),
            "original": ([pack(row["original"], 8) for row in groups], 128),
            "qp": ([row["qp"] for row in groups], 6),
            "lambda": ([row["lambda_q16"] for row in groups], 32),
            "modes": ([pack(row["modes"], 6) for row in groups], 210),
            "rates": ([pack(row["rate_bits"], 24) for row in groups], 840),
            "costs": ([pack(row["rd_cost_q16"], 56) for row in groups], 1960),
        }
        for k in (4, 16, 35):
            for field, width in (("rank", 6), ("mode", 6), ("cost_q16", 56)):
                name = f"winner_{field.replace('_q16', '')}_k{k}"
                memories[name] = ([row["winners"][str(k)][field] for row in groups], width)
        for name, (values, width) in memories.items():
            write_memory(build, name, values, width)
        for p in (args.p_values or (1, 2, 4, 8)):
            for depth in (args.depths or (2, 3)):
                for cost_width in (args.cost_widths or (56,)):
                    object_dir = build / f"obj_p{p}_d{depth}_w{cost_width}"
                    started = time.monotonic()
                    command = [
                        shutil.which("verilator") or "verilator", "--binary", "--timing", "-Wall",
                        "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-BLKSEQ",
                        "--top-module", "full_rdo_pway_optimized_tb", f"-GP={p}",
                        f"-GPIPELINE_DEPTH={depth}", f"-GGROUP_COUNT={args.groups}",
                        f"-GCOST_WIDTH={cost_width}",
                        "--Mdir", str(object_dir), *map(str, sources),
                    ]
                    compile_process = subprocess.run(
                        command, cwd=build, text=True, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, timeout=600, check=False,
                    )
                    if compile_process.returncode:
                        raise RuntimeError(compile_process.stdout)
                    compile_seconds = time.monotonic() - started
                    started = time.monotonic()
                    simulation = subprocess.run(
                        [str(object_dir / "Vfull_rdo_pway_optimized_tb")], cwd=build,
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        timeout=600, check=False,
                    )
                    if simulation.returncode:
                        raise RuntimeError(simulation.stdout)
                    measured = json.loads(next(
                        line for line in simulation.stdout.splitlines() if line.startswith("{")
                    ))
                    if measured["total_fail"]:
                        raise RuntimeError(
                            f"P={p}, depth={depth}, width={cost_width} failed: {measured}"
                        )
                    measured["compile_seconds"] = compile_seconds
                    measured["simulation_seconds"] = time.monotonic() - started
                    runs.append(measured)
    output = args.output if args.output.is_absolute() else ROOT / args.output
    payload = {
        "schema_version": "chia-rdo.phase7b-pway-rtl.v1",
        "status": "PASS",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "Optimized P-way Full-RDO kernel; not encoder throughput",
        "group_corpus_sha256": hashlib.sha256(corpus).hexdigest(),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sources},
        "total_candidate_evaluations": sum(row["candidate_evaluations"] for row in runs),
        "runs": runs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
