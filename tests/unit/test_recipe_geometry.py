from __future__ import annotations

import math
import unittest

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.geometry import (
    compute_circular_bend,
    compute_circular_route,
    compute_symmetric_euler_bend,
    evaluate_circular_route,
    evaluate_symmetric_euler_bend,
)


class CircularRecipeTests(unittest.TestCase):
    def test_circular_bend_and_route_preserve_requested_radius(self) -> None:
        bend = compute_circular_bend((-10.0, 0.0), (0.0, 0.0), (0.0, 10.0), 2.0)
        self.assertAlmostEqual(bend["cutback"], 2.0, places=12)
        self.assertAlmostEqual(bend["a1"] - bend["a0"], math.pi / 2.0, places=12)

        route = compute_circular_route(
            [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
            radius=2.0,
            width=0.5,
        )
        self.assertAlmostEqual(route["centerline_length"], 16.0 + math.pi, places=12)

    def test_circular_evaluator_has_closed_parameter_schema(self) -> None:
        parameters = {
            "vertices_um": [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
            "radius_um": 2.0,
            "width_um": 0.5,
        }
        evaluated = evaluate_circular_route(parameters)
        self.assertEqual(len(evaluated["bends"]), 1)
        self.assertEqual(evaluated["length_unit"], "um")
        self.assertAlmostEqual(evaluated["centerline_length_um"], 16.0 + math.pi)
        with self.assertRaisesRegex(InvalidInputError, "unknown circular-route"):
            evaluate_circular_route({**parameters, "java": "g.run();"})

    def test_circular_evaluator_rejects_malicious_json_types(self) -> None:
        baseline = {
            "vertices_um": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
            "radius_um": 2.0,
            "width_um": 0.5,
        }
        invalid_cases = (
            {"vertices_um": "0,0;10,0"},
            {"vertices_um": [[0.0, 0.0], [10.0, "payload"]]},
            {"radius_um": "2.0"},
            {"radius_um": True},
            {"radius_um": 10**400},
            {"width_um": [0.5]},
        )
        for change in invalid_cases:
            with self.subTest(change=change), self.assertRaises(InvalidInputError):
                evaluate_circular_route(baseline | change)

    def test_two_vertex_route_rejects_a_degenerate_segment(self) -> None:
        with self.assertRaisesRegex(InvalidInputError, "zero or near-zero"):
            compute_circular_route(
                [(1.0, 1.0), (1.0, 1.0)],
                radius=2.0,
                width=0.5,
            )


class SymmetricEulerRecipeTests(unittest.TestCase):
    def test_r5_ninety_degree_regression_and_boundary_shape(self) -> None:
        bend = compute_symmetric_euler_bend(
            turn_angle_deg=90.0,
            minimum_radius_um=5.0,
            width_um=0.5,
            samples=64,
        )
        self.assertAlmostEqual(bend["cutback"], 9.350479137922, places=12)
        self.assertAlmostEqual(bend["length"], 5.0 * math.pi, places=12)
        self.assertEqual(len(bend["centerline"]), 65)
        self.assertEqual(len(bend["tangent"]), 65)
        self.assertEqual(len(bend["boundary_table"]), 130)
        self.assertEqual(bend["claim_level"], "configuration-only-2d-eim")
        self.assertAlmostEqual(bend["tangent"][0][0], 1.0, places=15)
        self.assertAlmostEqual(bend["tangent"][0][1], 0.0, places=15)
        self.assertAlmostEqual(bend["tangent"][-1][0], 0.0, places=15)
        self.assertAlmostEqual(bend["tangent"][-1][1], 1.0, places=15)
        self.assertTrue(
            all(math.isfinite(value) for point in bend["boundary_table"] for value in point)
        )
        self.assertAlmostEqual(
            math.dist(bend["boundary_table"][0], bend["boundary_table"][-1]),
            0.5,
            places=12,
        )

    def test_negative_turn_reflects_centerline_and_tangent(self) -> None:
        left = compute_symmetric_euler_bend(60.0, 4.0, 0.4, 64)
        right = compute_symmetric_euler_bend(-60.0, 4.0, 0.4, 64)
        self.assertAlmostEqual(left["cutback"], right["cutback"], places=12)
        for left_point, right_point in zip(left["centerline"], right["centerline"], strict=True):
            self.assertAlmostEqual(left_point[0], right_point[0], places=12)
            self.assertAlmostEqual(left_point[1], -right_point[1], places=12)
        self.assertLess(right["tangent"][-1][1], 0.0)

    def test_invalid_euler_inputs_fail_closed(self) -> None:
        invalid_cases = (
            ({"turn_angle_deg": math.nan}, "finite"),
            ({"turn_angle_deg": 0.0}, "zero"),
            ({"turn_angle_deg": 180.0}, "below 180"),
            ({"minimum_radius_um": 0.0}, "radius"),
            ({"width_um": 10.0}, "width"),
            ({"samples": 7}, "samples"),
            ({"samples": 63}, "samples"),
            ({"samples": 64.0}, "samples"),
            ({"turn_angle_deg": "90"}, "real number"),
            ({"minimum_radius_um": True}, "real number"),
            ({"minimum_radius_um": 10**400}, "finite number"),
            ({"width_um": [0.5]}, "real number"),
        )
        baseline = {
            "turn_angle_deg": 90.0,
            "minimum_radius_um": 5.0,
            "width_um": 0.5,
            "samples": 64,
        }
        for change, message in invalid_cases:
            with self.subTest(change=change), self.assertRaisesRegex(
                InvalidInputError,
                message,
            ):
                compute_symmetric_euler_bend(**(baseline | change))

    def test_euler_evaluator_rejects_unknown_keys(self) -> None:
        parameters = {
            "turn_angle_deg": 90.0,
            "minimum_radius_um": 5.0,
            "width_um": 0.5,
        }
        self.assertEqual(evaluate_symmetric_euler_bend(parameters)["samples"], 64)
        with self.assertRaisesRegex(InvalidInputError, "unknown symmetric-euler-bend"):
            evaluate_symmetric_euler_bend({**parameters, "tag": "attacker-controlled"})


if __name__ == "__main__":
    unittest.main()
