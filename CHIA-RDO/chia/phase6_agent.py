"""History-aware proposal policy for the Phase-6 CHIA graph."""

from __future__ import annotations

import hashlib
import json
import math

from phase6_objectives import pareto_frontier


P_VALUES = (1, 2, 4, 8)
PIPELINE_VALUES = (1, 2, 4)
BUFFER_VALUES = (35, 48, 64)
COST_WIDTH_VALUES = (48, 56)
SCHEDULERS = ("static", "batch_aware", "utilization_aware")
FROZEN_POLICY = {
    "policy_id": "adaptive_threshold_v1_frozen",
    "policy_version": "adaptive-threshold.v1",
    "parameters": {"easy_threshold": 0.04, "hard_threshold": 0.20,
                   "easy_k": 4, "medium_k": 16, "hard_k": 35},
    "immutable_reference": True,
}


def canonical_id(proposal: dict) -> str:
    identity = {key: proposal[key] for key in ("track", "policy", "hardware_configuration",
                                                "measurement_level", "workload_set")}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"phase6-{proposal['track'].lower()}-{digest[:16]}"


def validate_proposal(proposal: dict) -> None:
    hardware = proposal["hardware_configuration"]
    if proposal["track"] not in {"A", "B"}:
        raise ValueError("track must be A or B")
    if hardware["p"] not in P_VALUES or hardware["pipeline_depth"] not in PIPELINE_VALUES:
        raise ValueError("unsupported P or pipeline depth")
    if hardware["buffer_depth"] not in BUFFER_VALUES or hardware["cost_width"] not in COST_WIDTH_VALUES:
        raise ValueError("unsupported buffer depth or cost width")
    if hardware["scheduler_architecture"] not in SCHEDULERS:
        raise ValueError("unsupported scheduler architecture")
    policy = proposal["policy"]
    if proposal["track"] == "A" and policy != FROZEN_POLICY:
        raise ValueError("Track A must use the immutable frozen policy")
    if proposal["track"] == "B" and (not policy.get("policy_id") or not policy.get("policy_version")):
        raise ValueError("Track B policies require a new ID and version")
    if policy.get("policy_id") == FROZEN_POLICY["policy_id"] and policy != FROZEN_POLICY:
        raise ValueError("the frozen policy cannot be redefined")


def candidate_pool() -> list[dict]:
    proposals = []
    for p in P_VALUES:
        proposals.append({
            "track": "A", "policy": FROZEN_POLICY,
            "hardware_configuration": {"p": p, "pipeline_depth": 2, "buffer_depth": 35,
                                       "cost_width": 56, "scheduler_architecture": "static",
                                       "pe_architecture": "full_rdo_mvp_4x4"},
            "measurement_level": 2, "workload_set": "phase4-heldout-matched",
            "hypothesis": f"measure frozen-policy scaling at P={p}",
        })
    for p in P_VALUES:
        for depth in PIPELINE_VALUES:
            for buffer_depth in BUFFER_VALUES:
                for width in COST_WIDTH_VALUES:
                    for scheduler in SCHEDULERS:
                        proposals.append({
                            "track": "A", "policy": FROZEN_POLICY,
                            "hardware_configuration": {"p": p, "pipeline_depth": depth,
                                                       "buffer_depth": buffer_depth, "cost_width": width,
                                                       "scheduler_architecture": scheduler,
                                                       "pe_architecture": "full_rdo_mvp_4x4"},
                            "measurement_level": 1, "workload_set": "phase4-heldout-matched",
                            "hypothesis": "screen hardware cost and batch behavior before RTL promotion",
                        })
    policy_variants = (
        ("adaptive_hw_batch_fill_baseline", "adaptive-hw-batch-fill.v1", "batch_boundary"),
        ("adaptive_hw_v1_p8", "adaptive-hw-v1.analytical-cost.v1", "existing_full_feature_baseline"),
        ("phase6_hw_qp", "hardware-aware.qp.v1", "confidence_qp"),
        ("phase6_hw_qp_p", "hardware-aware.qp-p.v1", "confidence_qp_p"),
        ("phase6_hw_full_state", "hardware-aware.full-state.v1", "full_hardware_state"),
    )
    for policy_id, version, feature_set in policy_variants:
        for p in P_VALUES:
            proposals.append({
                "track": "B",
                "policy": {"policy_id": policy_id, "policy_version": version,
                           "parameters": {"feature_set": feature_set}, "immutable_reference": False},
                "hardware_configuration": {"p": p, "pipeline_depth": 2, "buffer_depth": 35,
                                           "cost_width": 56, "scheduler_architecture": "batch_aware",
                                           "pe_architecture": "full_rdo_mvp_4x4"},
                "measurement_level": 1, "workload_set": "phase4-heldout-matched",
                "hypothesis": f"test whether {feature_set} merits matched software measurement",
            })
    unique = {}
    for proposal in proposals:
        validate_proposal(proposal)
        proposal = {**proposal, "experiment_id": canonical_id(proposal)}
        unique[proposal["experiment_id"]] = proposal
    return list(unique.values())


def _novelty(proposal: dict, history: list[dict]) -> float:
    hardware = proposal["hardware_configuration"]
    categories = (("p", hardware["p"]), ("pipeline_depth", hardware["pipeline_depth"]),
                  ("buffer_depth", hardware["buffer_depth"]), ("cost_width", hardware["cost_width"]),
                  ("scheduler", hardware["scheduler_architecture"]),
                  ("policy", proposal["policy"]["policy_id"]))
    return sum(1.0 / (1 + sum(row.get("proposal", {}).get("hardware_configuration", {}).get(key) == value
                               if key != "policy" and key != "scheduler" else
                               (row.get("policy_id") == value if key == "policy" else
                                row.get("hardware_configuration", {}).get("scheduler_architecture") == value)
                               for row in history)) for key, value in categories)


def propose(history: list[dict], count: int) -> list[dict]:
    """Select a diverse initial wave, then refine around the measured frontier."""
    if count < 1:
        raise ValueError("proposal count must be positive")
    completed = {row["experiment_id"] for row in history}
    available = [proposal for proposal in candidate_pool() if proposal["experiment_id"] not in completed]
    frontier = pareto_frontier(history) if history else []
    frontier_p = {row["hardware_configuration"]["p"] for row in frontier}
    for proposal in available:
        hardware = proposal["hardware_configuration"]
        base = _novelty(proposal, history)
        rtl_bonus = 8.0 if proposal["measurement_level"] == 2 else 0.0
        track_bonus = 20.0 if history and proposal["track"] == "B" else 0.0
        frontier_bonus = 2.0 if frontier and hardware["p"] in frontier_p else 0.0
        boundary_bonus = 1.0 if hardware["p"] in {4, 8} else 0.0
        proposal["information_gain_score"] = base + rtl_bonus + track_bonus + frontier_bonus + boundary_bonus
        proposal["parent_experiment_id"] = (frontier[0]["experiment_id"] if frontier else None)
    return sorted(available, key=lambda row: (-row["information_gain_score"], row["experiment_id"]))[:count]
