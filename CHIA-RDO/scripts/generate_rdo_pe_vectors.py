#!/usr/bin/env python3
"""Convert instrumented HM candidate costs into fixed-point RDO PE vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRACTION_BITS = 16
COST_WIDTH = 56


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("traces", nargs="+", type=Path)
    parser.add_argument("--events-per-trace", type=int, default=50)
    parser.add_argument("--output", type=Path, default=ROOT / "results/phase5/rdo_pe_vectors.txt")
    args = parser.parse_args()
    if args.events_per_trace < 1:
        parser.error("--events-per-trace must be positive")

    vectors: list[tuple[int, int, int, int, int]] = []
    errors: list[float] = []
    qp_values: set[int] = set()
    source_events = 0
    trace_metadata = []
    for trace in args.traces:
        accepted = 0
        with trace.open(encoding="utf-8") as stream:
            for line in stream:
                if accepted >= args.events_per_trace:
                    break
                row = json.loads(line)
                required = ("distortion_by_rank", "rate_bits_by_rank", "rd_cost_by_rank", "lambda")
                if not all(field in row for field in required):
                    raise ValueError(f"{trace} is not a Phase-5 instrumented HM trace")
                lambda_q = round(row["lambda"] * (1 << FRACTION_BITS))
                triples = zip(row["distortion_by_rank"], row["rate_bits_by_rank"], row["rd_cost_by_rank"])
                for distortion, rate_bits, hm_cost in triples:
                    cost = (int(distortion) << FRACTION_BITS) + int(rate_bits) * lambda_q
                    vectors.append((int(distortion), int(rate_bits), lambda_q, cost, 0))
                    errors.append(cost / (1 << FRACTION_BITS) - float(hm_cost))
                qp_values.add(int(row["qp"]))
                accepted += 1
        source_events += accepted
        trace_metadata.append({"path": str(trace), "sha256": sha256(trace), "events": accepted})

    maximum = (1 << COST_WIDTH) - 1
    overflow_raw = ((1 << 32) - 1) * (1 << FRACTION_BITS) + ((1 << 24) - 1) * ((1 << 32) - 1)
    vectors.extend(((0, 0, 0, 0, 0), ((1 << 32) - 1, (1 << 24) - 1, (1 << 32) - 1, maximum, int(overflow_raw > maximum))))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="ascii") as stream:
        for vector in vectors:
            stream.write(" ".join(map(str, vector)) + "\n")

    metadata = {
        "schema_version": "chia-rdo.rdo-pe-vectors.v1",
        "formula": "rd_cost_q16 = (distortion << 16) + rate_bits * round(HM_lambda * 65536)",
        "fixed_point": {"lambda": "Q16.16", "cost_fraction_bits": FRACTION_BITS, "cost_width": COST_WIDTH},
        "hm_revision": "22178e370178133438c0339f57b3b3a29f112909",
        "source_traces": trace_metadata,
        "source_events": source_events,
        "hm_vectors": len(vectors) - 2,
        "edge_vectors": 2,
        "total_vectors": len(vectors),
        "qp_values": sorted(qp_values),
        "hm_cost_quantization_error": {
            "minimum": min(errors), "maximum": max(errors),
            "maximum_absolute": max(map(abs, errors)),
        },
        "unsupported_stages": ["prediction", "residual", "transform", "quantization", "reconstruction"],
    }
    metadata_path = args.output.with_suffix(".json")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metadata, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
