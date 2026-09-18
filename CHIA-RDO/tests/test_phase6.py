from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chia"))

from phase6_agent import FROZEN_POLICY, candidate_pool, canonical_id, propose, validate_proposal  # noqa: E402
from phase6_objectives import dominates, model_rtl_error, pareto_frontier  # noqa: E402


class Phase6AgentTests(unittest.TestCase):
    def test_frozen_policy_cannot_be_redefined(self) -> None:
        proposal = copy.deepcopy(candidate_pool()[0])
        proposal["policy"]["parameters"]["easy_threshold"] = 0.05
        with self.assertRaises(ValueError):
            validate_proposal(proposal)

    def test_identity_is_canonical_and_stable(self) -> None:
        proposal = candidate_pool()[0]
        self.assertEqual(canonical_id(proposal), canonical_id(copy.deepcopy(proposal)))

    def test_agent_consumes_history_and_avoids_completed_ids(self) -> None:
        first = propose([], 4)
        history = [{"experiment_id": row["experiment_id"], "result_status": "PASS",
                    "feasible": True, "hardware_configuration": row["hardware_configuration"],
                    "proposal": row, "bd_rate_percent": 0.0, "average_rdo_evaluations": 20,
                    "rtl_cycles_per_event": 20, "resource_proxy": 1000} for row in first]
        second = propose(history, 4)
        self.assertTrue({row["experiment_id"] for row in first}.isdisjoint(
            row["experiment_id"] for row in second))
        self.assertTrue(all(row["parent_experiment_id"] for row in second))

    def test_pareto_marks_dominated_history_without_deleting_it(self) -> None:
        better = {"experiment_id": "better", "result_status": "PASS", "feasible": True,
                  "bd_rate_percent": 0.0, "average_rdo_evaluations": 10,
                  "rtl_cycles_per_event": 10, "resource_proxy": 100}
        worse = {"experiment_id": "worse", "result_status": "PASS", "feasible": True,
                 "bd_rate_percent": 0.0, "average_rdo_evaluations": 11,
                 "rtl_cycles_per_event": 12, "resource_proxy": 110}
        self.assertTrue(dominates(better, worse))
        self.assertEqual(pareto_frontier([better, worse]), [better])
        self.assertTrue(worse["dominated"])

    def test_model_error_requires_measured_pairs(self) -> None:
        self.assertEqual(model_rtl_error([])["status"], "UNAVAILABLE")
        result = model_rtl_error([{"estimated_cycles": 10, "rtl_cycles_per_event": 8}])
        self.assertEqual(result["status"], "CALIBRATED_RTL_REPLAY")
        self.assertEqual(result["mae_cycles"], 2)


if __name__ == "__main__":
    unittest.main()
