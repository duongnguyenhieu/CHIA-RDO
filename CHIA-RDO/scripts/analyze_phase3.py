#!/usr/bin/env python3
"""Generate Phase 3 comparisons, Pareto sets, and gate evidence."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))
from analysis import nondominated  # noqa: E402


def mean(rows: list[dict], key: str) -> float:
    return sum(row[key] for row in rows) / len(rows)


def main() -> None:
    database = json.loads((ROOT / "results/experiments/database.json").read_text())
    groups = defaultdict(list)
    for record in database["records"]:
        groups[record["policy"]].append(record)
    summaries = []
    for policy, rows in groups.items():
        p = rows[0]["P"]
        qp32 = [row for row in rows if row["qp"] == 32]
        summaries.append({
            "policy": policy, "P": p, "avg_k": mean(rows, "avg_k"),
            "rdo_reduction": mean(rows, "rdo_reduction"),
            "winner_retention": mean(rows, "winner_retention"),
            "bitrate_qp32": mean(qp32, "bitrate"), "psnr_yuv_qp32": sum(row["psnr"]["yuv"] for row in qp32) / len(qp32),
            "bd_rate_percent": database["policy_bd_rate_percent"][policy],
            "avg_batches": mean(rows, "estimated_batches"), "estimated_cycles": mean(rows, "estimated_cycles"),
            "p8_estimated_cycles": sum(row["estimated_by_p"]["8"]["estimated_cycles"] for row in rows) / len(rows),
        })
    by_name = {row["policy"]: row for row in summaries}
    common_p8_names = ("full_rdo", "fixed_k8", "fixed_k16", "adaptive_v0", "adaptive_v0_aggressive",
                       "adaptive_threshold", "relative_satd", "adaptive_hw_batch_fill_p8", "adaptive_hw_v1_p8")
    common_p8 = [{**by_name[name], "estimated_cycles": by_name[name]["p8_estimated_cycles"], "P": 8}
                 for name in common_p8_names]
    quality_frontier = nondominated(common_p8, ("bd_rate_percent", "estimated_cycles"))
    retention_frontier = nondominated(common_p8, ("estimated_cycles",), ("winner_retention",))
    pareto = {"schema_version": "chia-rdo.phase3-pareto.v1", "comparison_parallelism": 8,
              "quality_cycle_frontier": quality_frontier, "retention_cycle_frontier": retention_frontier,
              "quality_constraint_bd_rate_percent": 1.0,
              "selections": {"quality_oriented": "relative_satd", "speed_oriented": "fixed_k8",
                             "balanced": "adaptive_threshold", "hardware_aware": "adaptive_hw_v1_p8",
                             "selected_for_rtl": "adaptive_threshold"}}
    (ROOT / "results/experiments/pareto.json").write_text(json.dumps(pareto, indent=2, sort_keys=True) + "\n")

    order = ("full_rdo", "fixed_k8", "fixed_k16", "adaptive_v0", "adaptive_threshold", "relative_satd",
             "adaptive_v0_aggressive", "adaptive_hw_batch_fill_p4", "adaptive_hw_batch_fill_p8",
             "adaptive_hw_v1_p4", "adaptive_hw_v1_p8")
    table = []
    for name in order:
        row = by_name[name]
        table.append(f"| {name} | {row['avg_k']:.3f} | {row['rdo_reduction']:.2%} | {row['winner_retention']:.2%} | "
                     f"{row['bitrate_qp32']:.3f} | {row['psnr_yuv_qp32']:.4f} | {row['bd_rate_percent']:+.3f}% | "
                     f"{row['P']} | {row['avg_batches']:.3f} | {row['estimated_cycles']:.3f} |")
    comparison = """# Phase 3 Algorithm Comparison

All values aggregate two deterministic synthetic workloads at matched QP 22/27/32/37. Bitrate and YUV-PSNR columns are the mean of the two QP32 workload measurements; BD-rate uses each workload's Y-PSNR curve and then averages the two BD-rates. Cycle fields are analytical estimates, not FPGA measurements.

| Policy | Avg K | RDO reduction | Winner retention | QP32 kbps | QP32 YUV-PSNR | BD-rate | P | Avg batches | Est. cycles/event |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
""" + "\n".join(table) + "\n\n"
    comparison += """## Answers

