from __future__ import annotations

import unittest

import numpy as np

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.optimization.robustness import axial_scenarios, weighted_pattern_loss


class OptimizationRobustnessTests(unittest.TestCase):
    def test_axial_order_and_mixed_interaction_blind_spot(self) -> None:
        scenarios = axial_scenarios(2)
        np.testing.assert_array_equal(scenarios, [[0, 0], [1, 0], [-1, 0], [0, 1], [0, -1]])
        np.testing.assert_array_equal(scenarios[:, 0] * scenarios[:, 1], np.zeros(5))
        joint_corner = np.ones(2)
        self.assertEqual(joint_corner[0] * joint_corner[1], 1)
        self.assertEqual(axial_scenarios(64).shape, (129, 64))
        self.assertEqual(axial_scenarios(np.int64(1)).shape, (3, 1))

    def test_axial_invalid_dimensions(self) -> None:
        for dimension in (True, np.bool_(False), 0, -1, 65, 2.0, "2", None, float("nan")):
            with self.subTest(dimension=dimension), self.assertRaises(InvalidInputError):
                axial_scenarios(dimension)

    def test_gradient_at_two_steps_with_nonuniform_area_weights(self) -> None:
        wafer = np.array([[0.3, 0.6], [0.45, 0.7]])
        target = np.array([[0.5, 0.2], [0.6, 0.4]])
        sensitivity = np.array([[0.0, -4.0], [2.0, 1.0]])
        weights = np.array([[1.0, 7.0], [2.0, 3.0]])
        direction = np.array([[0.2, -0.5], [0.7, 0.1]])
        _, derivative, _ = weighted_pattern_loss(wafer, target, sensitivity, quadrature_weights=weights)
        exact = float(np.sum(derivative * direction))
        for step in (1e-4, 1e-5):
            plus = weighted_pattern_loss(wafer + step * direction, target, sensitivity, quadrature_weights=weights)[0]
            minus = weighted_pattern_loss(wafer - step * direction, target, sensitivity, quadrature_weights=weights)[0]
            self.assertAlmostEqual((plus - minus) / (2 * step), exact, delta=1e-8)

    def test_gamma_is_inside_fourth_power_and_sensitivity_scale_invariant(self) -> None:
        loss, derivative, gamma = weighted_pattern_loss([0.75, 0.75], [0.5, 0.5], [0.0, -2.0])
        np.testing.assert_array_equal(gamma, [0.5, 1.5])
        self.assertAlmostEqual(loss, 0.25**4 * (0.5**4 + 1.5**4) / 2)
        self.assertNotAlmostEqual(loss, 0.25**4 * np.mean(gamma))
        for sensitivity in ([0.0, -2e-300], [0.0, -1e308]):
            other = weighted_pattern_loss([0.75, 0.75], [0.5, 0.5], sensitivity)
            self.assertEqual(other[0], loss)
            np.testing.assert_array_equal(other[1], derivative)

    def test_zero_sensitivity_and_overflow_safe_area_normalization(self) -> None:
        loss, derivative, gamma = weighted_pattern_loss([0.2, 0.8], [0.5, 0.5], [0, 0])
        np.testing.assert_array_equal(gamma, [1, 1])
        self.assertAlmostEqual(loss, 0.3**4)
        np.testing.assert_allclose(derivative, [-2 * 0.3**3, 2 * 0.3**3])
        large = weighted_pattern_loss([0.2, 0.8], [0.5, 0.5], [0, 0], quadrature_weights=[1e308, 1e308])
        self.assertEqual(large[0], loss)
        np.testing.assert_array_equal(large[1], derivative)
        # Cell subdivision with unchanged density and total area preserves loss.
        coarse = weighted_pattern_loss([0.2, 0.7], [0.5, 0.5], [0, 0], quadrature_weights=[1, 9])[0]
        fine = weighted_pattern_loss([0.2, 0.7, 0.7], [0.5] * 3, [0] * 3, quadrature_weights=[1, 4, 5])[0]
        self.assertAlmostEqual(coarse, fine)

    def test_mean_image_cancels_errors_but_mean_loss_does_not(self) -> None:
        # Exact opposing-error cancellation uses a gray target in the interior.
        target = np.array([0.5, 0.5])
        delta = np.array([0.1, -0.2])
        wafers = [target + delta, target - delta]
        losses = [weighted_pattern_loss(wafer, target, [0, 0])[0] for wafer in wafers]
        mean_image_loss = weighted_pattern_loss(np.mean(wafers, axis=0), target, [0, 0])[0]
        self.assertEqual(mean_image_loss, 0)
        self.assertAlmostEqual(float(np.mean(losses)), (0.1**4 + 0.2**4) / 2)
        self.assertGreater(min(losses), 0)

    def test_binary_target_mean_image_underestimates_mean_and_worst_loss(self) -> None:
        target, sensitivity = [0], [0]
        wafers = [[0], [0], [1]]
        losses = [weighted_pattern_loss(wafer, target, sensitivity)[0] for wafer in wafers]
        image_loss = weighted_pattern_loss(np.mean(wafers, axis=0), target, sensitivity)[0]
        self.assertAlmostEqual(image_loss, 1 / 81)
        self.assertAlmostEqual(float(np.mean(losses)), 1 / 3)
        self.assertEqual(max(losses), 1)
        self.assertAlmostEqual(float(np.mean(losses)) / image_loss, 27)

    def test_invalid_samples_shapes_and_ranges(self) -> None:
        invalid = ([], [float("nan"), 0], [float("inf"), 0], [1j, 0], ["0", "1"], [10**400, 0],
                   [True, False], [True, 0.2], [np.bool_(False), 1], [[0.2], [0.3, 0.4]],
                   np.array([True, False]), np.array([0.2, 0.3], dtype=object))
        for field in range(3):
            for value in invalid:
                args = [[0.2, 0.8], [0.5, 0.5], [0, 1]]
                args[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(InvalidInputError):
                    weighted_pattern_loss(*args)
        for wafer, target, sensitivity in (([-0.01], [0.5], [0]), ([0.5], [1.01], [0]),
                                            ([[0.5, 0.5]], [0.5, 0.5], [0, 0]), ([0.5], [0.5], [0, 1])):
            with self.subTest(wafer=wafer, target=target), self.assertRaises(InvalidInputError):
                weighted_pattern_loss(wafer, target, sensitivity)

    def test_invalid_quadrature_weights(self) -> None:
        for weights in ([], [0, 0], [1, -1], [True, False], [True, 1.0], [1j, 0],
                        [float("nan"), 1], [float("inf"), 1], [1], [[1, 2]]):
            with self.subTest(weights=weights), self.assertRaises(InvalidInputError):
                weighted_pattern_loss([0.2, 0.8], [0.5, 0.5], [0, 1], quadrature_weights=weights)


if __name__ == "__main__":
    unittest.main()
