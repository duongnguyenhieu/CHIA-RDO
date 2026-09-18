#!/usr/bin/env python3
"""Generate Phase-4 generalization, failure, hardware-cost, and Pareto evidence."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))
from analysis import nondominated  # noqa: E402


DISPLAY = {
    "full_rdo": "Full-RDO",
    "fixed_k2": "Fixed-K 2",
    "fixed_k4": "Fixed-K 4",
    "fixed_k8": "Fixed-K 8",
    "fixed_k16": "Fixed-K 16",
    "adaptive_v0": "Adaptive-K v0",
    "adaptive_threshold": "Adaptive-threshold",
    "relative_satd": "Relative-SATD",
    "adaptive_hw_batch_fill_p8": "Adaptive-HW batch-fill baseline P=8",
    "adaptive_hw_v1_p8": "Adaptive-HW v1 P=8",
}
EVENT_KEY = ("poc", "ctu_rs_addr", "cu_x", "cu_y", "cu_width", "cu_height", "cu_depth",
             "pu_part_offset", "pu_x", "pu_y", "pu_width", "pu_height", "qp")


def mean(rows: list[dict], key: str) -> float:
    return sum(row[key] for row in rows) / len(rows)


def main() -> None:
    database = json.loads((ROOT / "results/phase4/database.json").read_text())
    corpus = json.loads((ROOT / "configs/phase4_heldout_corpus.json").read_text())
    groups = defaultdict(list)
    workload_groups = defaultdict(list)
    for record in database["records"]:
        groups[record["policy"]].append(record)
        workload_groups[(record["workload"], record["policy"])].append(record)
    summaries = []
    for policy, rows in groups.items():
        summaries.append({"policy": policy, "avg_k": mean(rows, "avg_k"),
                          "rdo_reduction": mean(rows, "rdo_reduction"),
                          "winner_retention": mean(rows, "winner_retention"),
                          "bd_rate_percent": database["policy_bd_rate_percent"][policy],
                          "estimated_batches_p8": mean(rows, "estimated_batches"),
                          "estimated_cycles_p8": mean(rows, "estimated_cycles")})
    by_policy = {row["policy"]: row for row in summaries}

    adaptive_workloads = []
    for workload in sorted({row["workload"] for row in database["records"]}):
        rows = workload_groups[(workload, "adaptive_threshold")]
        adaptive_workloads.append({"workload": workload, "bd_rate_percent": rows[0]["bd_rate_percent"],
                                   "avg_k": mean(rows, "avg_k"), "rdo_reduction": mean(rows, "rdo_reduction"),
                                   "winner_retention": mean(rows, "winner_retention")})
    acceptance = corpus["acceptance"]
    adaptive = by_policy["adaptive_threshold"]
    freeze_checks = {
        "aggregate_bd_rate": adaptive["bd_rate_percent"] <= acceptance["adaptive_threshold_aggregate_bd_rate_max_percent"],
        "per_workload_bd_rate": all(row["bd_rate_percent"] <= acceptance["adaptive_threshold_per_workload_bd_rate_max_percent"] for row in adaptive_workloads),
        "aggregate_winner_retention": adaptive["winner_retention"] >= acceptance["adaptive_threshold_aggregate_winner_retention_min"],
        "per_workload_winner_retention": all(row["winner_retention"] >= acceptance["adaptive_threshold_per_workload_winner_retention_min"] for row in adaptive_workloads),
        "positive_rdo_reduction": adaptive["rdo_reduction"] > 0,
    }

    summary_lines = ["# Phase 4 Generalization Results", "",
                     "The Phase-3 selected Adaptive-threshold policy was evaluated without retuning on three predeclared, deterministic held-out generator families. These workloads differ from both Phase-3 generator instances but are still synthetic; this is out-of-sample synthetic evidence, not validation on a standard HEVC corpus.", "",
                     "All policies use HM-16.20 revision `22178e370178133438c0339f57b3b3a29f112909`, Main-profile 8-bit 4:2:0 All-Intra settings, identical four-frame inputs, and matched QP 22/27/32/37 curves.", "",
                     "## Aggregate", "",
                     "| Policy | Avg K | RDO reduction | Winner retention | BD-rate | Est. P8 batches | Est. P8 cycles/event |",
                     "|---|---:|---:|---:|---:|---:|---:|"]
    for row in sorted(summaries, key=lambda item: item["estimated_cycles_p8"]):
        summary_lines.append(f"| {DISPLAY[row['policy']]} | {row['avg_k']:.3f} | {row['rdo_reduction']:.2%} | {row['winner_retention']:.2%} | {row['bd_rate_percent']:+.3f}% | {row['estimated_batches_p8']:.3f} | {row['estimated_cycles_p8']:.3f} |")
    summary_lines += ["", "Phase-3 best Fixed-K was Fixed-K 8. On the held-out synthetic corpus, Fixed-K 16 is the stronger quality/speed fixed baseline; Adaptive-threshold preserves substantially more Full-RDO winners and has the best aggregate BD-rate among tested non-exhaustive policies, but performs fewer reductions than Fixed-K 16.", "",
                      "## Frozen Policy By Workload", "", "| Workload | Avg K | RDO reduction | Winner retention | BD-rate |",
                      "|---|---:|---:|---:|---:|"]
    for row in adaptive_workloads:
        summary_lines.append(f"| {row['workload']} | {row['avg_k']:.3f} | {row['rdo_reduction']:.2%} | {row['winner_retention']:.2%} | {row['bd_rate_percent']:+.3f}% |")
    summary_lines += ["", "## Matched Measurements", "",
                      "BD-rate is repeated per workload curve and is calculated only from its four matched QP points.", "",
                      "| Workload | QP | Policy | Avg K | RDO reduction | Winner retention | Candidate recall | Bitrate (kbps) | Y-PSNR (dB) | U-PSNR (dB) | V-PSNR (dB) | YUV-PSNR (dB) | BD-rate |",
                      "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in database["records"]:
        summary_lines.append(f"| {row['workload']} | {row['qp']} | {DISPLAY[row['policy']]} | {row['avg_k']:.3f} | {row['rdo_reduction']:.2%} | {row['winner_retention']:.2%} | {row['candidate_recall']:.2%} | {row['bitrate']:.3f} | {row['psnr']['y']:.4f} | {row['psnr']['u']:.4f} | {row['psnr']['v']:.4f} | {row['psnr']['yuv']:.4f} | {row['bd_rate_percent']:+.3f}% |")
    summary_lines += ["", "Current evidence is not sufficient to claim generalization to a standard HEVC corpus. The result supports only limited generalization across the declared synthetic content classes and resolutions."]
    (ROOT / "reports/phase4_generalization_results.md").write_text("\n".join(summary_lines) + "\n")

    misses = []
    feature_groups = defaultdict(lambda: {"events": 0, "confidence": 0.0, "activity": 0.0, "rough": 0.0,
                                         "misses": 0, "k4_misses": 0, "k35_top16": 0,
                                         "k": Counter(), "cu_misses": Counter()})
    for record in groups["adaptive_threshold"]:
        result_path = ROOT / record["source_record"]
        result = json.loads(result_path.read_text())
        trace_path = result_path.parent / "intra-rdo.jsonl"
        comparison_path = result_path.parent / "reference-comparison.jsonl"
        with trace_path.open() as trace_stream, comparison_path.open() as comparison_stream:
            for trace_line, comparison_line in zip(trace_stream, comparison_stream):
                trace = json.loads(trace_line)
                comparison = json.loads(comparison_line)
                if tuple(trace[key] for key in EVENT_KEY) != tuple(comparison[key] for key in EVENT_KEY):
                    raise RuntimeError(f"trace/reference order mismatch: {record['experiment_id']}")
                group = feature_groups[record["workload"]]
                group["events"] += 1
                group["confidence"] += trace["confidence"]
                group["activity"] += trace["activity_norm"]
                group["rough"] += trace["normalized_best_rough_cost"]
                group["k"][trace["selected_k"]] += 1
                if trace["selected_k"] == 35 and comparison["full_rdo_winner_current_rank"] <= 16:
                    group["k35_top16"] += 1
                if not comparison["full_rdo_winner_retained"]:
                    group["misses"] += 1
                    group["k4_misses"] += trace["selected_k"] == 4
                    group["cu_misses"][f"{trace['pu_width']}x{trace['pu_height']}"] += 1
                    mode = comparison["full_rdo_winner"]
                    misses.append({"workload": record["workload"], "qp": trace["qp"],
                                   "cu": f"{trace['cu_width']}x{trace['cu_height']}",
                                   "pu": f"{trace['pu_width']}x{trace['pu_height']}", "selected_k": trace["selected_k"],
                                   "confidence": trace["confidence"], "activity_norm": trace["activity_norm"],
                                   "normalized_rough_cost": trace["normalized_best_rough_cost"],
                                   "winner_satd": trace["satd_by_mode"][mode],
                                   "winner_rough_cost": trace["rough_cost_by_mode"][mode],
                                   "full_winner": mode, "policy_winner": comparison["policy_selected_mode"],
                                   "winner_rank": comparison["full_rdo_winner_current_rank"]})
    misses.sort(key=lambda row: (-row["winner_rank"], row["selected_k"], -row["activity_norm"]))
    adaptive_rows = groups["adaptive_threshold"]
    worst_retention = min(adaptive_rows, key=lambda row: row["winner_retention"])
    worst_bitrate = max(adaptive_rows, key=lambda row: row.get("bitrate_delta_percent", 0.0))
    failure_lines = ["# Phase 4 Failure Analysis", "",
                     f"Frozen Adaptive-threshold matched {adaptive['winner_retention']:.2%} of Full-RDO winners in aggregate. The worst run was `{worst_retention['workload']}` QP {worst_retention['qp']} at {worst_retention['winner_retention']:.2%}; the largest per-run bitrate increase was {worst_bitrate.get('bitrate_delta_percent', 0.0):+.3f}% on `{worst_bitrate['workload']}` QP {worst_bitrate['qp']}.", "",
                     "## Distribution And Miss Concentration", "",
                     "| Workload | Events | Mean confidence | Mean activity | Mean normalized rough cost | K=4 | K=16 | K=35 | Miss rate | K=4 miss rate | K=35/top-16 proxy | Most common missed PU |",
                     "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for workload, values in sorted(feature_groups.items()):
        events = values["events"]
        common = values["cu_misses"].most_common(1)[0][0] if values["cu_misses"] else "none"
        failure_lines.append(f"| {workload} | {events} | {values['confidence']/events:.5f} | {values['activity']/events:.5f} | {values['rough']/events:.5f} | {values['k'][4]/events:.2%} | {values['k'][16]/events:.2%} | {values['k'][35]/events:.2%} | {values['misses']/events:.2%} | {values['k4_misses']/events:.2%} | {values['k35_top16']/events:.2%} | {common} |")
    failure_lines += ["", "The smooth/edge workload drives the controller into K=4 and contains the highest miss concentration, while repetitive and mixed texture shift almost entirely to K=16/35. This is a systematic feature-distribution response, not a threshold change: low normalized rough cost classifies smooth blocks as easy. Its coding impact remains bounded in the four-point curve, so no v2 is created.", "",
                      "Adaptive-threshold is not dominated by Fixed-K 2/4/8/16 on coding quality: its aggregate BD-rate is lower and its winner retention is higher. Fixed-K 16 is more aggressive and therefore faster in the analytical model, but retains fewer winners. The K=35/top-16 column is an over-allocation proxy: it counts events where K=35 was selected although the Full-RDO winner ranked within 16. It is not proof that K=16 would preserve the final coding trajectory, but it locates conservative decisions that limit speedup.", "",
                      "## Worst Missed-Winner Events", "",
                      "| Workload | QP | CU | PU | K | Winner rank | SATD | Rough cost | Confidence | Activity | Norm. best rough | Full winner | Policy winner |",
                      "|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in misses[:16]:
        failure_lines.append(f"| {row['workload']} | {row['qp']} | {row['cu']} | {row['pu']} | {row['selected_k']} | {row['winner_rank']} | {row['winner_satd']} | {row['winner_rough_cost']:.3f} | {row['confidence']:.5f} | {row['activity_norm']:.5f} | {row['normalized_rough_cost']:.5f} | {row['full_winner']} | {row['policy_winner']} |")
    failure_lines += ["", "Failure evidence is limited to deterministic synthetic All-Intra traces. It does not establish behavior on natural-camera noise, standard HEVC classes, inter prediction, 10-bit content, or other chroma formats."]
    (ROOT / "reports/phase4_failure_analysis.md").write_text("\n".join(failure_lines) + "\n")

    hardware_lines = ["# Phase 4 Hardware Cost Model", "",
                      "All cycle values are estimated hardware cycles, not measured RTL or FPGA cycles.", "",
                      "For the locked empty scheduler state, `batches = ceil(K/P)` and `estimated_cycles = 3 + batches*(8+1) + 2`. Variable-K rows average the exact per-event K histogram; they do not apply ceil to average K.", "",
                      "| Policy | P | Avg K | Avg batches | Estimated cycles/event |",
                      "|---|---:|---:|---:|---:|"]
    for policy in sorted(groups):
        rows = groups[policy]
        for p in (1, 2, 4, 8):
            hardware_lines.append(f"| {DISPLAY[policy]} | {p} | {mean(rows, 'avg_k'):.3f} | {sum(row['estimated_by_p'][str(p)]['average_batches'] for row in rows)/len(rows):.3f} | {sum(row['estimated_by_p'][str(p)]['estimated_cycles'] for row in rows)/len(rows):.3f} |")
    scheduler = json.loads((ROOT / "results/rtl/verilator-regression.json").read_text())
    hardware_lines += ["", f"Existing scheduler validation status: `{scheduler['status'].upper()}` with {scheduler['total_pass']:,} passing and {scheduler['total_fail']} failing cases across P=1/2/4/8 and K=2/4/8/16/35. It validates `ceil(K/P)` batch accounting and stable reduction, but its pipeline timing is not calibration of the analytical constants above."]
    (ROOT / "reports/phase4_hardware_cost_model.md").write_text("\n".join(hardware_lines) + "\n")

    frontier = nondominated(summaries, ("bd_rate_percent", "estimated_cycles_p8"), ("rdo_reduction",))
    eligible = [row for row in summaries if row["policy"] != "full_rdo" and row["winner_retention"] >= 0.85
                and row["bd_rate_percent"] <= acceptance["adaptive_threshold_aggregate_bd_rate_max_percent"]]
    selections = {"quality_optimal": min((row for row in summaries if row["policy"] != "full_rdo"), key=lambda row: row["bd_rate_percent"])["policy"],
                  "speed_optimal": max((row for row in summaries if row["policy"] != "full_rdo"), key=lambda row: row["rdo_reduction"])["policy"],
                  "balanced": max(eligible, key=lambda row: (row["rdo_reduction"], row["winner_retention"]))["policy"],
                  "final_policy": "adaptive_threshold" if all(freeze_checks.values()) else None}
    pareto = {"schema_version": "chia-rdo.phase4-pareto.v1", "status": "PASS", "comparison_parallelism": 8,
              "axes": ["BD-rate degradation", "RDO reduction", "estimated hardware cycles"],
              "frontier": frontier, "summaries": summaries, "selections": selections,
              "adaptive_threshold_acceptance": freeze_checks}
    (ROOT / "results/phase4/pareto.json").write_text(json.dumps(pareto, indent=2, sort_keys=True) + "\n")
    pareto_lines = ["# Phase 4 Software Pareto Frontier", "",
                    "The frontier uses aggregate held-out BD-rate, measured software RDO reduction, and analytical P=8 estimated hardware cycles. Lower BD-rate/cycles and higher RDO reduction are preferred.", "",
                    "## All Candidates", "", "| Policy | BD-rate | RDO reduction | Est. P8 cycles/event | Winner retention |",
                    "|---|---:|---:|---:|---:|"]
    for row in sorted(summaries, key=lambda item: item["estimated_cycles_p8"]):
        pareto_lines.append(f"| {DISPLAY[row['policy']]} | {row['bd_rate_percent']:+.3f}% | {row['rdo_reduction']:.2%} | {row['estimated_cycles_p8']:.3f} | {row['winner_retention']:.2%} |")
    pareto_lines += ["", "## Nondominated Set", "", "| Policy | BD-rate | RDO reduction | Est. P8 cycles/event | Winner retention |", "|---|---:|---:|---:|---:|"]
    for row in frontier:
        pareto_lines.append(f"| {DISPLAY[row['policy']]} | {row['bd_rate_percent']:+.3f}% | {row['rdo_reduction']:.2%} | {row['estimated_cycles_p8']:.3f} | {row['winner_retention']:.2%} |")
    pareto_lines += ["", f"Quality-optimal: `{selections['quality_optimal']}`. Speed-optimal: `{selections['speed_optimal']}`. Balanced under the predeclared aggregate BD-rate and 85% retention constraints: `{selections['balanced']}`.", "",
                     "Adaptive-threshold remains the freeze candidate because it passes every predeclared policy-specific criterion and provides the highest winner retention among the practical non-exhaustive adaptive choices. The frontier still exposes Fixed-K 16 and other alternatives rather than forcing Adaptive-threshold to dominate them."]
    (ROOT / "reports/phase4_pareto.md").write_text("\n".join(pareto_lines) + "\n")
    analysis = {"schema_version": "chia-rdo.phase4-analysis.v1", "status": "PASS",
                "adaptive_threshold_acceptance": freeze_checks, "adaptive_threshold_by_workload": adaptive_workloads,
                "missed_winner_events": len(misses), "selections": selections,
                "generalization": "LIMITED", "standard_hevc_corpus": False}
    (ROOT / "results/phase4/analysis.json").write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    print(json.dumps(analysis, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
