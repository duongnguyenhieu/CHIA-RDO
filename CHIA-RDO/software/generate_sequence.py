#!/usr/bin/env python3
"""Generate deterministic, dependency-free YUV420 smoke sequences."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


TINY64_SHA256 = "1ba7c09220b0c0124db023bc5b1549fc8da68f70a8c7f4e51348f7d84a2b6a6a"
HELDOUT_GENERATORS = (
    "heldout-smooth-edges-v1",
    "heldout-repetitive-v1",
    "heldout-mixed-texture-v1",
)


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


def heldout_yuv420(width: int, height: int, frames: int, generator: str) -> bytes:
    if width <= 0 or height <= 0 or frames <= 0 or width % 2 or height % 2:
        raise ValueError("YUV420 dimensions must be positive and even; frames must be positive")
    if generator not in HELDOUT_GENERATORS:
        raise ValueError(f"unsupported held-out generator: {generator}")

    data = bytearray()
    for frame in range(frames):
        for y in range(height):
            for x in range(width):
                if generator == "heldout-smooth-edges-v1":
                    edge_x = width // 3 + frame * max(width // 24, 1)
                    edge_y = height * 2 // 3 - frame * max(height // 32, 1)
                    value = 40 + (x // 12) + (y // 16)
                    if x >= edge_x:
                        value += 112
                    if y >= edge_y:
                        value += 48
                elif generator == "heldout-repetitive-v1":
                    checker = ((x // 4) + (y // 4) + frame) & 1
                    stripes = 35 if ((x + 3 * frame) // 12) & 1 else 0
                    value = 36 + checker * 164 + stripes
                else:
                    noise = ((x * 73) ^ (y * 151) ^ (frame * 199) ^ (x * y * 3)) & 0x7F
                    radial = (abs(2 * x - width) + abs(2 * y - height)) // 5
                    shape = 60 if (x - width // 2) ** 2 + (y - height // 2) ** 2 < (min(width, height) // 4) ** 2 else 0
                    value = 24 + noise + radial + shape
                data.append(max(0, min(value, 255)))
        for plane in (0, 1):
            for y in range(height // 2):
                for x in range(width // 2):
                    if generator == "heldout-smooth-edges-v1":
                        value = (92 if plane == 0 else 164) + (x // 8) - (y // 12) + frame * (3 if plane == 0 else -2)
                    elif generator == "heldout-repetitive-v1":
                        value = (80 if plane == 0 else 176) + (36 if ((x // 3 + y // 3 + frame) & 1) else -36)
                    else:
                        value = 128 + ((((x * 29) ^ (y * 47) ^ (frame * 31) ^ (plane * 53)) & 0x3F) - 32)
                    data.append(max(0, min(value, 255)))
    return bytes(data)


def sequence_yuv420(width: int, height: int, frames: int, generator: str) -> bytes:
    if generator == "tiny-yuv-v1":
        return tiny_yuv420(width, height, frames)
    return heldout_yuv420(width, height, frames, generator)


def write_tiny_sequence(path: Path, width: int = 64, height: int = 64, frames: int = 4) -> str:
    payload = tiny_yuv420(width, height, frames)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def write_sequence(path: Path, width: int, height: int, frames: int, generator: str) -> str:
    payload = sequence_yuv420(width, height, frames, generator)
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
