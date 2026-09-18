#!/usr/bin/env python3
"""Build and run the exact 4x4 Full-RDO RTL gate against captured HM vectors."""

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR_FILE = ROOT / "tests" / "full_rdo" / "vectors" / "full_rdo_4x4_dc.jsonl"
BUILD_DIR = ROOT / "build" / "phase5_1" / "verilator"
RESULT_FILE = ROOT / "results" / "phase5_1" / "rtl_gate.json"


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def write_memory(name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (BUILD_DIR / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values),
        encoding="ascii",
    )


def main() -> None:
    vectors = [json.loads(line) for line in VECTOR_FILE.read_text(encoding="utf-8").splitlines()]
    if len(vectors) != 256:
        raise RuntimeError(f"expected 256 vectors, found {len(vectors)}")

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)
    memories = {
        "references": ([pack([item["references"][0], *item["references"][1:5], 0, 0, 0, 0,
                              *item["references"][5:9], 0, 0, 0, 0], 8) for item in vectors], 136),
        "original": ([pack(item["original"], 8) for item in vectors], 128),
        "qp": ([item["qp"] for item in vectors], 6),
        "rate": ([item["rate_bits"] for item in vectors], 24),
        "lambda": ([item["lambda_q16"] for item in vectors], 32),
        "prediction": ([pack(item["prediction"], 8) for item in vectors], 128),
        "residual": ([pack(item["residual"], 9) for item in vectors], 144),
        "transform": ([pack(item["transform"], 32) for item in vectors], 512),
        "quantized": ([pack(item["quantized"], 16) for item in vectors], 256),
        "dequantized": ([pack(item["dequantized"], 16) for item in vectors], 256),
        "inverse": ([pack(item["inverse_residual"], 16) for item in vectors], 256),
        "reconstruction": ([pack(item["reconstruction"], 8) for item in vectors], 128),
        "distortion": ([item["distortion"] for item in vectors], 32),
        "cost": ([item["rd_cost_q16"] for item in vectors], 56),
    }
    for name, (values, width) in memories.items():
        write_memory(name, values, width)

    verilator = shutil.which("verilator")
    if verilator is None:
        raise RuntimeError("verilator is required")
    sources = [
        ROOT / "rtl" / "rdo_pe.sv",
        ROOT / "rtl" / "full_rdo_codec_4x4.sv",
        ROOT / "rtl" / "full_rdo_mvp_4x4.sv",
        ROOT / "rtl" / "tb" / "full_rdo_mvp_4x4_tb.sv",
    ]
    subprocess.run(
        [verilator, "--binary", "--timing", "-Wall", "-Wno-DECLFILENAME", "--top-module",
         "full_rdo_mvp_4x4_tb", "--Mdir", str(BUILD_DIR / "obj_dir"), *map(str, sources)],
        check=True,
        cwd=BUILD_DIR,
    )
    run = subprocess.run(
        [str(BUILD_DIR / "obj_dir" / "Vfull_rdo_mvp_4x4_tb")],
        check=True,
        cwd=BUILD_DIR,
        text=True,
        capture_output=True,
    )
    result_line = next(line for line in run.stdout.splitlines() if line.startswith("{"))
    result = json.loads(result_line)
    result["status"] = "PASS" if result["total_fail"] == 0 else "FAIL"
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
