import json
import unittest
from collections import Counter
from pathlib import Path

from tests.full_rdo.model import SUPPORTED_MODES, evaluate, evaluate_candidate


VECTOR_DIR = Path(__file__).with_name("vectors")
PHASE52_MODES = (0, 1, 10, 26)


def load_vectors() -> list[dict]:
    return [json.loads(line) for line in (VECTOR_DIR / "full_rdo_4x4_dc.jsonl").read_text().splitlines()]


class FullRdoModelTest(unittest.TestCase):
    def test_hm_vectors_match_integer_model_at_every_stage(self):
        stage_names = (
            "prediction",
            "residual",
            "transform",
            "quantized",
            "dequantized",
            "inverse_residual",
            "reconstruction",
            "distortion",
        )
        vectors = load_vectors()
        self.assertEqual(len(vectors), 256)
        for vector in vectors:
            modeled = evaluate(vector["references"], vector["original"], vector["qp"])
            self.assertEqual(
                {name: modeled[name] for name in stage_names},
                {name: vector[name] for name in stage_names},
            )
            self.assertEqual(
                vector["rd_cost_q16"],
                (vector["distortion"] << 16) + vector["lambda_q16"] * vector["rate_bits"],
            )

    def test_vector_corpus_covers_supported_profile_and_edges(self):
        vectors = load_vectors()
        self.assertEqual(Counter(vector["qp"] for vector in vectors), {22: 64, 27: 64, 32: 64, 37: 64})
        self.assertEqual(
            Counter(vector["source_class"] for vector in vectors),
            {"tiny": 128, "flat": 64, "high-contrast": 64},
        )
        transformed = [coefficient for vector in vectors for coefficient in vector["transform"]]
        quantized = [coefficient for vector in vectors for coefficient in vector["quantized"]]
        self.assertLessEqual(min(transformed), -16000)
        self.assertGreaterEqual(max(transformed), 16000)
        self.assertLess(min(quantized), 0)
        self.assertGreater(max(quantized), 0)

    def test_phase52_hm_candidates_and_winners_match_reference(self):
        candidates = [json.loads(line) for line in (VECTOR_DIR / "full_rdo_pe_candidates.jsonl").read_text().splitlines()]
        groups = [json.loads(line) for line in (VECTOR_DIR / "full_rdo_pe_groups.jsonl").read_text().splitlines()]
        self.assertEqual(len(candidates), 10000)
        self.assertEqual(len(groups), 2500)
        for candidate in candidates:
            modeled = evaluate_candidate(candidate["references"], candidate["original"],
                                         candidate["mode"], candidate["qp"])
            for stage, expected in modeled.items():
                self.assertEqual(candidate[stage], expected)
            self.assertEqual(candidate["rd_cost_q16"],
                             (candidate["distortion"] << 16)
                             + candidate["rate_bits"] * candidate["lambda_q16"])
        for group in groups:
            winner_rank = min(range(4), key=lambda rank: group["rd_cost_q16"][rank])
            self.assertEqual(group["winner_rank"], winner_rank)
            self.assertEqual(group["winner_mode"], group["modes"][winner_rank])
            self.assertEqual(group["winner_cost_q16"], group["rd_cost_q16"][winner_rank])
            self.assertEqual(group["winner_mode"], group["hm_double_winner_mode"])

    def test_phase52_corpus_coverage(self):
        manifest = json.loads((VECTOR_DIR / "full_rdo_pe_manifest.json").read_text())
        self.assertEqual(manifest["candidate_count"], 10000)
        self.assertEqual(manifest["group_count"], 2500)
        self.assertEqual(manifest["candidate_set"], list(PHASE52_MODES))
        self.assertEqual(manifest["supported_block_sizes"], [4])
        self.assertEqual(manifest["mode_counts"], {str(mode): 2500 for mode in PHASE52_MODES})
        self.assertEqual(manifest["qp_counts"], {str(qp): 2500 for qp in (22, 27, 32, 37)})
        self.assertEqual(set(manifest["source_class_counts"]),
                         {"smooth", "edge-heavy", "texture-heavy", "random", "worst-case-signed"})
        self.assertEqual(manifest["hm_double_vs_q16_winner_disagreements"], 0)
        self.assertLessEqual(manifest["transform_range"][0], -18000)
        self.assertGreaterEqual(manifest["transform_range"][1], 21000)

    def test_phase53_all_mode_candidates_and_winners_match_reference(self):
        candidates = [json.loads(line) for line in (VECTOR_DIR / "pway_candidates.jsonl").read_text().splitlines()]
        groups = [json.loads(line) for line in (VECTOR_DIR / "pway_groups.jsonl").read_text().splitlines()]
        self.assertEqual(len(candidates), 8960)
        self.assertEqual(len(groups), 256)
        for candidate in candidates:
            modeled = evaluate_candidate(candidate["references"], candidate["original"],
                                         candidate["mode"], candidate["qp"])
            for stage, expected in modeled.items():
                self.assertEqual(candidate[stage], expected)
            self.assertEqual(candidate["rd_cost_q16"],
                             (candidate["distortion"] << 16)
                             + candidate["rate_bits"] * candidate["lambda_q16"])
        for group in groups:
            for k in (4, 16, 35):
                winner_rank = min(range(k), key=lambda rank: group["rd_cost_q16"][rank])
                winner = group["winners"][str(k)]
                self.assertEqual(winner["rank"], winner_rank)
                self.assertEqual(winner["mode"], group["modes"][winner_rank])
                self.assertEqual(winner["cost_q16"], group["rd_cost_q16"][winner_rank])

    def test_phase53_corpus_coverage(self):
        manifest = json.loads((VECTOR_DIR / "pway_manifest.json").read_text())
        self.assertEqual(manifest["candidates"], 8960)
        self.assertEqual(manifest["groups"], 256)
        self.assertEqual(manifest["k_values"], [4, 16, 35])
        self.assertEqual(manifest["p_values"], [1, 2, 4, 8])
        self.assertEqual(manifest["mode_counts"], {str(mode): 256 for mode in SUPPORTED_MODES})
        self.assertEqual(manifest["qp_counts"], {str(qp): 2240 for qp in (22, 27, 32, 37)})
