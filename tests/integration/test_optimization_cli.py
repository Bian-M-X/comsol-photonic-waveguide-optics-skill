from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from photonic_workflow.models.io import write_contract
from tests.integration.test_cli import invoke
from tests.unit.test_optimization_search import observation, specification


class OptimizationCliTests(unittest.TestCase):
    def test_ask_is_read_only_and_pending_blocks_new_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trials = root / "trials"
            trials.mkdir()
            spec = specification()
            spec_path = root / "spec.json"
            write_contract(spec_path, spec)
            before = spec_path.read_bytes()
            command = ["optimize", "suggest", str(spec_path), "--trials", str(trials), "--json"]
            with patch("subprocess.Popen", side_effect=AssertionError("suggest must not launch a solver")):
                code, output, error = invoke(command)
            self.assertEqual((code, error), (0, ""))
            proposal = json.loads(output)["data"]
            self.assertEqual(proposal["action"], "evaluate_candidate")
            self.assertEqual(list(trials.iterdir()), [])
            self.assertEqual(spec_path.read_bytes(), before)
            trial = observation(spec, 0, proposal["parameters"]["x"], status="planned", objectives={})
            write_contract(trials / "trial.json", trial)
            trial_bytes = (trials / "trial.json").read_bytes()
            code, output, error = invoke(command)
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["data"]["action"], "wait_for_pending")
            self.assertEqual((trials / "trial.json").read_bytes(), trial_bytes)

    def test_changed_spec_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trials = root / "trials"
            trials.mkdir()
            spec = specification()
            write_contract(trials / "trial.json", observation(spec, 0, 0.5))
            spec.fidelity = "full-wave-3d"
            write_contract(root / "spec.json", spec)
            code, output, _ = invoke(["optimize", "suggest", str(root / "spec.json"),
                                      "--trials", str(trials), "--json"])
            self.assertNotEqual(code, 0)
            self.assertFalse(json.loads(output)["ok"])

    def test_raw_boolean_objective_is_rejected_before_float_coercion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            trials = root / "trials"
            trials.mkdir()
            spec = specification()
            write_contract(root / "spec.json", spec)
            trial_path = trials / "trial.json"
            write_contract(trial_path, observation(spec, 0, 0.5))
            payload = json.loads(trial_path.read_text(encoding="utf-8"))
            payload["objectives"]["loss"] = True
            trial_path.write_text(json.dumps(payload), encoding="utf-8")
            code, output, _ = invoke(["optimize", "suggest", str(root / "spec.json"),
                                      "--trials", str(trials), "--json"])
            self.assertNotEqual(code, 0)
            self.assertFalse(json.loads(output)["ok"])
            self.assertIn("not boolean", output)


if __name__ == "__main__":
    unittest.main()
