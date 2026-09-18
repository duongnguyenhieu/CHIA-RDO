#!/usr/bin/env python3
"""Analyze exhaustive intra-RDO traces without loading them fully into memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACES = [
    ROOT / "results/baseline/tiny64-all-intra-full-rdo-qp32-faed5f414b11/intra-rdo.jsonl",
    ROOT / "results/baseline/synthetic128-all-intra-full-rdo-qp32-2c1671d6cbd5/intra-rdo.jsonl",
]
K_LEVELS = (2, 4, 8, 16, 35)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + end + 1) / 2
        for index in order[start:end]:
            result[index] = rank
        start = end
    return result


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_norm = sum((x - left_mean) ** 2 for x in left)
    right_norm = sum((y - right_mean) ** 2 for y in right)
    if left_norm == 0 or right_norm == 0:
        return None
    return numerator / math.sqrt(left_norm * right_norm)


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(ranks(left), ranks(right))


def auc(scores: list[float], labels: list[int]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    score_ranks = ranks(scores)
    rank_sum = sum(rank for rank, label in zip(score_ranks, labels) if label)
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def validate_row(row: dict[str, Any], line_number: int) -> None:
    arrays = ("ranked_modes", "satd_by_mode", "mode_bits_by_mode", "rough_cost_by_mode", "rd_cost_by_rank")
    if row.get("event") != "intra_luma_rdo" or row.get("policy") != "exhaustive":
        raise RuntimeError(f"line {line_number}: expected exhaustive intra_luma_rdo")
    if any(len(row.get(name, [])) != 35 for name in arrays):
        raise RuntimeError(f"line {line_number}: expected five length-35 arrays")
    if sorted(row["ranked_modes"]) != list(range(35)):
        raise RuntimeError(f"line {line_number}: invalid mode permutation")
    stable = sorted(range(35), key=lambda mode: row["rough_cost_by_mode"][mode])
    if row["ranked_modes"] != stable or row["best_mode"] not in stable:
        raise RuntimeError(f"line {line_number}: invalid ranking or winner")


def analyze_trace(path: Path) -> tuple[dict[str, Any], dict[str, list[float]]]:
    histogram: Counter[int] = Counter()
    by_size: dict[int, list[int]] = defaultdict(list)
    winner_classes: Counter[str] = Counter()
    features: dict[str, list[float]] = defaultdict(list)
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            row = json.loads(line)
            validate_row(row, line_number)
            ranking = row["ranked_modes"]
            satd = row["satd_by_mode"]
            rough = row["rough_cost_by_mode"]
            k_hit = ranking.index(row["best_mode"]) + 1
            histogram[k_hit] += 1
            by_size[row["pu_width"]].append(k_hit)
            winner = row["best_mode"]
            winner_classes["planar"] += winner == 0
            winner_classes["dc"] += winner == 1
            winner_classes["angular"] += winner >= 2
            ranked_satd = [satd[mode] for mode in ranking]
            ranked_rough = [rough[mode] for mode in ranking]
            satd_mean = mean(satd)
            satd1 = ranked_satd[0]
            rough1 = ranked_rough[0]
            features["k_hit"].append(float(k_hit))
            features["top1_hit"].append(float(k_hit == 1))
            features["rough_gap_2_1"].append((ranked_rough[1] - rough1) / max(rough1, 1e-12))
            features["satd_gap_2_1"].append((ranked_satd[1] - satd1) / max(satd1, 1))
            features["satd_2_over_1"].append(ranked_satd[1] / max(satd1, 1))
            features["satd_3_over_1"].append(ranked_satd[2] / max(satd1, 1))
            features["satd_1_over_mean"].append(satd1 / max(satd_mean, 1e-12))
            features["satd_2_over_mean"].append(ranked_satd[1] / max(satd_mean, 1e-12))
            features["satd_coefficient_of_variation"].append(
                math.sqrt(mean([(value - satd_mean) ** 2 for value in satd])) / max(satd_mean, 1e-12)
            )
            features["pu_width"].append(float(row["pu_width"]))
            features["cu_width"].append(float(row["cu_width"]))
            features["qp"].append(float(row["qp"]))

    k_hits = [int(value) for value in features["k_hit"]]
    count = len(k_hits)
    summary = {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "records": count,
        "k_hit_definition": "1 + index(best_mode in ranked_modes)",
        "k_hit_histogram": {str(rank): histogram[rank] for rank in range(1, 36)},
        "k_hit_mean": mean(k_hits),
        "k_hit_median": median(k_hits),
        "k_hit_percentiles": {str(percent): percentile(k_hits, percent / 100) for percent in (75, 90, 95, 99)},
        "winner_recall_at_k": {str(k): sum(value <= k for value in k_hits) / count for k in K_LEVELS},
        "winner_mode_class": dict(winner_classes),
        "by_pu_width": {
            str(size): {
                "records": len(values),
                "mean_k_hit": mean(values),
                "winner_recall_at_k": {str(k): sum(value <= k for value in values) / len(values) for k in K_LEVELS},
            }
            for size, values in sorted(by_size.items(), reverse=True)
        },
        "feature_relationships": {
            name: {
                "spearman_with_k_hit": spearman(values, features["k_hit"]),
                "auc_for_top1_hit": auc(values, [int(value) for value in features["top1_hit"]]),
            }
            for name, values in features.items()
            if name not in {"k_hit", "top1_hit", "qp"}
        },
    }
    return summary, features


def confidence_quintiles(features: dict[str, list[float]]) -> list[dict[str, Any]]:
    scores = features["rough_gap_2_1"]
    hits = [int(value) for value in features["top1_hit"]]
    k_hits = [int(value) for value in features["k_hit"]]
    order = sorted(range(len(scores)), key=scores.__getitem__)
    bins = []
    for index in range(5):
        selected = order[index * len(order) // 5 : (index + 1) * len(order) // 5]
        bins.append({
            "quintile": index + 1,
            "records": len(selected),
            "minimum_confidence": min(scores[item] for item in selected),
            "maximum_confidence": max(scores[item] for item in selected),
            "top1_hit_rate": mean(hits[item] for item in selected),
            "mean_k_hit": mean(k_hits[item] for item in selected),
        })
    return bins


def markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Exhaustive Telemetry Analysis", "", "Analysis date: 2026-09-08", "",
        "`K_hit = 1 + index(best_mode in ranked_modes)`. The ranking includes SATD and mode-bit cost; it is not raw SATD order.", "",
        "## Winner Coverage", "", "| Trace | Records | Mean K_hit | P(K_hit<=2) | <=4 | <=8 | <=16 | <=35 |", "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for trace in result["traces"]:
        recall = trace["winner_recall_at_k"]
        lines.append(f"| `{Path(trace['path']).parent.name}` | {trace['records']:,} | {trace['k_hit_mean']:.3f} | {recall['2']:.3%} | {recall['4']:.3%} | {recall['8']:.3%} | {recall['16']:.3%} | {recall['35']:.3%} |")
    lines += ["", "## Confidence", "", "The tested confidence is `(rough_cost_2 - rough_cost_1) / rough_cost_1`.", ""]
    for trace in result["traces"]:
        relation = trace["feature_relationships"]["rough_gap_2_1"]
        lines.append(f"- `{Path(trace['path']).parent.name}`: Spearman versus K_hit `{relation['spearman_with_k_hit']:.3f}`, top-1 AUC `{relation['auc_for_top1_hit']:.3f}`.")
    lines += ["", "High confidence improves top-1 probability but does not guarantee a shallow winner. Adaptive-K v0 must therefore report misses and coding loss rather than treating this feature as an oracle.", "", "## Limitations", "", "- Both unique traces are deterministic synthetic All-Intra QP32 workloads.", "- Rows are searched CU/PU alternatives and are not independent final-bitstream blocks.", "- QP correlation is unavailable because QP is constant.", "- Approximately three quarters of rows are 4x4 PUs, so aggregate results are size-skewed.", "- Single-QP analysis cannot produce BD-rate.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("traces", nargs="*", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--output", type=Path, default=ROOT / "results/analysis/telemetry-analysis.json")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/telemetry_analysis.md")
    args = parser.parse_args()
    seen: set[str] = set()
    summaries = []
    for path in args.traces:
        digest = sha256_file(path)
        if digest in seen:
            continue
        seen.add(digest)
        summary, features = analyze_trace(path)
        summary["confidence_quintiles"] = confidence_quintiles(features)
        summaries.append(summary)
    result = {"schema_version": "chia-rdo.telemetry-analysis.v1", "traces": summaries}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.write_text(markdown(result), encoding="utf-8")
    print(args.output.relative_to(ROOT))
    print(args.report.relative_to(ROOT))


if __name__ == "__main__":
    main()
