from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))

from generate_sequence import TINY64_SHA256, tiny_yuv420  # noqa: E402
from run_baseline import parse_hm_log  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
