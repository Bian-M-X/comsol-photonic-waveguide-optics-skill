from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import OptimizationSpec, OptimizationTrial
from photonic_workflow.optimization import spec_fingerprint, suggest_candidate


def specification(**updates: object) -> OptimizationSpec:
    values = dict(stable_id="optimization:test", name="test", source="unit fixture",
                  created_at=datetime(2026, 1, 1, tzinfo=UTC),
                  variables=[{"name": "x", "lower": 0.0, "upper": 1.0, "unit": "1"}],
                  objectives=[{"name": "loss", "sense": "minimize"}],
                  random_seed=11, evaluation_budget=22, promotion_rule={"validation_reserve": 2})
    values.update(updates)
    return OptimizationSpec(**values)


def observation(spec: OptimizationSpec, index: int, x: float, **updates: object) -> OptimizationTrial:
    values = dict(stable_id=f"trial:t{index}", name=f"trial {index}", source="unit fixture",
                  created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index),
                  optimization_spec_id=spec.stable_id, run_id=f"run:t{index}", parameters={"x": x},
                  objectives={"loss": (x - 0.23)**2}, status="succeeded",
                  provenance=["optimization-spec-sha256:" + spec_fingerprint(spec)])
    values.update(updates)
    return OptimizationTrial(**values)


class OptimizationSearchTests(unittest.TestCase):
    def test_resume_is_deterministic_and_reserves_validation(self) -> None:
        spec, history = specification(), []
        points = []
        for index in range(20):
            a = suggest_candidate(spec, history, pool_size=128)
            self.assertEqual(a, suggest_candidate(spec, list(reversed(history)), pool_size=128))
            self.assertFalse(a["will_execute"])
            x = a["parameters"]["x"]
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x, 1)
            self.assertNotIn(x, points)
            points.append(x)
            history.append(observation(spec, index, x))
        self.assertLess(min(t.objectives["loss"] for t in history), 1e-4)
        self.assertEqual(suggest_candidate(spec, history)["action"], "stop_search_preserve_validation")

    def test_pending_blocks_parallel_suggestions(self) -> None:
        spec = specification()
        trial = observation(spec, 0, 0.5, status="running", objectives={})
        self.assertEqual(suggest_candidate(spec, [trial])["action"], "wait_for_pending")

    def test_failed_solve_counts_without_training(self) -> None:
        spec = specification()
        history = [observation(spec, i, 0.1 * i, status="failed", failure="mesh", objectives={}) for i in range(3)]
        response = suggest_candidate(spec, history[:2])
        self.assertEqual(response["successful_observations"], 0)
        self.assertEqual(response["search_slots_remaining"], 18)
        self.assertEqual(suggest_candidate(spec, history)["action"], "diagnose_repeated_failure")

    def test_changed_spec_and_duplicate_identity_rejected(self) -> None:
        spec = specification()
        t = observation(spec, 0, 0.2)
        spec.fidelity = "full-wave-3d"
        with self.assertRaises(InvalidInputError):
            suggest_candidate(spec, [t])
        fresh = specification()
        with self.assertRaises(InvalidInputError):
            suggest_candidate(fresh, [t, t])

    def test_constraints_need_observations_and_scale(self) -> None:
        spec = specification(constraints=[{"name": "g", "upper": 0, "scale": 0.1}])
        with self.assertRaises(InvalidInputError):
            suggest_candidate(spec, [observation(spec, 0, 0.5)])
        history = [observation(spec, i, x, constraint_results={"g": x - 0.6})
                   for i, x in enumerate([0.1, 0.3, 0.7, 0.9, 0.5])]
        response = suggest_candidate(spec, history, pool_size=128)
        self.assertEqual(response["action"], "evaluate_candidate")
        self.assertIsNotNone(response["prediction"])

    def test_no_feasible_sample_uses_feasibility_search(self) -> None:
        spec = specification(constraints=[{"name": "g", "upper": -0.1, "scale": 1}])
        history = [observation(spec, i, x, constraint_results={"g": x})
                   for i, x in enumerate([0.1, 0.3, 0.7, 0.9, 0.5])]
        self.assertEqual(suggest_candidate(spec, history, pool_size=128)["reason"], "seek_feasibility")

    def test_maximization_and_failed_boundary_inputs(self) -> None:
        spec = specification(objectives=[{"name": "loss", "sense": "maximize"}])
        history = [observation(spec, i, x) for i, x in enumerate([0.1, 0.3, 0.7, 0.9, 0.5])]
        self.assertEqual(suggest_candidate(spec, history, pool_size=128)["action"], "evaluate_candidate")
        for changes in ({"parameters": {"x": True}}, {"parameters": {"x": 1.1}},
                        {"objectives": {"loss": float("nan")}}, {"status": "draft"},
                        {"run_id": ""}, {"failure": "unexplained"}):
            with self.assertRaises(InvalidInputError):
                suggest_candidate(spec, [observation(spec, 0, 0.5, **changes)])

    def test_configuration_limits(self) -> None:
        for changes in ({"promotion_rule": {}}, {"random_seed": None}, {"failure_penalty": 0.0},
                        {"evaluation_budget": 513}, {"objectives": []}):
            with self.assertRaises(InvalidInputError):
                suggest_candidate(specification(**changes), [])

    def test_boolean_budget_and_seed_rejected_before_integer_coercion(self) -> None:
        for updates in ({"random_seed": True}, {"evaluation_budget": True}):
            with self.assertRaises(ValidationError):
                specification(**updates)

    def test_invalid_spec_does_not_propose(self) -> None:
        with self.assertRaises(InvalidInputError):
            suggest_candidate(specification(validity="invalid"), [])

    def test_initialization_cost_is_visible_before_spending(self) -> None:
        spec = specification(variables=[{"name": f"x{i}", "lower": 0, "upper": 1, "unit": "1"}
                                        for i in range(8)], evaluation_budget=30,
                             promotion_rule={"validation_reserve": 8})
        result = suggest_candidate(spec, [])
        self.assertEqual(result["initial_successes_required"], 17)
        self.assertEqual(result["remaining_initialization"], 17)
        self.assertEqual(result["possible_model_guided_slots"], 5)


if __name__ == "__main__":
    unittest.main()
