#!/usr/bin/env python3
"""Replay interpretable Adaptive-K candidates on exhaustive telemetry."""

from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "results/baseline/tiny64-all-intra-full-rdo-qp32-faed5f414b11/intra-rdo.jsonl"
K_LEVELS = (2, 4, 8, 16, 35)


def select(confidence: float, medium: float, high: float, levels: tuple[int, int, int]) -> int:
    return levels[0] if confidence >= high else levels[1] if confidence >= medium else levels[2]


def hardware_fill(k: int, p: int) -> int:
    batches = math.ceil(k / p)
    fitting = [level for level in K_LEVELS if math.ceil(level / p) <= batches]
    return max(fitting)


def main() -> None:
    rows = [json.loads(line) for line in TRACE.open(encoding="utf-8")]
    policies = []
    for medium, high in ((0.02, 0.045), (0.02, 0.088), (0.045, 0.088), (0.045, 0.15)):
        for levels in ((4, 8, 16), (4, 8, 35), (8, 16, 35), (4, 16, 35)):
            decisions = []
            hits = []
            for row in rows:
                costs = [row["rough_cost_by_mode"][mode] for mode in row["ranked_modes"][:2]]
                confidence = (costs[1] - costs[0]) / max(costs[0], 1e-12)
                k = select(confidence, medium, high, levels)
                decisions.append(k)
                hits.append(row["ranked_modes"].index(row["best_mode"]) < k)
            base = {
                "policy_id": f"gap-m{medium:g}-h{high:g}-k{'-'.join(map(str, levels))}",
                "feature": "normalized_top_two_rough_cost_gap",
                "medium_threshold": medium,
                "high_threshold": high,
                "k_levels_high_medium_low": list(levels),
                "average_k": sum(decisions) / len(decisions),
                "winner_retention_rate": sum(hits) / len(hits),
                "rdo_reduction_fraction": 1 - sum(decisions) / (35 * len(decisions)),
                "average_batches_by_p": {str(p): sum(math.ceil(k / p) for k in decisions) / len(decisions) for p in (1, 2, 4, 8)},
                "hardware_fill": {},
            }
            for p in (1, 2, 4, 8):
                filled = [hardware_fill(k, p) for k in decisions]
                filled_hits = [row["ranked_modes"].index(row["best_mode"]) < k for row, k in zip(rows, filled)]
                base["hardware_fill"][str(p)] = {
                    "average_k": sum(filled) / len(filled),
                    "average_batches": sum(math.ceil(k / p) for k in filled) / len(filled),
                    "winner_retention_rate": sum(filled_hits) / len(filled_hits),
                }
            policies.append(base)
    nondominated = []
    for candidate in policies:
        if any(
            other["average_k"] <= candidate["average_k"]
            and other["winner_retention_rate"] >= candidate["winner_retention_rate"]
            and (other["average_k"] < candidate["average_k"] or other["winner_retention_rate"] > candidate["winner_retention_rate"])
            for other in policies
        ):
            continue
        nondominated.append(candidate["policy_id"])
    result = {
        "schema_version": "chia-rdo.policy-replay-sweep.v1",
        "source_trace": str(TRACE.relative_to(ROOT)),
        "records": len(rows),
        "policies": policies,
        "nondominated_policy_ids_for_average_k_vs_retention": nondominated,
        "qualification": "Replay estimates candidate retention on exhaustive states; no coding metrics or runtime are inferred.",
    }
    path = ROOT / "results/analysis/policy-replay-sweep.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(path.relative_to(ROOT))
    for row in sorted(policies, key=lambda item: (item["average_k"], -item["winner_retention_rate"])):
        marker = "*" if row["policy_id"] in nondominated else " "
        print(f"{marker} {row['policy_id']}: K={row['average_k']:.2f}, hit={row['winner_retention_rate']:.2%}")


if __name__ == "__main__":
    main()
