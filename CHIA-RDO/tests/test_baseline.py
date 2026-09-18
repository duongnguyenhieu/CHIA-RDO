from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))

from generate_sequence import HELDOUT_GENERATORS, TINY64_SHA256, sequence_yuv420, tiny_yuv420  # noqa: E402
from run_baseline import parse_hm_log  # noqa: E402
from run_policy import hardware_fill_k, policy_environment, select_adaptive_k  # noqa: E402
from policy_algorithms import (  # noqa: E402
    HardwareState,
    estimate_cycles,
    normalized_best_rough_cost,
    relative_satd_values,
    select_adaptive_hw_v1_k,
    select_adaptive_threshold_k,
    select_relative_satd_k,
)
from analysis import bd_rate, nondominated  # noqa: E402


class SequenceTests(unittest.TestCase):
    def test_tiny_sequence_is_stable(self) -> None:
        payload = tiny_yuv420()
        self.assertEqual(len(payload), 24576)
        self.assertEqual(hashlib.sha256(payload).hexdigest(), TINY64_SHA256)

    def test_invalid_yuv420_dimensions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            tiny_yuv420(width=63)

    def test_larger_sequence_is_deterministic(self) -> None:
        first = tiny_yuv420(128, 128, 8)
        second = tiny_yuv420(128, 128, 8)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 196608)

    def test_heldout_generators_are_deterministic_and_distinct(self) -> None:
        payloads = [sequence_yuv420(32, 24, 2, generator) for generator in HELDOUT_GENERATORS]
        self.assertTrue(all(len(payload) == 2304 for payload in payloads))
        self.assertEqual(len(set(payloads)), len(HELDOUT_GENERATORS))
        for generator, payload in zip(HELDOUT_GENERATORS, payloads):
            self.assertEqual(payload, sequence_yuv420(32, 24, 2, generator))


class LogParserTests(unittest.TestCase):
    def test_parses_required_metrics(self) -> None:
        pictures = "\n".join(
            f"POC {poc:4d} TId: 0 ( I-SLICE, QP 32 )       100 bits [Y 40.0000 dB    U 41.0000 dB    V 42.0000 dB]"
            for poc in range(4)
        )
        log = f"""
{pictures}
SUMMARY --------------------------------------------------------
 Total Frames |   Bitrate     Y-PSNR    U-PSNR    V-PSNR    YUV-PSNR
             4 a      24.0000    40.0000    41.0000    42.0000    40.5000
Bytes written to file: 400 (24.000 kbps)
 Total Time:        1.234 sec.
"""
        metrics = parse_hm_log(log, 4)
        self.assertEqual(metrics["encoded_frames"], 4)
        self.assertEqual(metrics["bitstream_bytes"], 400)
        self.assertEqual(metrics["psnr_yuv_db"], 40.5)
        self.assertEqual(len(metrics["pictures"]), 4)

    def test_rejects_non_intra_picture(self) -> None:
        log = """
POC 0 TId: 0 ( P-SLICE, QP 32 ) 100 bits [Y 40.0 dB U 40.0 dB V 40.0 dB]
1 a 1 1 1 1 1
Bytes written to file: 1 (1 kbps)
Total Time: 1 sec.
"""
        with self.assertRaises(RuntimeError):
            parse_hm_log(log, 1)


class PolicyTests(unittest.TestCase):
    def test_adaptive_boundaries(self) -> None:
        self.assertEqual(select_adaptive_k(0.0449), 16)
        self.assertEqual(select_adaptive_k(0.045), 8)
        self.assertEqual(select_adaptive_k(0.0879), 8)
        self.assertEqual(select_adaptive_k(0.088), 4)

    def test_invalid_thresholds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_adaptive_k(0.1, medium_threshold=0.2, high_threshold=0.1)

    def test_fixed_k_bounds_are_rejected(self) -> None:
        for value in (0, 1, 3, 36):
            with self.subTest(value=value), self.assertRaises(ValueError):
                policy_environment({"name": "fixed", "k": value})

    def test_fixed_supported_levels(self) -> None:
        for value in (2, 4, 8, 16, 35):
            with self.subTest(value=value):
                self.assertEqual(policy_environment({"name": "fixed", "k": value})["CHIA_RDO_FIXED_K"], str(value))

    def test_full_policy_selects_exhaustive_path(self) -> None:
        self.assertEqual(policy_environment({"name": "full"})["CHIA_RDO_POLICY"], "exhaustive")

    def test_hardware_fill_respects_batch_boundaries(self) -> None:
        self.assertEqual(hardware_fill_k(2, 4), 4)
        self.assertEqual(hardware_fill_k(4, 4), 4)
        self.assertEqual(hardware_fill_k(4, 8), 8)
        self.assertEqual(hardware_fill_k(8, 8), 8)
        self.assertEqual(hardware_fill_k(16, 8), 16)

    def test_adaptive_threshold_is_independent_of_gap_policy(self) -> None:
        self.assertEqual(select_adaptive_threshold_k(0.08), 4)
        self.assertEqual(select_adaptive_threshold_k(0.081), 8)
        self.assertEqual(select_adaptive_threshold_k(0.20), 8)
        self.assertEqual(select_adaptive_threshold_k(0.201), 16)
        self.assertAlmostEqual(normalized_best_rough_cost(8160, 16), 2.0)

    def test_relative_satd_definition_and_quantization(self) -> None:
        satd = [100, 110, 120, 200] + [300] * 31
        relative = relative_satd_values(satd)
        self.assertEqual(relative[:4], [0.0, 0.1, 0.2, 1.0])
        self.assertEqual(select_relative_satd_k(satd, relative_threshold=0.1), 4)
        self.assertEqual(select_relative_satd_k([0] * 35, relative_threshold=0.0), 35)

    def test_cycle_model_batch_boundaries_and_partial_state(self) -> None:
        state = HardwareState(parallelism=4)
        self.assertEqual(estimate_cycles(3, state)["batches"], 1)
        self.assertEqual(estimate_cycles(4, state)["batches"], 1)
        self.assertEqual(estimate_cycles(5, state)["batches"], 2)
        partial = HardwareState(parallelism=4, current_batch_position=3)
        self.assertEqual(estimate_cycles(1, partial)["batches"], 1)
        self.assertEqual(estimate_cycles(2, partial)["batches"], 2)

    def test_hardware_v1_is_deterministic_and_p_sensitive(self) -> None:
        features = {"confidence": 0.10, "relative_satd_count": 2, "activity_norm": 0.1,
                    "normalized_rough_cost": 0.05, "qp": 37, "block_area": 16}
        p1 = select_adaptive_hw_v1_k(**features, state=HardwareState(parallelism=1))[0]
        p8 = select_adaptive_hw_v1_k(**features, state=HardwareState(parallelism=8))[0]
        self.assertIn(p1, (2, 4, 8, 16, 35))
        self.assertIn(p8, (2, 4, 8, 16, 35))
        self.assertNotEqual(p1, p8)

    def test_bd_rate_identity_and_pareto_dominance(self) -> None:
        curve = [(100.0, 30.0), (150.0, 32.0), (220.0, 34.0), (330.0, 36.0)]
        self.assertAlmostEqual(bd_rate(curve, curve), 0.0, places=9)
        rows = [{"name": "a", "cost": 1, "quality": 1}, {"name": "b", "cost": 2, "quality": 1},
                {"name": "c", "cost": 2, "quality": 2}]
        self.assertEqual([row["name"] for row in nondominated(rows, ("cost", "quality"))], ["a"])


if __name__ == "__main__":
    unittest.main()
