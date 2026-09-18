"""Pareto and information-gain utilities for Phase 6."""

from __future__ import annotations

import math
from statistics import mean


MINIMIZE_AXES = (
    "bd_rate_percent",
    "average_rdo_evaluations",
    "rtl_cycles_per_event",
    "resource_proxy",
)


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def dominates(left: dict, right: dict, axes: tuple[str, ...] = MINIMIZE_AXES) -> bool:
    """Return whether left is no worse on every available objective."""
    if not left.get("feasible") or not right.get("feasible"):
        return False
    common = tuple(axis for axis in axes if _finite(left.get(axis)) and _finite(right.get(axis)))
    if len(common) < 2:
        return False
    return (all(float(left[axis]) <= float(right[axis]) for axis in common)
            and any(float(left[axis]) < float(right[axis]) for axis in common))


def pareto_frontier(rows: list[dict]) -> list[dict]:
    feasible = [row for row in rows if row.get("result_status") == "PASS" and row.get("feasible")
                and all(_finite(row.get(axis)) for axis in MINIMIZE_AXES)]
    for row in rows:
        row["dominated"] = row in feasible and any(
            dominates(other, row) for other in feasible if other["experiment_id"] != row["experiment_id"]
        )
    return sorted((row for row in feasible if not row["dominated"]),
                  key=lambda row: (row.get("rtl_cycles_per_event", math.inf),
                                   row.get("resource_proxy", math.inf), row["experiment_id"]))


def normalized_balanced_score(row: dict, frontier: list[dict]) -> float | None:
    axes = tuple(axis for axis in MINIMIZE_AXES if all(_finite(point.get(axis)) for point in frontier))
    if not axes or not all(_finite(row.get(axis)) for axis in axes):
        return None
    score = 0.0
    for axis in axes:
        values = [float(point[axis]) for point in frontier]
        span = max(values) - min(values)
        score += 0.0 if span == 0 else (float(row[axis]) - min(values)) / span
    return score / len(axes)


def model_rtl_error(rows: list[dict]) -> dict:
    paired = [row for row in rows if _finite(row.get("estimated_cycles"))
              and _finite(row.get("rtl_cycles_per_event")) and row["rtl_cycles_per_event"] != 0]
    if not paired:
        return {"status": "UNAVAILABLE", "pairs": 0, "mae_cycles": None, "mape_percent": None}
    errors = [abs(float(row["estimated_cycles"]) - float(row["rtl_cycles_per_event"])) for row in paired]
    percentages = [error / float(row["rtl_cycles_per_event"]) * 100
                   for error, row in zip(errors, paired)]
    return {"status": "CALIBRATED_RTL_REPLAY", "pairs": len(paired), "mae_cycles": mean(errors),
            "mape_percent": mean(percentages), "maximum_absolute_error_cycles": max(errors),
            "qualification": "Policy-level cycles reweight measured fixed-K RTL cycles; this is not an independent integrated-policy RTL measurement."}
