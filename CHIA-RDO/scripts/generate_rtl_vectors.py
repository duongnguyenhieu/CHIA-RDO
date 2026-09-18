#!/usr/bin/env python3
"""Generate scheduler vectors from HM RD traces plus deterministic random cases."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "results/baseline/tiny64-all-intra-full-rdo-qp32-faed5f414b11/intra-rdo.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "build/rtl/golden_vectors.txt")
    args = parser.parse_args()
    vectors: list[list[tuple[int, int]]] = []
    with TRACE.open(encoding="utf-8") as stream:
      for index, line in enumerate(stream):
        if index >= 160:
            break
        row = json.loads(line)
        k = (2, 4, 8, 16, 35)[index % 5]
        vectors.append([
            (mode, round(cost * 256))
            for mode, cost in zip(row["ranked_modes"][:k], row["rd_cost_by_rank"][:k])
        ])
    randomizer = random.Random(0xC1A)
    for index in range(340):
        k = (2, 4, 8, 16, 35)[index % 5]
        ids = randomizer.sample(range(35), k)
        costs = [randomizer.randrange(1, 1 << 36) for _ in range(k)]
        if index % 17 == 0 and k > 1:
            costs[1] = costs[0]
        vectors.append(list(zip(ids, costs)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="ascii") as output:
        for candidates in vectors:
            best_index = min(range(len(candidates)), key=lambda item: candidates[item][1])
            best_id, best_cost = candidates[best_index]
            fields = [str(len(candidates)), str(best_id), str(best_cost)]
            for candidate_id, cost in candidates:
                fields.extend((str(candidate_id), str(cost)))
            output.write(" ".join(fields) + "\n")
    metadata = {
        "schema_version": "chia-rdo.rtl-vectors.v1", "vectors": len(vectors),
        "hm_trace_vectors": 160, "random_vectors": 340, "seed": "0xC1A",
        "cost_quantization": "round(HM double RD cost * 256)",
        "reference_operation": "stable minimum cost; first candidate wins ties",
    }
    (args.output.parent / "golden_vectors.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    print(args.output.relative_to(ROOT))


if __name__ == "__main__":
    main()
