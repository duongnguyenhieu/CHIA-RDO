"""Small dependency-free analysis primitives for CHIA-RDO."""

from __future__ import annotations

import math


def _solve(matrix: list[list[float]], values: list[float]) -> list[float]:
    size = len(values)
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular curve fit")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [left - factor * right for left, right in zip(augmented[row], augmented[column])]
    return [augmented[row][-1] for row in range(size)]


def _cubic_fit(x: list[float], y: list[float]) -> list[float]:
    if len(x) != 4 or len(y) != 4 or len(set(x)) != 4:
        raise ValueError("BD-rate requires four distinct points")
    return _solve([[1.0, value, value**2, value**3] for value in x], y)


def _integral(coefficients: list[float], low: float, high: float) -> float:
    return sum(coefficient * (high ** (power + 1) - low ** (power + 1)) / (power + 1)
               for power, coefficient in enumerate(coefficients))


def bd_rate(reference: list[tuple[float, float]], test: list[tuple[float, float]]) -> float:
    """Return Bjontegaard delta rate (%) using cubic log-rate versus PSNR."""
    if len(reference) != 4 or len(test) != 4 or any(rate <= 0 for rate, _ in reference + test):
        raise ValueError("BD-rate requires two positive four-point curves")
    ref_psnr = [psnr for _, psnr in reference]
    test_psnr = [psnr for _, psnr in test]
    low = max(min(ref_psnr), min(test_psnr))
    high = min(max(ref_psnr), max(test_psnr))
    if high <= low:
        raise ValueError("BD-rate curves have no overlapping PSNR interval")
    ref_fit = _cubic_fit(ref_psnr, [math.log(rate) for rate, _ in reference])
    test_fit = _cubic_fit(test_psnr, [math.log(rate) for rate, _ in test])
    average_difference = (_integral(test_fit, low, high) - _integral(ref_fit, low, high)) / (high - low)
    return (math.exp(average_difference) - 1.0) * 100.0


def nondominated(rows: list[dict], minimize: tuple[str, ...], maximize: tuple[str, ...] = ()) -> list[dict]:
    frontier = []
    for candidate in rows:
        dominated = False
        for other in rows:
            no_worse = all(other[key] <= candidate[key] for key in minimize) and all(
                other[key] >= candidate[key] for key in maximize)
            strictly_better = any(other[key] < candidate[key] for key in minimize) or any(
                other[key] > candidate[key] for key in maximize)
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier
