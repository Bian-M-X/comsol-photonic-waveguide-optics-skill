from __future__ import annotations

import unittest

import numpy as np

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.optimization.numerics import (
    ConicFilter,
    allocate_error_budget,
    compare_error_intervals,
    complex_target_metrics,
    density_binarization_metrics,
    directional_gradient_check,
    smooth_worst_case,
    tanh_projection,
)


class OptimizationNumericsTests(unittest.TestCase):
    def test_binarization_metrics_respect_volume_weights_and_subdivision(self) -> None:
        measured = density_binarization_metrics([0, 0.5], weights=[1, 9])
        self.assertAlmostEqual(measured["grayness"], 0.9)
        self.assertAlmostEqual(measured["mean_absolute_half_threshold_discrepancy"], 0.45)
        np.testing.assert_allclose(measured["discrepancy_bounds_from_grayness"], [0.225, 0.45], rtol=1e-14)
        self.assertAlmostEqual(density_binarization_metrics([0, 0.5])["grayness"], 0.5)
        subdivided = density_binarization_metrics([0, 0.5, 0.5], weights=[1, 4, 5])
        for key in ("grayness", "gray_fraction_10_90", "mean_absolute_half_threshold_discrepancy"):
            self.assertAlmostEqual(subdivided[key], measured[key])
        large = density_binarization_metrics([0, 0.5], weights=[1e308, 1e308])
        self.assertEqual(large["grayness"], 0.5)

    def test_grayness_bounds_and_projection_counterexample(self) -> None:
        rho = np.linspace(0, 1, 1001)
        measured = density_binarization_metrics(rho, weights=np.linspace(1, 3, len(rho)))
        low, high = measured["discrepancy_bounds_from_grayness"]
        discrepancy = measured["mean_absolute_half_threshold_discrepancy"]
        self.assertLessEqual(low, discrepancy)
        self.assertLessEqual(discrepancy, high)
        self.assertEqual(density_binarization_metrics([0, 1])["grayness"], 0)
        fractions = density_binarization_metrics([0, 0.01, 0.1, 0.5, 0.9, 0.99, 1])
        self.assertAlmostEqual(fractions["gray_fraction_10_90"], 1 / 7)
        self.assertAlmostEqual(fractions["gray_fraction_01_99"], 3 / 7)
        # Reoptimized controls can follow the shrinking transition while the
        # physical material remains gray, even at large projection beta.
        for beta in (32, 128, 512):
            projected, _ = tanh_projection([0.5 + np.arctanh(0.5) / beta], beta)
            self.assertAlmostEqual(projected[0], 0.75, places=12)
            self.assertAlmostEqual(density_binarization_metrics(projected)["grayness"], 0.75, places=12)

    def test_binarization_metrics_reject_invalid_samples_and_weights(self) -> None:
        for density in ([], [True], [1j], [float("nan")], [-0.01], [1.01]):
            with self.subTest(density=density), self.assertRaises(InvalidInputError):
                density_binarization_metrics(density)
        for weights in ([0, 0], [1, -1], [True, False], [float("inf"), 1], [1], [[1, 2]]):
            with self.subTest(weights=weights), self.assertRaises(InvalidInputError):
                density_binarization_metrics([0.2, 0.8], weights=weights)

    def test_filter_preserves_constants_and_exact_transpose_at_edges(self) -> None:
        rng = np.random.default_rng(271)
        f = ConicFilter((9, 7), 3.7)
        np.testing.assert_allclose(f.forward(np.ones(f.shape)), 1)
        x, v = rng.normal(size=f.shape), rng.normal(size=f.shape)
        self.assertAlmostEqual(float(np.sum(f.forward(x) * v)), float(np.sum(x * f.vjp(v))), places=12)
        self.assertGreater(np.linalg.norm(f.forward(v) - f.vjp(v)), 0.01)

    def test_double_filter_projection_full_chain_directional_derivative(self) -> None:
        rng = np.random.default_rng(19)
        first, second = ConicFilter((11, 8), 3.2), ConicFilter((11, 8), 2.1)
        rho = rng.uniform(0.25, 0.75, size=first.shape)
        probe = rng.normal(size=first.shape)

        def evaluate(x: np.ndarray) -> tuple[float, np.ndarray]:
            p1, d1 = tanh_projection(first.forward(x), 3.0)
            p2, d2 = tanh_projection(second.forward(p1), 6.0, 0.35)
            loss = float(np.sum(probe * p2**2))
            gradient = first.vjp(d1 * second.vjp(d2 * 2 * p2 * probe))
            return loss, gradient

        _, gradient = evaluate(rho)
        report = directional_gradient_check(lambda x: evaluate(x)[0], rho, gradient, rng.normal(size=rho.shape))
        self.assertTrue(report["passed"])
        self.assertEqual(report["evaluations"], 6)

    def test_projection_erosion_order_and_endpoints(self) -> None:
        rho = np.linspace(0, 1, 101)
        dilated, _ = tanh_projection(rho, 12, 0.3)
        nominal, _ = tanh_projection(rho, 12, 0.5)
        eroded, _ = tanh_projection(rho, 12, 0.7)
        self.assertTrue(np.all(dilated >= nominal - 1e-14))
        self.assertTrue(np.all(nominal >= eroded - 1e-14))
        np.testing.assert_allclose(nominal[[0, -1]], [0, 1])
        with self.assertRaises(InvalidInputError):
            tanh_projection([0, 1.001], 8)

    def test_smooth_max_bound_and_derivative(self) -> None:
        loss = np.array([1e4, 1e4 + 0.2, 1e4 - 2])
        value, weights = smooth_worst_case(loss, 0.1)
        self.assertGreaterEqual(value, loss.max())
        self.assertLessEqual(value, loss.max() + 0.1 * np.log(3))
        self.assertAlmostEqual(float(weights.sum()), 1)
        report = directional_gradient_check(lambda x: smooth_worst_case(x, 0.1)[0], loss, weights, [1, -2, 3])
        self.assertTrue(report["passed"])

    def test_complex_metric_distinguishes_loss_and_relative_phase(self) -> None:
        target = np.array([[1, 1j], [1j, 1]]) / np.sqrt(2)
        lossy = complex_target_metrics(0.1 * np.exp(0.4j) * target, target)
        self.assertAlmostEqual(lossy["shape_overlap"], 1)
        np.testing.assert_allclose(lossy["column_power"], [0.01, 0.01])
        self.assertAlmostEqual(lossy["relative_error_after_global_phase"], 0.9)
        wrong_phase = complex_target_metrics(np.abs(target), target)
        self.assertLess(wrong_phase["shape_overlap"], 0.6)
        zero = complex_target_metrics(np.zeros((2, 2)), target)
        self.assertEqual(zero["shape_overlap"], 0)
        self.assertEqual(zero["relative_error_after_global_phase"], 1)

    def test_complex_discrete_adjoint_and_wrong_sign(self) -> None:
        rng = np.random.default_rng(32)
        base = np.eye(5) * (3 + 0.4j) + rng.normal(size=(5, 5)) * 0.1
        b, c = rng.normal(size=5) + 1j * rng.normal(size=5), rng.normal(size=5) + 1j * rng.normal(size=5)
        rho = rng.uniform(0.3, 0.7, size=5)

        def objective(x: np.ndarray) -> float:
            return float(abs(np.vdot(c, np.linalg.solve(base + np.diag(x), b)))**2)

        a = base + np.diag(rho)
        field = np.linalg.solve(a, b)
        adjoint = np.linalg.solve(a.conj().T, c * np.vdot(c, field))
        gradient = -2 * np.real(adjoint.conj() * field)
        direction = rng.normal(size=5)
        self.assertTrue(directional_gradient_check(objective, rho, gradient, direction)["passed"])
        self.assertFalse(directional_gradient_check(objective, rho, -gradient, direction)["passed"])

    def test_error_budget_prevents_false_ranking(self) -> None:
        self.assertEqual(compare_error_intervals(0.1, 0.11, 0.01, 0.01)["decision"], "unresolved")
        self.assertEqual(compare_error_intervals(0.1, 0.2, 0.01, 0.02)["decision"], "improvement_resolved")
        for invalid in (float("nan"), float("inf"), -0.1):
            with self.assertRaises(InvalidInputError):
                compare_error_intervals(0.1, 0.2, invalid, 0)

    def test_task_error_allocation_beats_uniform_allocation_under_its_cost_model(self) -> None:
        sensitivity, cost, target = np.array([1.0, 4.0, 0.25]), np.array([1.0, 5.0, 2.0]), 0.02
        result = allocate_error_budget(sensitivity, cost, target)
        error = np.array(result["component_errors"])
        uniform = target / sensitivity.sum()
        self.assertAlmostEqual(float(sensitivity @ error), target)
        self.assertLess(float(np.sum(cost / error**2)), float(np.sum(cost / uniform**2)))
        multipliers = 2 * cost / (sensitivity * error**3)
        np.testing.assert_allclose(multipliers, multipliers[0], rtol=1e-12)

    def test_nonfinite_boolean_and_invalid_inputs_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            smooth_worst_case([True, False], 0.1)
        with self.assertRaises(InvalidInputError):
            smooth_worst_case([float("nan")], 0.1)
        with self.assertRaises(InvalidInputError):
            ConicFilter((1001, 1000), 1)
        with self.assertRaises(InvalidInputError):
            complex_target_metrics([[1]], [[0]])


if __name__ == "__main__":
    unittest.main()
