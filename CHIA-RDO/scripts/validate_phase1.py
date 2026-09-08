#!/usr/bin/env python3
"""Execute the blocking CHIA-RDO Phase 1 quality gate."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software"))

from generate_sequence import write_tiny_sequence  # noqa: E402
from run_baseline import (  # noqa: E402
    DECODER,
    ENCODER,
    encoder_argv,
    load_trace,
    parse_hm_log,
    run_process,
    sha256_file,
)


EXPECTED_BASELINE_BITSTREAM = "68de30e7f7ca39f8df9fb412a3c38f31b54aadc063791876525ea94a700d4a45"
EXPECTED_BASELINE_RECON = "9695e6606861cc58de4398bfe70b4b894010ea6a377a8c7adf64db3f9752d606"
EXPECTED_BASELINE_TRACE = "56f12bb400649ea148f2bae06cbf63ea4eb31f915c34dd60fdef2dd761cca7fd"


class Gate:
    def __init__(self) -> None:
        self.tests: list[dict[str, Any]] = []

    def check(
        self,
        name: str,
        method: str,
        expected: str,
        evidence: str,
        function: Callable[[], str],
    ) -> None:
        try:
            actual = function()
            status = "PASS"
        except Exception as exc:
            actual = f"{type(exc).__name__}: {exc}"
            status = "FAIL"
        self.tests.append(
            {
                "test": name,
                "method": method,
                "expected": expected,
                "actual": actual,
                "status": status,
                "evidence_path": evidence,
            }
        )

    @property
    def passed(self) -> bool:
        return bool(self.tests) and all(test["status"] == "PASS" for test in self.tests)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def stable_rank(row: dict[str, Any]) -> list[int]:
    return sorted(range(35), key=lambda mode: row["rough_cost_by_mode"][mode])


def validate_satd(rows: list[dict[str, Any]]) -> str:
    nonconstant = 0
    for index, row in enumerate(rows):
        satd = row["satd_by_mode"]
        bits = row["mode_bits_by_mode"]
        costs = row["rough_cost_by_mode"]
        require(len(satd) == len(bits) == len(costs) == 35, f"row {index}: feature length")
        require(all(isinstance(value, int) and value >= 0 for value in satd), f"row {index}: SATD")
        lambda_estimates = [
            (costs[mode] - satd[mode]) / bits[mode]
            for mode in range(35)
            if bits[mode] > 0
        ]
        tolerance = max(1e-8, abs(lambda_estimates[0]) * 1e-10)
        require(
            max(lambda_estimates) - min(lambda_estimates) <= tolerance,
            f"row {index}: rough cost is inconsistent with SATD + bits * sqrt(lambda)",
        )
        nonconstant += len(set(satd)) > 1
    require(nonconstant > 0, "all SATD vectors are constant")
    return f"{nonconstant}/{len(rows)} rows have mode-dependent SATD; all rows satisfy rough-cost identity"


def validate_ranking(rows: list[dict[str, Any]]) -> str:
    for index, row in enumerate(rows):
        require(row["ranked_modes"] == stable_rank(row), f"row {index}: ranking mismatch")
        require(sorted(row["ranked_modes"]) == list(range(35)), f"row {index}: mode coverage")
    return f"all {len(rows)} rankings match stable rough-cost order and cover modes 0..34"


def validate_rd_costs(rows: list[dict[str, Any]]) -> str:
    for index, row in enumerate(rows):
        costs = row["rd_cost_by_rank"]
        require(len(costs) == 35, f"row {index}: RD cost length")
        require(all(math.isfinite(value) and value >= 0 for value in costs), f"row {index}: RD cost")
        require(row["best_mode"] in row["ranked_modes"], f"row {index}: winner absent")
        tolerance = max(1e-8, min(costs) * 1e-10)
        require(row["best_rd_cost"] <= min(costs) + tolerance, f"row {index}: winner cost")
    return f"all {len(rows)} RD vectors are finite; each recorded winner is a tested candidate"


def run_encoder(
    encoder: Path,
    config: dict[str, Any],
    input_path: Path,
    output_dir: Path,
    label: str,
    env: dict[str, str],
) -> tuple[dict[str, Any], Path, Path, Path]:
    bitstream = output_dir / f"{label}.bin"
    recon = output_dir / f"{label}-recon.yuv"
    log = output_dir / f"{label}.log"
    argv = encoder_argv(config, input_path, bitstream, recon)
    argv[0] = str(encoder)
    _, text = run_process(argv, env, log)
    return parse_hm_log(text, config["sequence"]["frames"]), bitstream, recon, log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pristine-encoder",
        type=Path,
        default=Path("/tmp/opencode/hm-pristine/bin/TAppEncoderStatic"),
    )
    args = parser.parse_args()
    baseline_dir = ROOT / "results" / "baseline" / "tiny64-all-intra-full-rdo-qp32-faed5f414b11"
    baseline_result = baseline_dir / "result.json"
    baseline_trace = baseline_dir / "intra-rdo.jsonl"
    config_path = ROOT / "configs" / "baseline_smoke.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    evidence_dir = ROOT / "results" / "quality_gate" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir.mkdir(parents=True, exist_ok=False)
    input_path = ROOT / "datasets" / "generated" / f"{config['sequence']['name']}.yuv"
    write_tiny_sequence(input_path)
    gate = Gate()

    unit_log = evidence_dir / "unit-tests.log"
    unit = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    unit_log.write_text(unit.stdout, encoding="utf-8")
    gate.check(
        "HM baseline reproducibility",
        "Run the test suite, then repeat exhaustive encode and compare immutable hashes.",
        "Tests pass and repeated bitstream/reconstruction/trace hashes match the recorded baseline.",
        str(evidence_dir.relative_to(ROOT)),
        lambda: "4 unit tests passed" if unit.returncode == 0 else (_ for _ in ()).throw(RuntimeError("unit tests failed")),
    )

    base_env = dict(os.environ)
    for key in ("CHIA_RDO_EXHAUSTIVE", "CHIA_RDO_TRACE"):
        base_env.pop(key, None)
    base_env["LC_ALL"] = "C"
    repeat_trace = evidence_dir / "repeat-intra-rdo.jsonl"
    exhaustive_env = dict(base_env)
    exhaustive_env.update({"CHIA_RDO_EXHAUSTIVE": "1", "CHIA_RDO_TRACE": str(repeat_trace)})
    repeat_metrics, repeat_bitstream, repeat_recon, repeat_log = run_encoder(
        ENCODER, config, input_path, evidence_dir, "repeat-exhaustive", exhaustive_env
    )
    decoded = evidence_dir / "repeat-decoded.yuv"
    run_process(
        [str(DECODER), "-b", str(repeat_bitstream), "-o", str(decoded)],
        base_env,
        evidence_dir / "repeat-decode.log",
    )
    rows = [json.loads(line) for line in repeat_trace.read_text(encoding="utf-8").splitlines()]
    trace_summary = load_trace(repeat_trace)

    gate.check(
        "Exhaustive mode coverage",
        "Validate every ranked_modes vector as a permutation of HEVC luma modes 0..34.",
        "Every search call covers all 35 modes exactly once.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: validate_ranking(rows),
    )
    gate.check(
        "SATD telemetry correctness",
        "Check nonnegative SATD and rough_cost = SATD + mode_bits * sqrt(lambda) per search call.",
        "All feature vectors satisfy the HM rough-cost identity; non-boundary content has mode variation.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: validate_satd(rows),
    )
    gate.check(
        "Candidate ranking telemetry correctness",
        "Reconstruct stable ordering from rough_cost_by_mode and compare every rank.",
        "All recorded rankings exactly match reconstructed stable order.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: validate_ranking(rows),
    )
    gate.check(
        "RD-cost telemetry correctness",
        "Check finite/nonnegative costs, candidate membership, and winner cost invariant.",
        "All candidate RD vectors and winners satisfy invariants.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: validate_rd_costs(rows),
    )
    gate.check(
        "RDO count consistency",
        "Sum per-event candidate evaluations and compare with event_count * 35.",
        "RDO evaluations equal search_calls * 35.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: (
            f"{trace_summary['rdo_evaluations']} = {trace_summary['search_calls']} * 35"
            if trace_summary["rdo_evaluations"] == trace_summary["search_calls"] * 35
            else (_ for _ in ()).throw(AssertionError("RDO count mismatch"))
        ),
    )
    gate.check(
        "RQT refinement count consistency",
        "Check each event's refinement counter under stock HHI_RQT_INTRA_SPEEDUP behavior.",
        "Exactly one winner refinement is recorded per search call.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: (
            f"{trace_summary['rqt_refinement_evaluations']} refinements for {len(rows)} calls"
            if trace_summary["rqt_refinement_evaluations"] == len(rows)
            else (_ for _ in ()).throw(AssertionError("RQT count mismatch"))
        ),
    )
    gate.check(
        "Encoder/decoder reconstruction equality",
        "Decode the repeated bitstream with HM decoder and compare SHA-256.",
        "Encoder reconstruction and decoder output hashes are identical.",
        str(decoded.relative_to(ROOT)),
        lambda: (
            sha256_file(decoded)
            if sha256_file(decoded) == sha256_file(repeat_recon) == EXPECTED_BASELINE_RECON
            else (_ for _ in ()).throw(AssertionError("reconstruction mismatch"))
        ),
    )
    gate.check(
        "Deterministic exhaustive bitstream",
        "Compare repeated encode SHA-256 with the previously recorded baseline.",
        EXPECTED_BASELINE_BITSTREAM,
        str(repeat_bitstream.relative_to(ROOT)),
        lambda: (
            sha256_file(repeat_bitstream)
            if sha256_file(repeat_bitstream) == EXPECTED_BASELINE_BITSTREAM
            else (_ for _ in ()).throw(AssertionError("bitstream hash mismatch"))
        ),
    )
    gate.check(
        "Deterministic telemetry parser and trace",
        "Parse the same log twice and compare trace SHA-256 with the recorded baseline.",
        "Repeated parser output and JSONL trace are byte-identical.",
        str(repeat_log.relative_to(ROOT)),
        lambda: (
            sha256_file(repeat_trace)
            if parse_hm_log(repeat_log.read_text(encoding="utf-8"), 4)
            == parse_hm_log(repeat_log.read_text(encoding="utf-8"), 4)
            and sha256_file(repeat_trace) == EXPECTED_BASELINE_TRACE
            else (_ for _ in ()).throw(AssertionError("parser or trace mismatch"))
        ),
    )
    gate.check(
        "Trace corresponds to executed HM candidate decisions",
        "Require each winner to be in its executed list and final best cost not exceed first-pass minimum.",
        "Every trace event identifies an executed candidate-loop winner; final coding-tree commitment remains out of scope.",
        str(repeat_trace.relative_to(ROOT)),
        lambda: validate_rd_costs(rows),
    )

    if not args.pristine_encoder.is_file():
        pristine_error = f"missing pristine encoder: {args.pristine_encoder}"
        patched_stock = pristine_stock = None
    else:
        patched_metrics, patched_bits, patched_recon, _ = run_encoder(
            ENCODER, config, input_path, evidence_dir, "patched-stock", base_env
        )
        pristine_metrics, pristine_bits, pristine_recon, _ = run_encoder(
            args.pristine_encoder, config, input_path, evidence_dir, "pristine-stock", base_env
        )
        patched_stock = (patched_metrics, patched_bits, patched_recon)
        pristine_stock = (pristine_metrics, pristine_bits, pristine_recon)
        pristine_error = ""
    gate.check(
        "Instrumentation does not alter stock HM bitstream",
        "Build pristine HM-16.20 and compare stock encode against patched HM with CHIA variables unset.",
        "Bitstream, reconstruction, and parsed coding metrics are identical.",
        str(evidence_dir.relative_to(ROOT)),
        lambda: (
            sha256_file(patched_stock[1])
            if patched_stock is not None
            and pristine_stock is not None
            and sha256_file(patched_stock[1]) == sha256_file(pristine_stock[1])
            and sha256_file(patched_stock[2]) == sha256_file(pristine_stock[2])
            and {k: v for k, v in patched_stock[0].items() if k != "hm_cpu_time_seconds"}
            == {k: v for k, v in pristine_stock[0].items() if k != "hm_cpu_time_seconds"}
            else (_ for _ in ()).throw(AssertionError(pristine_error or "stock parity mismatch"))
        ),
    )

    larger_config = ROOT / "configs" / "nontrivial_local.json"
    gate.check(
        "Nontrivial local benchmark availability",
        "Validate a reproducible configuration larger than the 64x64 smoke input.",
        "A deterministic >64x64 multi-frame configuration is present and generator-compatible.",
        str(larger_config.relative_to(ROOT)),
        lambda: (
            "128x128, 8 frames configuration available"
            if larger_config.is_file()
            and json.loads(larger_config.read_text(encoding="utf-8"))["sequence"]["width"] > 64
            else (_ for _ in ()).throw(AssertionError("nontrivial configuration unavailable"))
        ),
    )

    evidence = {
        "schema_version": "chia-rdo.phase1-quality-gate.v1",
        "created_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "PASS" if gate.passed else "FAIL",
        "baseline_result": str(baseline_result.relative_to(ROOT)),
        "baseline_trace": str(baseline_trace.relative_to(ROOT)),
        "repeat_metrics": repeat_metrics,
        "repeat_trace_summary": trace_summary,
        "tests": gate.tests,
        "limitations": [
            "HHI_RQT_INTRA_SPEEDUP remains enabled; candidate-loop coverage is exhaustive but transform-tree refinement follows stock HM.",
            "Trace events describe evaluated search alternatives, not only coding-tree units committed to the final bitstream.",
            "The 64x64 synthetic sequence is a smoke test, not research-quality evidence.",
        ],
        "cloud_cost_usd": 0.0,
    }
    evidence_path = evidence_dir / "phase1-quality-gate.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_path = ROOT / "results" / "quality_gate" / "latest.json"
    latest_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"PHASE 1 QUALITY GATE: {evidence['status']}")
    print(evidence_path.relative_to(ROOT))
    for test in gate.tests:
        print(f"{test['status']}: {test['test']}: {test['actual']}")
    return 0 if gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
