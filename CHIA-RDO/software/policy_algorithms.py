"""Reference definitions for CHIA-RDO software policy decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


K_LEVELS = (2, 4, 8, 16, 35)


def quantize_k(required: int, minimum_k: int = 2, maximum_k: int = 35) -> int:
    if minimum_k not in K_LEVELS or maximum_k not in K_LEVELS or minimum_k > maximum_k:
        raise ValueError("K bounds must be ordered members of K_LEVELS")
    bounded = min(max(required, minimum_k), maximum_k)
    return next(k for k in K_LEVELS if k >= bounded and k <= maximum_k)


def normalized_best_rough_cost(best_rough_cost: float, area: int, bit_depth: int = 8) -> float:
    if best_rough_cost < 0 or area <= 0 or bit_depth <= 0 or bit_depth > 16:
        raise ValueError("invalid rough-cost normalization input")
    return best_rough_cost / (area * ((1 << bit_depth) - 1))


def select_adaptive_threshold_k(
    normalized_rough_cost: float,
    easy_threshold: float = 0.08,
    hard_threshold: float = 0.20,
    easy_k: int = 4,
    medium_k: int = 8,
    hard_k: int = 16,
) -> int:
    if not math.isfinite(normalized_rough_cost) or normalized_rough_cost < 0:
        raise ValueError("normalized rough cost must be finite and nonnegative")
    if not 0 <= easy_threshold <= hard_threshold:
        raise ValueError("adaptive thresholds must satisfy 0 <= easy <= hard")
    if any(k not in K_LEVELS for k in (easy_k, medium_k, hard_k)):
        raise ValueError("adaptive K levels must belong to K_LEVELS")
    if normalized_rough_cost <= easy_threshold:
        return easy_k
    if normalized_rough_cost <= hard_threshold:
        return medium_k
    return hard_k


def relative_satd_values(satd_by_mode: Sequence[int]) -> list[float]:
    if len(satd_by_mode) != 35 or any(value < 0 for value in satd_by_mode):
        raise ValueError("relative SATD requires 35 nonnegative mode SATDs")
    reference = min(satd_by_mode)
    denominator = max(reference, 1)
    return [(value - reference) / denominator for value in satd_by_mode]


def select_relative_satd_k(
    satd_by_mode: Sequence[int],
    relative_threshold: float = 0.15,
    minimum_k: int = 4,
    maximum_k: int = 35,
) -> int:
    if not math.isfinite(relative_threshold) or relative_threshold < 0:
        raise ValueError("relative SATD threshold must be finite and nonnegative")
    qualifying = sum(value <= relative_threshold for value in relative_satd_values(satd_by_mode))
    return quantize_k(qualifying, minimum_k, maximum_k)


@dataclass(frozen=True)
class HardwareState:
    parallelism: int
    pipeline_fill_cycles: int = 3
    pipeline_drain_cycles: int = 2
    rdo_cycles_per_batch: int = 8
    batch_overhead_cycles: int = 1
    current_batch_position: int = 0
    pending_batches: int = 0

    def validate(self) -> None:
        if self.parallelism not in (1, 2, 4, 8):
            raise ValueError("parallelism must be one of 1,2,4,8")
        values = (self.pipeline_fill_cycles, self.pipeline_drain_cycles,
                  self.rdo_cycles_per_batch, self.batch_overhead_cycles,
                  self.current_batch_position, self.pending_batches)
        if any(value < 0 for value in values):
            raise ValueError("hardware state values must be nonnegative")
        if self.rdo_cycles_per_batch == 0 or self.current_batch_position >= self.parallelism:
            raise ValueError("invalid RDO cost or batch position")


def estimate_cycles(k: int, state: HardwareState) -> dict[str, float | int]:
    state.validate()
    if k < 1 or k > 35:
        raise ValueError("K must be in [1,35]")
    initial_capacity = state.parallelism - state.current_batch_position
    new_candidates = max(0, k - initial_capacity)
    batches = 1 + math.ceil(new_candidates / state.parallelism) if k else 0
    batches += state.pending_batches
    cycles = (state.pipeline_fill_cycles + batches *
              (state.rdo_cycles_per_batch + state.batch_overhead_cycles) +
              state.pipeline_drain_cycles)
    slots = batches * state.parallelism
    return {
        "batches": batches,
        "estimated_cycles": cycles,
        "lane_slots": slots,
        "lane_utilization": k / slots if slots else 0.0,
        "remaining_batch_capacity": initial_capacity,
    }


def select_adaptive_hw_v1_k(
    *, confidence: float, relative_satd_count: int, activity_norm: float,
    normalized_rough_cost: float, qp: int, block_area: int, state: HardwareState,
    gap_scale: float = 0.10, relative_satd_scale: float = 8.0,
    quality_weight: float = 1.0, cycle_weight: float = 0.30,
    waste_weight: float = 0.05,
) -> tuple[int, dict[str, float]]:
    state.validate()
    numeric = (confidence, activity_norm, normalized_rough_cost, gap_scale,
               relative_satd_scale, quality_weight, cycle_weight, waste_weight)
    if any(not math.isfinite(value) or value < 0 for value in numeric):
        raise ValueError("hardware policy inputs and weights must be finite and nonnegative")
    if gap_scale == 0 or relative_satd_scale == 0 or not 0 <= qp <= 63 or block_area <= 0:
        raise ValueError("invalid hardware policy feature scale")
    gap_uncertainty = 1.0 - min(confidence / gap_scale, 1.0)
    satd_ambiguity = min(relative_satd_count / relative_satd_scale, 1.0)
    activity = min(activity_norm, 1.0)
    rough = min(normalized_rough_cost, 1.0)
    quality_pressure = min(max((37 - qp) / 15.0, 0.0), 1.0)
    size_pressure = min(math.sqrt(block_area / 4096.0), 1.0)
    difficulty = (0.30 * gap_uncertainty + 0.20 * satd_ambiguity + 0.20 * activity +
                  0.10 * rough + 0.10 * quality_pressure + 0.10 * size_pressure)
    full_cycles = float(estimate_cycles(35, state)["estimated_cycles"])
    objectives: dict[int, float] = {}
    for k in K_LEVELS:
        model = estimate_cycles(k, state)
        miss_risk = difficulty * (35 - k) / 35.0
        cycle_ratio = float(model["estimated_cycles"]) / full_cycles
        lane_waste = 1.0 - float(model["lane_utilization"])
        objectives[k] = quality_weight * miss_risk + cycle_weight * cycle_ratio + waste_weight * lane_waste
    selected = min(K_LEVELS, key=lambda k: (objectives[k], k))
    return selected, {
        "difficulty": difficulty,
        "objective": objectives[selected],
        "gap_uncertainty": gap_uncertainty,
        "satd_ambiguity": satd_ambiguity,
    }
