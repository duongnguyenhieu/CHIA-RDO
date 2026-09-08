#!/usr/bin/env python3
"""Generate deterministic, dependency-free YUV420 smoke sequences."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


TINY64_SHA256 = "1ba7c09220b0c0124db023bc5b1549fc8da68f70a8c7f4e51348f7d84a2b6a6a"


def tiny_yuv420(width: int = 64, height: int = 64, frames: int = 4) -> bytes:
    if width <= 0 or height <= 0 or frames <= 0 or width % 2 or height % 2:
        raise ValueError("YUV420 dimensions must be positive and even; frames must be positive")

    data = bytearray()
    for frame in range(frames):
        data.extend(
            (3 * x + 5 * y + 17 * frame + (x * y) % 29) & 0xFF
            for y in range(height)
            for x in range(width)
        )
        data.extend(
            (96 + 7 * x + 3 * y + 13 * frame) & 0xFF
            for y in range(height // 2)
            for x in range(width // 2)
        )
        data.extend(
            (160 + 5 * x - 9 * y + 19 * frame) & 0xFF
            for y in range(height // 2)
            for x in range(width // 2)
        )
    return bytes(data)


def write_tiny_sequence(path: Path, width: int = 64, height: int = 64, frames: int = 4) -> str:
    payload = tiny_yuv420(width, height, frames)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--width", type=int, default=64)
    parser.add_argument("--height", type=int, default=64)
    parser.add_argument("--frames", type=int, default=4)
    args = parser.parse_args()
    digest = write_tiny_sequence(args.output, args.width, args.height, args.frames)
    print(f"{args.output}: sha256={digest}")


if __name__ == "__main__":
    main()