1. Adaptive-K v0 is faster than Fixed K=16 but has worse BD-rate and retention; it does not dominate Fixed K=8 or K=16.
2. Adaptive-threshold improves the measured tradeoff: +0.755% BD-rate with 46.7% RDO reduction and 90.2% retention.
3. Relative-SATD improves quality further: +0.528% BD-rate and 96.1% retention, at a smaller 26.8% RDO reduction.
4. Batch-fill adds candidates at unchanged modeled batch cost. Against its exact aggressive-v0 base (+4.925%), P4 reaches +4.581% and P8 +3.574%; it improves quality but saves zero cycles versus that base.
5. Feature-rich HW-v1 strongly improves quality over batch-fill. P8 reaches +0.613%, but relative-SATD still dominates it slightly in both quality and estimated P8 cycles.
6. P changes HW-v1's selected K: the measured average K differs across P=1/2/4/8 because the objective contains batch cost and lane waste.
7. Batch-boundary awareness produces no cycle reduction over its exact base by construction; it provides candidate filling at the same estimated cycles. HW-v1 provides estimated cycle reductions versus Full-RDO through cost-aware K selection.
8. Adaptive-threshold is the balanced point under the 1% BD-rate constraint; relative-SATD is quality-oriented and Fixed K=8 is speed-oriented.
9. The selected controller for the next RTL specification is adaptive-threshold, not HW-v1, because measured data do not justify choosing the more complex controller.
10. Its controller feature vector is `best_rough_cost`, `PU width`, `PU height`, and bit depth, plus configured easy/hard thresholds and K levels. The ranker separately supplies the stable 35-mode rough-cost ordering.

These conclusions apply only to the two deterministic synthetic All-Intra fixtures and are not a general HEVC corpus claim.
"""
    (ROOT / "reports/phase3_algorithm_comparison.md").write_text(comparison)

    (ROOT / "reports/phase3_hardware_model.md").write_text("""# Phase 3 Analytical Hardware Model

This is an estimated hardware cycle model, not measured RTL or FPGA performance.

For K candidates, parallelism P, initial occupied position `q`, pending batches `b_pending`, fill `F`, drain `D`, per-batch RDO service `R`, and batch overhead `O`:

```text
initial_capacity = P - q
new_batches = 1 + ceil(max(0, K - initial_capacity) / P)
batches = new_batches + b_pending
estimated_cycles = F + batches * (R + O) + D
```

The locked experiments use `q=0`, `b_pending=0`, `F=3`, `D=2`, `R=8`, and `O=1`. They separately record candidate evaluations, RD evaluations, batch count, lane utilization, and estimated cycles. P is restricted to 1/2/4/8; K is restricted to 2/4/8/16/35. Invalid P, K, negative latency, zero RDO service, and impossible batch positions are rejected. The model includes fill/drain and lane waste but not measured memory contention, clock frequency, power, or a complete HEVC datapath.
""")

    qtable = "\n".join(f"| {row['policy']} | {row['bd_rate_percent']:+.3f}% | {row['estimated_cycles']:.3f} |" for row in quality_frontier)
    rtable = "\n".join(f"| {row['policy']} | {row['winner_retention']:.2%} | {row['estimated_cycles']:.3f} |" for row in retention_frontier)
    (ROOT / "reports/phase3_pareto.md").write_text(
        "# Phase 3 Pareto Analysis\n\nAll policies are compared at analytical P=8 for a common hardware-width view.\n\n"
        "## BD-rate Versus Estimated Cycles\n\n| Policy | BD-rate | Est. cycles/event |\n|---|---:|---:|\n" + qtable +
        "\n\n## Winner Retention Versus Estimated Cycles\n\n| Policy | Retention | Est. cycles/event |\n|---|---:|---:|\n" + rtable +
        "\n\nAdaptive-threshold is the lowest-cycle point satisfying the strict BD-rate <1% gate. Relative-SATD is the quality-oriented adaptive policy. HW-v1 P8 satisfies the gate but is dominated by relative-SATD on these fixtures.\n"
    )
    print(json.dumps(pareto["selections"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
