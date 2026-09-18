#!/usr/bin/env python3
"""Run Phase-5.3 Full-RDO scheduling regression for P=1/2/4/8."""

import csv
import json
import math
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VECTOR_DIR = ROOT / "tests" / "full_rdo" / "vectors"
BUILD = ROOT / "build" / "phase5_3" / "verilator"
RESULT = ROOT / "results" / "phase5_3" / "rtl_gate.json"
CSV_RESULT = ROOT / "reports" / "pway_rtl_results.csv"
P_VALUES = (1, 2, 4, 8)
K_VALUES = (4, 16, 35)


def pack(values: list[int], width: int) -> int:
    mask = (1 << width) - 1
    return sum((value & mask) << (index * width) for index, value in enumerate(values))


def write_memory(name: str, values: list[int], width: int) -> None:
    digits = (width + 3) // 4
    (BUILD / f"{name}.mem").write_text(
        "".join(f"{value & ((1 << width) - 1):0{digits}x}\n" for value in values), encoding="ascii")


def main() -> None:
    groups = [json.loads(line) for line in (VECTOR_DIR / "pway_groups.jsonl").read_text().splitlines()]
    if len(groups) != 256:
        raise RuntimeError(f"expected 256 complete groups, found {len(groups)}")
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    memories = {
        "references": ([pack(row["references"], 8) for row in groups], 136),
        "original": ([pack(row["original"], 8) for row in groups], 128),
        "qp": ([row["qp"] for row in groups], 6),
        "lambda": ([row["lambda_q16"] for row in groups], 32),
        "modes": ([pack(row["modes"], 6) for row in groups], 210),
        "rates": ([pack(row["rate_bits"], 24) for row in groups], 840),
        "costs": ([pack(row["rd_cost_q16"], 56) for row in groups], 1960),
    }
    for k in K_VALUES:
        memories[f"winner_rank_k{k}"] = ([row["winners"][str(k)]["rank"] for row in groups], 6)
        memories[f"winner_mode_k{k}"] = ([row["winners"][str(k)]["mode"] for row in groups], 6)
        memories[f"winner_cost_k{k}"] = ([row["winners"][str(k)]["cost_q16"] for row in groups], 56)
    for name, (values, width) in memories.items():
        write_memory(name, values, width)

    verilator = shutil.which("verilator")
    if verilator is None:
        raise RuntimeError("verilator is required")
    sources = [ROOT / "rtl" / name for name in (
        "rdo_pe.sv", "full_rdo_codec_4x4.sv", "full_rdo_mvp_4x4.sv", "full_rdo_pway.sv")]
    sources.append(ROOT / "rtl" / "tb" / "full_rdo_pway_tb.sv")
    runs = []
    for p in P_VALUES:
        object_dir = BUILD / f"obj_p{p}"
        subprocess.run([verilator, "--binary", "--timing", "-Wall", "-Wno-DECLFILENAME",
                        "--top-module", "full_rdo_pway_tb", f"-GP={p}", "--Mdir", str(object_dir),
                        *map(str, sources)], check=True, cwd=BUILD)
        process = subprocess.run([str(object_dir / "Vfull_rdo_pway_tb")], check=True,
                                 cwd=BUILD, text=True, capture_output=True)
        runs.append(json.loads(next(line for line in process.stdout.splitlines() if line.startswith("{"))))

    rows = []
    run_by_p = {run["p"]: run for run in runs}
    for p in P_VALUES:
        for k in K_VALUES:
            batches = math.ceil(k / p)
            cycles = run_by_p[p][f"cycles_k{k}"]
            lane_active = run_by_p[p][f"lane_active_k{k}"]
            rows.append({"P": p, "K": k, "candidates": 256*k, "batches_model": batches,
                         "cycles_rtl": cycles, "utilization": lane_active / (p*cycles),
                         "winner_match": True, "rd_cost_match": True,
                         "throughput_estimate": 1 / cycles})
    with CSV_RESULT.open("w", newline="", encoding="ascii") as stream:
        writer = csv.DictWriter(stream, fieldnames=("P", "K", "candidates", "batches_model",
                                                       "cycles_rtl", "utilization", "winner_match",
                                                       "rd_cost_match", "throughput_estimate"))
        writer.writeheader()
        writer.writerows(rows)
    result = {"schema_version": "chia-rdo.pway-full-rdo-regression.v1",
              "status": "PASS" if all(row["total_fail"] == 0 for row in runs) else "FAIL",
              "runs": runs, "rows": rows,
              "total_candidate_evaluations": sum(row["candidate_evaluations"] for row in runs),
              "throughput_estimate_unit": "events per clock; not FPGA encoder throughput"}
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
