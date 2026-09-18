#!/usr/bin/env python3
"""Measure all Phase-6 K levels using a derived P-way RTL testbench."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_TB = ROOT / "rtl/tb/full_rdo_pway_tb.sv"
SOURCE_SHA256 = "ebc2dbeff6090c4ff06e61a03e7355dde3c4b81231072ef2255f0513a295e116"
OUTPUT = ROOT / "results/phase6/rtl_k_levels.json"


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one source testbench marker: {old!r}")
    return text.replace(old, new)


def derived_testbench() -> str:
    if hashlib.sha256(SOURCE_TB.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("protected Phase-5.3 testbench hash changed")
    text = SOURCE_TB.read_text()
    text = replace_once(text, "module full_rdo_pway_tb #(", "module phase6_pway_klevel_tb #(")
    text = replace_once(text, "integer cycles_k4 = 0;", "integer cycles_k2 = 0;\n  integer cycles_k4 = 0;\n  integer cycles_k8 = 0;")
    text = replace_once(text, "slot < -1 || slot > 2", "slot < -1 || slot > 4")
    text = replace_once(
        text,
        "if (slot == 0) begin cycles_k4 = integer'(event_cycles); lane_active_k4 = integer'(lane_active_cycles); end\n"
        "      else if (slot == 1) begin cycles_k16 = integer'(event_cycles); lane_active_k16 = integer'(lane_active_cycles); end\n"
        "      else if (slot == 2) begin cycles_k35 = integer'(event_cycles); lane_active_k35 = integer'(lane_active_cycles); end",
        "if (slot == 0) begin cycles_k4 = integer'(event_cycles); lane_active_k4 = integer'(lane_active_cycles); end\n"
        "      else if (slot == 1) begin cycles_k16 = integer'(event_cycles); lane_active_k16 = integer'(lane_active_cycles); end\n"
        "      else if (slot == 2) begin cycles_k35 = integer'(event_cycles); lane_active_k35 = integer'(lane_active_cycles); end\n"
        "      else if (slot == 3) cycles_k2 = integer'(event_cycles);\n"
        "      else if (slot == 4) cycles_k8 = integer'(event_cycles);",
    )
    text = replace_once(
        text,
        "run_event(group_index, 4, 0);\n      run_event(group_index, 16, 1);\n      run_event(group_index, 35, 2);",
        "run_event(group_index, 2, 3);\n      run_event(group_index, 4, 0);\n"
        "      run_event(group_index, 8, 4);\n      run_event(group_index, 16, 1);\n"
        "      run_event(group_index, 35, 2);",
    )
    text = replace_once(text, '\\"events\\":770', '\\"events\\":1282')
    text = replace_once(text, '\\"candidate_evaluations\\":%0d,',
                        '\\"candidate_evaluations\\":%0d,\\"cycles_k2\\":%0d,\\"cycles_k8\\":%0d,')
    text = replace_once(text, "P, 256*(4+16+35)+4, cycles_k4", "P, 256*(2+4+8+16+35)+4, cycles_k2, cycles_k8, cycles_k4")
    return text


def write_memory(directory: Path, name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (directory / f"{name}.mem").write_text("".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values))


def pack(values: list[int], width: int) -> int:
    return sum((value & ((1 << width) - 1)) << (index * width) for index, value in enumerate(values))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codec-path", type=Path, default=ROOT / "rtl/full_rdo_codec_4x4.sv")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--p", action="append", type=int, choices=(1, 2, 4, 8), dest="p_values")
    args = parser.parse_args()
    codec_path = args.codec_path if args.codec_path.is_absolute() else ROOT / args.codec_path
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    groups = [json.loads(line) for line in (ROOT / "tests/full_rdo/vectors/pway_groups.jsonl").read_text().splitlines()]
    runs = []
    with tempfile.TemporaryDirectory(prefix="phase6-klevel-rtl-") as temporary:
        build = Path(temporary)
        testbench = build / "phase6_pway_klevel_tb.sv"
        testbench.write_text(derived_testbench())
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
                memories[f"winner_{field.replace('_q16', '')}_k{k}"] = ([row["winners"][str(k)][field] for row in groups], width)
        for name, (values, width) in memories.items():
            write_memory(build, name, values, width)
        sources = [ROOT / "rtl/rdo_pe.sv", codec_path, ROOT / "rtl/full_rdo_mvp_4x4.sv",
                   ROOT / "rtl/full_rdo_pway.sv"]
        for p in (args.p_values or (1, 2, 4, 8)):
            object_dir = build / f"obj_p{p}"
            command = [shutil.which("verilator") or "verilator", "--binary", "--timing", "-Wall",
                       "-Wno-DECLFILENAME", "-Wno-BLKSEQ", "--top-module", "phase6_pway_klevel_tb", f"-GP={p}",
                       "--Mdir", str(object_dir), *map(str, sources), str(testbench)]
            compile_process = subprocess.run(command, cwd=build, text=True, stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, timeout=300, check=False)
            if compile_process.returncode:
                raise RuntimeError(compile_process.stdout)
            simulation = subprocess.run([str(object_dir / "Vphase6_pway_klevel_tb")], cwd=build,
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        timeout=300, check=False)
            if simulation.returncode:
                raise RuntimeError(simulation.stdout)
            measured = json.loads(next(line for line in simulation.stdout.splitlines() if line.startswith("{")))
            if measured["total_fail"]:
                raise RuntimeError(f"P={p} RTL regression failed: {measured}")
            runs.append(measured)
    payload = {
        "schema_version": "chia-rdo.phase6-klevel-rtl.v1", "status": "PASS",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "P-way 4x4 luma intra DC MVP RDO datapath; not encoder throughput",
        "source_testbench": str(SOURCE_TB.relative_to(ROOT)), "source_testbench_sha256": SOURCE_SHA256,
        "k_values": [2, 4, 8, 16, 35], "runs": runs,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
