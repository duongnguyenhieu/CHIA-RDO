#!/usr/bin/env python3
"""Measure exact observed Phase-7B datapath ranges on the frozen golden corpus."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/full_rdo/vectors/pway_candidates.jsonl"
RESULT = ROOT / "results/phase7b/width_analysis.json"
REPORT = ROOT / "reports/phase7b_width_analysis.md"


FIELDS = {
    "prediction": ("prediction", False),
    "residual": ("residual", True),
    "transform": ("transform", True),
    "quantized": ("quantized", True),
    "dequantized": ("dequantized", True),
    "inverse_residual": ("inverse_residual", True),
    "reconstruction": ("reconstruction", False),
    "distortion": ("distortion", False),
    "rate_bits": ("rate_bits", False),
    "lambda_q16": ("lambda_q16", False),
    "rd_cost_q16": ("rd_cost_q16", False),
}


def signed_width(low: int, high: int) -> int:
    width = 1
    while low < -(1 << (width - 1)) or high > (1 << (width - 1)) - 1:
        width += 1
    return width


def main() -> None:
    rows = [json.loads(line) for line in CORPUS.read_text().splitlines()]
    ranges = {}
    for name, (key, signed) in FIELDS.items():
        values = []
        for row in rows:
            value = row[key]
            values.extend(value if isinstance(value, list) else [value])
        low, high = min(values), max(values)
        width = signed_width(low, high) if signed else max(1, high.bit_length())
        ranges[name] = {"minimum": low, "maximum": high, "signed": signed,
                        "minimum_observed_width_bits": width}
    payload = {
        "schema_version": "chia-rdo.phase7b-width-analysis.v1",
        "updated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "Observed frozen corpus ranges; not a formal proof outside this corpus",
        "vectors": len(rows),
        "qps": sorted({row["qp"] for row in rows}),
        "modes": sorted({row["mode"] for row in rows}),
        "ranges": ranges,
        "minimum_corpus_safe_cost_width": ranges["rd_cost_q16"]["minimum_observed_width_bits"],
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="ascii")
    table = "\n".join(
        f"| {name} | {value['minimum']} | {value['maximum']} | "
        f"{'signed' if value['signed'] else 'unsigned'} | {value['minimum_observed_width_bits']} |"
        for name, value in ranges.items()
    )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "# Phase 7B Width Analysis\n\n"
        f"Measured {len(rows):,} frozen golden vectors across QP 22/27/32/37 and modes 0..34. "
        "These bounds qualify the corpus only; they are not a formal proof for arbitrary inputs.\n\n"
        "| Signal | Minimum | Maximum | Interpretation | Required observed bits |\n"
        "|---|---:|---:|---|---:|\n" + table + "\n\n"
        f"The minimum corpus-safe unsigned RD-cost width is **{payload['minimum_corpus_safe_cost_width']} bits**. "
        "Any narrower configuration must be rejected before RTL promotion; production width reduction "
        "still requires analytical range proof beyond this corpus.\n",
        encoding="ascii",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
