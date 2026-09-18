#!/usr/bin/env python3
"""Build and run the 10,000-candidate Phase-5.2 Full-RDO PE regression."""

import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "tests" / "full_rdo" / "vectors"
BUILD = ROOT / "build" / "phase5_2" / "verilator"
RESULT = ROOT / "results" / "phase5_2" / "rtl_gate.json"


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def write_memory(name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (BUILD / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values), encoding="ascii")


def main() -> None:
    groups = [json.loads(line) for line in (VECTOR_DIR / "full_rdo_pe_groups.jsonl").read_text().splitlines()]
    candidates = [json.loads(line) for line in (VECTOR_DIR / "full_rdo_pe_candidates.jsonl").read_text().splitlines()]
    if len(groups) != 2500 or len(candidates) != 10000:
        raise RuntimeError(f"expected 2500 groups/10000 candidates, found {len(groups)}/{len(candidates)}")
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    group_memories = {
        "group_references": ([pack(row["references"], 8) for row in groups], 136),
        "group_original": ([pack(row["original"], 8) for row in groups], 128),
        "group_qp": ([row["qp"] for row in groups], 6),
        "group_lambda": ([row["lambda_q16"] for row in groups], 32),
        "group_modes": ([pack(row["modes"], 6) for row in groups], 24),
        "group_rates": ([pack(row["rate_bits"], 24) for row in groups], 96),
        "winner_rank": ([row["winner_rank"] for row in groups], 2),
        "winner_mode": ([row["winner_mode"] for row in groups], 6),
        "winner_cost": ([row["winner_cost_q16"] for row in groups], 56),
    }
    candidate_memories = {
        "candidate_mode": ([row["mode"] for row in candidates], 6),
        "prediction": ([pack(row["prediction"], 8) for row in candidates], 128),
        "residual": ([pack(row["residual"], 9) for row in candidates], 144),
        "transform": ([pack(row["transform"], 32) for row in candidates], 512),
        "quantized": ([pack(row["quantized"], 16) for row in candidates], 256),
        "dequantized": ([pack(row["dequantized"], 16) for row in candidates], 256),
        "inverse": ([pack(row["inverse_residual"], 16) for row in candidates], 256),
        "reconstruction": ([pack(row["reconstruction"], 8) for row in candidates], 128),
        "distortion": ([row["distortion"] for row in candidates], 32),
        "bits": ([row["rate_bits"] for row in candidates], 24),
        "cost": ([row["rd_cost_q16"] for row in candidates], 56),
    }
    for name, (values, width) in {**group_memories, **candidate_memories}.items():
        write_memory(name, values, width)

    verilator = shutil.which("verilator")
    if verilator is None:
        raise RuntimeError("verilator is required")
    sources = [ROOT / "rtl" / name for name in (
        "rdo_pe.sv", "full_rdo_codec_4x4.sv", "full_rdo_mvp_4x4.sv", "full_rdo_pe.sv")]
    sources.append(ROOT / "rtl" / "tb" / "full_rdo_pe_tb.sv")
    subprocess.run([verilator, "--binary", "--timing", "-Wall", "-Wno-DECLFILENAME",
                    "--top-module", "full_rdo_pe_tb", "--Mdir", str(BUILD / "obj_dir"),
                    *map(str, sources)], check=True, cwd=BUILD)
    run = subprocess.run([str(BUILD / "obj_dir" / "Vfull_rdo_pe_tb")], check=True,
                         cwd=BUILD, text=True, capture_output=True)
    result = json.loads(next(line for line in run.stdout.splitlines() if line.startswith("{")))
    result["status"] = "PASS" if result["total_fail"] == 0 else "FAIL"
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
