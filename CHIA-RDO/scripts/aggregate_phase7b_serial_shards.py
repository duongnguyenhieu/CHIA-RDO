#!/usr/bin/env python3
"""Validate and aggregate disjoint Phase-7B GCP serial RTL shards."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHARDS = ROOT / "results/phase7b/gcp/shards"
OUTPUT = ROOT / "results/phase7b/serial_rtl_gate.json"
EXPECTED_HASH = "54b0dc5975157800875103377c958e11a929bfdcffa016f9577fd2d34625e3f8"


def main() -> None:
    rows = [json.loads((SHARDS / f"shard-{index}.json").read_text()) for index in range(4)]
    cursor = 0
    for index, row in enumerate(rows):
        if row["shard_id"] != index or row["shard_count"] != 4:
            raise RuntimeError(f"invalid identity for shard {index}")
        if row["start_index"] != cursor or row["end_index_exclusive"] <= cursor:
            raise RuntimeError(f"gap or overlap at shard {index}")
        if row["corpus_sha256"] != EXPECTED_HASH:
            raise RuntimeError(f"corpus hash mismatch at shard {index}")
        if row["status"] != "PASS" or row["total_fail"] != 0:
            raise RuntimeError(f"failing shard {index}")
        cursor = row["end_index_exclusive"]
    if cursor != 8960 or {qp for row in rows for qp in row["qps"]} != {22, 27, 32, 37}:
        raise RuntimeError("shards do not cover the full corpus")

    result = {
        "schema_version": "chia-rdo.phase7b-serial-gate.v1",
        "status": "PASS",
        "execution_backend": "GCP Verilator",
        "worker_count": 4,
        "vectors": sum(row["vectors"] for row in rows),
        "candidate_vector_evaluations": sum(row["vectors"] for row in rows),
        "modes": 35,
        "qps": [22, 27, 32, 37],
        "latency_cycles": 115,
        "stage_fail": sum(row["stage_fail"] for row in rows),
        "interface_fail": sum(row["interface_fail"] for row in rows),
        "total_fail": sum(row["total_fail"] for row in rows),
        "corpus_sha256": EXPECTED_HASH,
        "aggregate_compile_seconds": sum(row["compile_seconds"] for row in rows),
        "aggregate_simulation_seconds": sum(row["simulation_seconds"] for row in rows),
        "shards": rows,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
