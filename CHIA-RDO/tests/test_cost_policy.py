from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def estimate(remaining: float | None, workers: int, campaign_class: str = "high-information") -> tuple[int, dict]:
    environment = os.environ.copy()
    environment.update({
        "CURRENT_VERIFIED_SPEND": "10" if remaining is not None else "",
        "CURRENT_VERIFIED_REMAINING_CREDIT": str(remaining) if remaining is not None else "",
        "BILLING_DATA_STATUS": "verified" if remaining is not None else "unverified",
        "VERIFICATION_SOURCE": "unit-test",
        "WORKER_COUNT": str(workers),
        "CAMPAIGN_CLASS": campaign_class,
        "MAX_LIFETIME_MINUTES": "10",
    })
    process = subprocess.run(["cloud/estimate_cost.sh"], cwd=ROOT, env=environment,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return process.returncode, json.loads(process.stdout)


class CostPolicyTests(unittest.TestCase):
    def test_unverified_billing_fails_closed(self) -> None:
        status, record = estimate(None, 1)
        self.assertEqual(status, 3)
        self.assertFalse(record["launch_allowed"])
        self.assertIsNone(record["current_verified_spend"])
        self.assertIsNone(record["current_verified_remaining_credit"])
        self.assertEqual(record["authorized_campaign_limit"], 280)
        self.assertEqual(record["safety_reserve"], 20)

    def test_budget_mode_worker_limits(self) -> None:
        cases = ((100, 8, "standard"), (99, 4, "reduced"), (59, 2, "cautious"), (29, 1, "strict"))
        for remaining, workers, mode in cases:
            with self.subTest(remaining=remaining):
                status, record = estimate(remaining, workers)
                self.assertEqual(status, 0)
                self.assertTrue(record["launch_allowed"])
                self.assertEqual(record["budget_mode"], mode)

    def test_below_reserve_stops_and_cautious_rejects_sweeps(self) -> None:
        status, record = estimate(19, 1)
        self.assertEqual(status, 3)
        self.assertEqual(record["budget_mode"], "stop")
        status, record = estimate(59, 1, "broad-sweep")
        self.assertEqual(status, 3)
        self.assertIn("campaign class is forbidden by the active budget mode", record["gate_reasons"])


if __name__ == "__main__":
    unittest.main()
