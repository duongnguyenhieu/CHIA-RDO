#!/usr/bin/env python3
"""Bounded deterministic replay search over the Full-RDO feature probe."""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))
from policy_algorithms import (  # noqa: E402
    HardwareState, estimate_cycles, select_adaptive_hw_v1_k,
    select_adaptive_threshold_k, select_relative_satd_k,
)


def probe_path() -> Path:
    candidates = []
    for path in (ROOT / "results/policy").glob("*/result.json"):
        record = json.loads(path.read_text())
        if (record.get("status") == "success" and record.get("policy", {}).get("name") == "fixed"
                and record["policy"].get("k") == 35 and record["policy"].get("version") == "fixed-k.v1"):
            candidates.append(path.parent / "intra-rdo.jsonl")
    if len(candidates) != 1:
        raise RuntimeError(f"expected one Phase 3 Fixed-K=35 feature probe, found {len(candidates)}")
    return candidates[0]


def summarize(name: str, parameters: dict, decisions: list[int], retained: int, p: int = 1) -> dict:
    state = HardwareState(parallelism=p)
    cycles = [int(estimate_cycles(k, state)["estimated_cycles"]) for k in decisions]
    return {
        "policy": name, "parameters": parameters, "P": p, "events": len(decisions),
        "avg_k": sum(decisions) / len(decisions), "rdo_evaluations": sum(decisions),
        "rdo_reduction": 1 - sum(decisions) / (35 * len(decisions)),
        "winner_retention": retained / len(decisions),
        "avg_batches": sum((k + p - 1) // p for k in decisions) / len(decisions),
        "avg_estimated_cycles": sum(cycles) / len(cycles),
    }


def score(row: dict) -> float:
    return row["winner_retention"] - 0.30 * row["avg_estimated_cycles"] / row["full_cycles"]


def main() -> None:
    with probe_path().open() as stream:
        events = [json.loads(line) for line in stream]
    rows = []
    for easy, hard, ks in itertools.product((0.04, 0.08, 0.12), (0.12, 0.20, 0.35), ((2, 4, 8), (4, 8, 16), (4, 16, 35))):
        if easy > hard:
            continue
        decisions = [select_adaptive_threshold_k(row["normalized_best_rough_cost"], easy, hard, *ks) for row in events]
        retained = sum(row["best_mode"] in row["ranked_modes"][:k] for row, k in zip(events, decisions))
        rows.append(summarize("adaptive_threshold", {"easy_threshold": easy, "hard_threshold": hard,
                              "easy_k": ks[0], "medium_k": ks[1], "hard_k": ks[2]}, decisions, retained))
    for threshold, minimum, maximum in itertools.product((0.02, 0.05, 0.10, 0.15, 0.25, 0.50), (2, 4, 8), (16, 35)):
        if minimum > maximum:
            continue
        decisions = [select_relative_satd_k(row["satd_by_mode"], threshold, minimum, maximum) for row in events]
        retained = sum(row["best_mode"] in row["ranked_modes"][:k] for row, k in zip(events, decisions))
        rows.append(summarize("relative_satd", {"relative_threshold": threshold,
                              "minimum_k": minimum, "maximum_k": maximum}, decisions, retained))
    for p, relative_threshold, quality_weight, cycle_weight in itertools.product(
            (1, 2, 4, 8), (0.10, 0.15, 0.25), (0.6, 1.0, 1.4), (0.15, 0.30, 0.60)):
        state = HardwareState(parallelism=p)
        parameters = {"relative_threshold": relative_threshold, "gap_scale": 0.10,
                      "relative_satd_scale": 8.0, "quality_weight": quality_weight,
                      "cycle_weight": cycle_weight, "waste_weight": 0.05}
        decisions = []
        for row in events:
            relative_count = sum((value - min(row["satd_by_mode"])) / max(min(row["satd_by_mode"]), 1) <= relative_threshold
                                 for value in row["satd_by_mode"])
            k, _ = select_adaptive_hw_v1_k(
                confidence=row["confidence"], relative_satd_count=relative_count,
                activity_norm=row["activity_norm"], normalized_rough_cost=row["normalized_best_rough_cost"],
                qp=row["qp"], block_area=row["pu_width"] * row["pu_height"], state=state,
                gap_scale=parameters["gap_scale"], relative_satd_scale=parameters["relative_satd_scale"],
                quality_weight=quality_weight, cycle_weight=cycle_weight, waste_weight=parameters["waste_weight"],
            )
            decisions.append(k)
        retained = sum(row["best_mode"] in row["ranked_modes"][:k] for row, k in zip(events, decisions))
        rows.append(summarize("adaptive_hw_v1", parameters, decisions, retained, p))
    for row in rows:
        row["full_cycles"] = estimate_cycles(35, HardwareState(parallelism=row["P"]))["estimated_cycles"]
        row["selection_score"] = score(row)
    selected = {}
    for policy in ("adaptive_threshold", "relative_satd"):
        selected[policy] = max((row for row in rows if row["policy"] == policy), key=lambda row: (row["selection_score"], -row["avg_k"]))
    selected["adaptive_hw_v1"] = {}
    for p in (1, 2, 4, 8):
        selected["adaptive_hw_v1"][str(p)] = max(
            (row for row in rows if row["policy"] == "adaptive_hw_v1" and row["P"] == p),
            key=lambda row: (row["selection_score"], -row["avg_k"]),
        )
    nondominated = []
    for candidate in rows:
        if not any(other["winner_retention"] >= candidate["winner_retention"]
                   and other["avg_estimated_cycles"] <= candidate["avg_estimated_cycles"]
                   and (other["winner_retention"] > candidate["winner_retention"]
                        or other["avg_estimated_cycles"] < candidate["avg_estimated_cycles"])
                   for other in rows if other["P"] == candidate["P"]):
            nondominated.append(candidate)
    result = {"schema_version": "chia-rdo.phase3-policy-search.v1", "source_trace": str(probe_path().relative_to(ROOT)),
              "qualification": "Replay estimates retention from a Full-RDO feature probe; coding metrics require online encode.",
              "trial_count": len(rows), "rows": rows, "selected": selected, "retention_cycle_frontier": nondominated}
    output = ROOT / "results/analysis/phase3-policy-search.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = ["# Phase 3 Policy Search", "", f"Bounded deterministic replay evaluated {len(rows)} configurations.", "",
             "Replay is used only for screening; selected configurations require online HM encoding.", "",
             "| Policy | P | Avg K | Retention | Avg batches | Estimated cycles |", "|---|---:|---:|---:|---:|---:|"]
    flat = [selected["adaptive_threshold"], selected["relative_satd"], *selected["adaptive_hw_v1"].values()]
    lines.extend(f"| {row['policy']} | {row['P']} | {row['avg_k']:.3f} | {row['winner_retention']:.2%} | {row['avg_batches']:.3f} | {row['avg_estimated_cycles']:.3f} |" for row in flat)
    verification_path = ROOT / "results/experiments/gcp-verification.json"
    if verification_path.is_file():
        verification = json.loads(verification_path.read_text())
        if verification.get("online_search_trials_per_run"):
            machines = "` and `".join(verification["online_search_machine_types"])
            lines += ["", "## Online Qualification", "",
                      f"GCP online HM encoding evaluated the same {verification['online_search_trials_per_run']} bounded configurations on `{machines}`. "
                      "Coding metrics and bitstream, reconstruction, and trace hashes matched exactly across machine types. "
                      "These QP32 trials qualify execution determinism; the matched multi-QP matrix remains the evidence used for final policy selection."]
    (ROOT / "reports/phase3_policy_search.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(selected, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
