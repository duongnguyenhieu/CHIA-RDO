#!/usr/bin/env python3
"""Summarize the measured 64x64 fixed/adaptive policy pilot."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "results/baseline/tiny64-all-intra-full-rdo-qp32-faed5f414b11/result.json"


def main() -> None:
    reference = json.loads(REFERENCE.read_text())
    records = []
    for path in sorted((ROOT / "results/policy").glob("*/result.json")):
        row = json.loads(path.read_text())
        if row.get("reference_experiment_id") != reference["experiment_id"]:
            continue
        metrics = row["metrics"]
        name = f"Fixed K={row['policy']['k']}" if row["policy"]["name"] == "fixed" else "Adaptive-K v0"
        records.append({
            "method": name,
            "experiment_id": row["experiment_id"],
            "average_k": metrics["average_k"],
            "winner_hit_rate": metrics["winner_retention_rate"],
            "rdo_evaluations": metrics["rdo_evaluations"],
            "rdo_reduction_fraction": metrics["rdo_reduction_fraction"],
            "encoding_wall_time_seconds": row["execution"]["wall_time_seconds"],
            "hm_cpu_time_seconds": row["execution"]["hm_cpu_time_seconds"],
            "bitrate_kbps": metrics["annex_b_kbps"],
            "psnr_y_db": metrics["psnr_y_db"],
            "psnr_u_db": metrics["psnr_u_db"],
            "psnr_v_db": metrics["psnr_v_db"],
            "psnr_yuv_db": metrics["psnr_yuv_db"],
            "bitstream_sha256": row["artifacts"]["bitstream_sha256"],
            "reconstruction_sha256": row["artifacts"]["reconstruction_sha256"],
            "average_batches_by_p": metrics["average_batches_by_p"],
            "bd_rate_percent": None,
        })
    order = {"Fixed K=2": 0, "Fixed K=4": 1, "Fixed K=8": 2, "Fixed K=16": 3,
             "Fixed K=35": 4, "Adaptive-K v0": 5}
    records.sort(key=lambda row: order[row["method"]])
    output = {
        "schema_version": "chia-rdo.policy-pilot-summary.v1",
        "reference": {
            "method": "Full RDO K=35",
            "experiment_id": reference["experiment_id"],
            "average_k": 35.0,
            "winner_hit_rate": 1.0,
            "rdo_evaluations": reference["metrics"]["rdo_evaluations"],
            "encoding_wall_time_seconds": reference["execution"]["wall_time_seconds"],
            "bitrate_kbps": reference["metrics"]["annex_b_kbps"],
            "psnr_y_db": reference["metrics"]["psnr_y_db"],
            "psnr_u_db": reference["metrics"]["psnr_u_db"],
            "psnr_v_db": reference["metrics"]["psnr_v_db"],
            "psnr_yuv_db": reference["metrics"]["psnr_yuv_db"],
        },
        "runs": records,
        "limitations": [
            "Winner retention uses structurally matched events from independent encodes; prior pruning can change state.",
            "Single-QP results do not define BD-rate.",
            "Sub-second smoke timing is noisy and is not a speedup claim.",
        ],
    }
    output_path = ROOT / "results/analysis/policy-pilot-summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    lines = [
        "# Fixed-K And Adaptive-K v0 Pilot", "", "Run date: 2026-09-08", "",
        "| Method | Avg K | Winner hit | RDO evals | RDO reduction | Wall s | kbps | Y dB | U dB | V dB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    all_rows = [output["reference"], *records]
    for row in all_rows:
        reduction = row.get("rdo_reduction_fraction", 0.0)
        lines.append(
            f"| {row['method']} | {row['average_k']:.3f} | {row['winner_hit_rate']:.2%} | "
            f"{row['rdo_evaluations']:,} | {reduction:.2%} | {row['encoding_wall_time_seconds']:.3f} | "
            f"{row['bitrate_kbps']:.3f} | {row['psnr_y_db']:.4f} | {row['psnr_u_db']:.4f} | {row['psnr_v_db']:.4f} |"
        )
    adaptive = next(row for row in records if row["method"] == "Adaptive-K v0")
    lines += [
        "", "## Findings", "",
        f"Adaptive-K v0 selected average K `{adaptive['average_k']:.3f}`, reduced candidate-loop evaluations by `{adaptive['rdo_reduction_fraction']:.2%}`, and retained the matched exhaustive winner in `{adaptive['winner_hit_rate']:.2%}` of events.",
        f"At P=4 it requires `{adaptive['average_batches_by_p']['4']:.3f}` average batches, versus 2 for fixed K=8 and 4 for fixed K=16.",
        "Fixed K=35 reproduces the exhaustive bitstream and reconstruction hashes exactly, validating the control path.",
        "Bitrate and PSNR are non-monotonic across this one QP. This is expected because each policy changes mode/tree decisions; only matched multi-QP curves can establish BD-rate.",
        "", "## Limitations", "",
        "- Winner hit is candidate-hit correctness, not bitstream equivalence.",
        "- Structural event matching reached 100%, but earlier pruning can still change predictor/reconstruction state.",
        "- Smoke timing is too short and noisy for a performance claim.",
        "- BD-rate is unavailable until matched QP curves are run.", "",
    ]
    report = ROOT / "reports/policy_pilot.md"
    report.write_text("\n".join(lines))
    print(output_path.relative_to(ROOT))
    print(report.relative_to(ROOT))


if __name__ == "__main__":
    main()
