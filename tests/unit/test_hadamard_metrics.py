import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from photonic_workflow.optimization.hadamard import decode_pairs, evaluate


def ideal():
    b = np.array([[1, 1j], [1j, 1]]) / np.sqrt(2)
    s = np.zeros((4, 4), complex)
    s[2:, :2] = b
    s[:2, 2:] = b.T
    return s


class MetricsTests(unittest.TestCase):
    def test_ideal(self):
        r = evaluate(ideal())
        self.assertTrue(r["acceptance_pass"])
        self.assertEqual(r["observed_matrix_scope"], "fundamental-selected S")
        self.assertAlmostEqual(r["conditional_choi_overlap"], 1)
        self.assertAlmostEqual(r["minimum_target_throughput_all_inputs"], 1)
        self.assertAlmostEqual(r["mirror_matrix_max_absolute_residual"], 0)
        for v in r["six_states"].values():
            self.assertAlmostEqual(v["conditional_fidelity"], 1)
            self.assertAlmostEqual(v["target_throughput"], 1)
        json.dumps(r, allow_nan=False)

    def test_superposition_throughput_is_visible_when_basis_inputs_pass(self):
        # Positive transfer Gram matrix: basis throughput .92, plus/minus .95/.89.
        b = ideal()[2:, :2]
        mixing = (
            np.array(
                [
                    [np.sqrt(0.95) + np.sqrt(0.89), np.sqrt(0.95) - np.sqrt(0.89)],
                    [np.sqrt(0.95) - np.sqrt(0.89), np.sqrt(0.95) + np.sqrt(0.89)],
                ]
            )
            / 2
        )
        s = ideal()
        s[2:, :2] = b @ mixing
        s[:2, 2:] = s[2:, :2].T
        report = evaluate(s)
        self.assertTrue(min(report["target_throughput_per_input"]) > 0.9)
        self.assertAlmostEqual(report["min_six_state_target_throughput"], 0.89)
        self.assertFalse(report["checks"]["throughput_pass"])
        script = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse/plot_results.py"
        spec = importlib.util.spec_from_file_location("hadamard_preview_metrics", script)
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        rows = dict(preview.metric_rows(report))
        self.assertEqual(rows["Minimum six-state target throughput"], "0.89")

    def test_all_input_throughput_catches_failure_between_six_states(self):
        # The least-transmitted Bloch direction is diagonal between all three
        # Pauli axes, so every six-state probe misses the .89 eigenvalue.
        diagonal_pauli = np.array([[1, 1 - 1j], [1 + 1j, -1]]) / np.sqrt(3)
        gram = 0.94 * np.eye(2) - 0.05 * diagonal_pauli
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        mixing = (eigenvectors * np.sqrt(eigenvalues)) @ eigenvectors.conj().T
        s = ideal()
        s[2:, :2] = s[2:, :2] @ mixing
        s[:2, 2:] = s[2:, :2].T
        report = evaluate(s)
        self.assertGreater(report["min_six_state_target_throughput"], 0.9)
        self.assertAlmostEqual(report["minimum_target_throughput_all_inputs"], 0.89)
        least_input = eigenvectors[:, 0]
        self.assertAlmostEqual(np.linalg.norm(s[2:, :2] @ least_input) ** 2, 0.89)
        self.assertFalse(report["checks"]["throughput_pass"])
        self.assertFalse(report["acceptance_pass"])

    def test_pml_preview_checks_full_domain_but_normalizes_inside_ports(self):
        script = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse/plot_results.py"
        spec = importlib.util.spec_from_file_location("hadamard_preview_pml", script)
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        with tempfile.TemporaryDirectory() as temp:
            field = Path(temp) / "field.txt"
            field.write_text(
                "x_um,y_um,Hz_abs_squared_source1\n"
                "-4.2,-4.2,nan\n4.2,4.2,1000000\n"
                "-3.15,-3.15,1\n-3.15,3.15,2\n3.15,-3.15,3\n3.15,3.15,4\n",
                encoding="utf-8",
            )
            config = {"outer_half_um": 3.15, "boundary_model": "slit_pml", "pml_thickness_um": 0.8}
            points, normalized, _, display_half, solved_half = preview.display_field_samples(field, config)
            self.assertEqual(len(points), 4)
            np.testing.assert_allclose(normalized, [0.25, 0.5, 0.75, 1.0])
            self.assertAlmostEqual(display_half, 3.15)
            self.assertAlmostEqual(solved_half, 4.2)
            with self.assertRaises(ValueError):
                preview.display_field_samples(field, config | {"pml_thickness_um": 1.2})
            with self.assertRaises(ValueError):
                preview.display_field_samples(field, {"outer_half_um": 3.15})
            field.write_text(field.read_text().replace("3.15,3.15,4", "3.15,3.15,nan"))
            with self.assertRaises(ValueError):
                preview.display_field_samples(field, config)

    def test_mirror_residual_checks_both_matrix_relations(self):
        s = ideal()
        s[2, 0] += 0.03j
        s[2, 1] += 0.04
        s[:2, 2:] = s[2:, :2].T
        report = evaluate(s)
        self.assertAlmostEqual(report["mirror_matrix_max_absolute_residual"], 0.04)

    def test_global_phase(self):
        a = evaluate(ideal())
        b = evaluate(ideal() * np.exp(1.173j))
        self.assertEqual(a["acceptance_pass"], b["acceptance_pass"])
        self.assertAlmostEqual(a["conditional_choi_overlap"], b["conditional_choi_overlap"])
        for k in a["six_states"]:
            self.assertAlmostEqual(
                a["six_states"][k]["conditional_fidelity"], b["six_states"][k]["conditional_fidelity"]
            )

    def test_lossy(self):
        r = evaluate(ideal() * 0.1)
        self.assertTrue(r["checks"]["fidelity_pass"])
        self.assertFalse(r["checks"]["throughput_pass"])
        self.assertFalse(r["acceptance_pass"])

    def test_identity_transfer(self):
        s = np.zeros((4, 4), complex)
        s[2:, :2] = np.eye(2)
        s[:2, 2:] = np.eye(2)
        r = evaluate(s)
        self.assertFalse(r["checks"]["fidelity_pass"])
        self.assertFalse(r["acceptance_pass"])

    def test_wrong_relative_phase(self):
        s = ideal()
        s[2, 0] *= np.exp(0.8j)
        s[0, 2] *= np.exp(0.8j)
        self.assertFalse(evaluate(s)["checks"]["fidelity_pass"])

    def test_convention_frozen(self):
        s = ideal().conj()
        self.assertFalse(evaluate(s)["acceptance_pass"])
        self.assertTrue(evaluate(s, convention="conjugate")["acceptance_pass"])
        with self.assertRaises(ValueError):
            evaluate(s, convention="auto")

    def test_nonfinite_wrongshape_zero_bool(self):
        s = ideal()
        s[0, 0] = np.nan
        with self.assertRaises(ValueError):
            evaluate(s)
        for v in (np.zeros((4, 3)), np.zeros((3, 3)), np.zeros((4, 4)), np.eye(4, dtype=bool)):
            with self.assertRaises(ValueError):
                evaluate(v)
        with self.assertRaises(ValueError):
            evaluate(np.eye(4))
        for pair in ([True, 0], [0, False], [0], [0, 0, 0], ["1", 0], [float("nan"), 0], 1):
            with self.assertRaises(ValueError):
                decode_pairs([[pair] * 4] * 4)
        with self.assertRaises(ValueError):
            evaluate(ideal(), policy={"fidelity_floor": True})
        with self.assertRaises(ValueError):
            evaluate(ideal(), input_indices=[False, 1])

    def test_passivity_reciprocity(self):
        self.assertFalse(evaluate(ideal() * 1.01)["checks"]["observed_passivity_pass"])
        s = ideal()
        s[0, 2] *= 0.8
        self.assertFalse(evaluate(s)["checks"]["observed_reciprocity_pass"])

    def test_expanded(self):
        s = ideal() * 0.8
        x = np.zeros((8, 8), complex)
        x[:4, :4] = s
        x[4, 0] = 0.1
        x[0, 4] = 0.1
        r = evaluate(s, additional_modes=x)
        self.assertAlmostEqual(r["observed_S"]["sum_observed_port_powers_per_input"][0], 0.64)
        self.assertAlmostEqual(r["additional_modes_observed_S"]["sum_observed_port_powers_per_input"][0], 0.65)
        x[0, 0] = 1
        with self.assertRaises(ValueError):
            evaluate(s, additional_modes=x)

    def test_pairs_roundtrip(self):
        s = ideal()
        pairs = [[[float(z.real), float(z.imag)] for z in row] for row in s]
        self.assertTrue(evaluate(decode_pairs(pairs))["acceptance_pass"])

    def run_cli(self, document):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.json"
            output = Path(temp) / "report.json"
            source.write_text(json.dumps(document), encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
            proc = subprocess.run(
                [sys.executable, "-m", "photonic_workflow.optimization.hadamard", str(source), "--output", str(output)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
                check=False,
            )
            report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
            return proc, report

    def test_cli_pass_zero_fail_two(self):
        for factor, expected in ((1, 0), (0.1, 2)):
            s = ideal() * factor
            document = {"S": [[[float(z.real), float(z.imag)] for z in row] for row in s]}
            proc, report = self.run_cli(document)
            self.assertEqual(proc.returncode, expected, proc.stderr)
            self.assertIsNotNone(report)
            self.assertEqual(report["acceptance_pass"], expected == 0)
            json.dumps(report, allow_nan=False)

    def test_cli_invalid_never_success(self):
        for element in ([False, 0], [float("nan"), 0], [float("inf"), 0], [0], 0):
            proc, report = self.run_cli({"S": [[element] * 4] * 4})
            self.assertNotEqual(proc.returncode, 0)
            self.assertIsNone(report)
            self.assertIn("error:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
