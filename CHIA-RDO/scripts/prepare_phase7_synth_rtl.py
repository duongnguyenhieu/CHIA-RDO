#!/usr/bin/env python3
"""Create the bounded-loop synthesis form without modifying locked RTL."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "rtl/full_rdo_codec_4x4.sv"
SOURCE_SHA256 = "46002cdda965834e9e9b136e3c6a6d9a85a70278032b43195828bb38b7492b21"
OUTPUT = ROOT / "build/phase7/generated/full_rdo_codec_4x4.sv"
MANIFEST = ROOT / "results/phase7/synth_rtl_derivation.json"


def main() -> None:
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("locked full_rdo_codec_4x4.sv hash changed")
    source = SOURCE.read_text()
    old = """            for (angular_index = -1; angular_index > ((4*prediction_angle) >>> 5);
                 angular_index = angular_index - 1) begin
              inverse_angle_sum = inverse_angle_sum + INV_ANGLE[absolute_angle_mode];
              reference_main[8+angular_index] = reference_side[8+(inverse_angle_sum >>> 8)];
            end"""
    new = """            for (angular_index = -1; angular_index >= -4; angular_index = angular_index - 1) begin
              if (angular_index > ((4*prediction_angle) >>> 5)) begin
                inverse_angle_sum = inverse_angle_sum + INV_ANGLE[absolute_angle_mode];
                reference_main[8+angular_index] = reference_side[8+(inverse_angle_sum >>> 8)];
              end
            end"""
    if source.count(old) != 1:
        raise RuntimeError("synthesis-loop derivation marker not found exactly once")
    derived = source.replace(old, new)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(derived)
    manifest = {
        "schema_version": "chia-rdo.phase7-synth-rtl-derivation.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": str(SOURCE.relative_to(ROOT)), "source_sha256": SOURCE_SHA256,
        "derived": str(OUTPUT.relative_to(ROOT)),
        "derived_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "transformation": "Bound the negative-angle reference extension loop to -1..-4 and preserve the original runtime condition as a guard.",
        "locked_source_modified": False,
        "equivalence_status": "PENDING_RTL_REGRESSION",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
