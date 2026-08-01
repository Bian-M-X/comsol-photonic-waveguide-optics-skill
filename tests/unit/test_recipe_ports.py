from __future__ import annotations

import math
import unittest

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.ports import (
    audit_exterior_boundary_partition,
    evaluate_segmented_port_window,
    segmented_port_window_plan,
)


class SegmentedPortWindowRecipeTests(unittest.TestCase):
    def parameters(self) -> dict[str, float]:
        return {
            "x_min_um": -30.0,
            "x_max_um": 30.0,
            "y_min_um": -8.0,
            "y_max_um": 8.0,
            "port_center_y_um": 0.0,
            "port_half_height_um": 3.0,
            "selection_tolerance_um": 0.01,
        }

    def test_plan_segments_background_and_subtracts_both_ports(self) -> None:
        plan = segmented_port_window_plan(**self.parameters())
        self.assertFalse(plan["will_execute"])
        self.assertEqual(plan["claim_level"], "configuration-only-2d-eim")
        self.assertEqual(plan["length_unit"], "um")
        self.assertNotIn("recipe_id", plan)
        self.assertNotIn("recipe_version", plan)
        self.assertEqual(len(plan["background_slabs"]), 3)
        self.assertEqual(len(plan["port_windows"]), 2)
        self.assertEqual(
            plan["background_slabs"][1]["bounds_um"],
            (-30.0, 30.0, -3.0, 3.0),
        )
        self.assertEqual(
            plan["scattering_boundary_difference"]["subtract"],
            ("port_1_boundary", "port_2_boundary"),
        )
        rules = {rule["metric"]: rule for rule in plan["entity_count_rules"]}
        self.assertEqual(rules["background_slab_domain_count"]["expected"], 3)
        self.assertEqual(rules["port_scattering_overlap_count"]["expected"], 0)
        self.assertEqual(rules["port_port_overlap_count"]["expected"], 0)
        self.assertEqual(rules["exterior_boundary_missing_count"]["expected"], 0)
        self.assertEqual(rules["nonexterior_boundary_selected_count"]["expected"], 0)
        self.assertEqual(rules["port_1_boundary_count"]["operator"], "gte")
        self.assertIn("port_boundary_count_symmetry", rules)

    def test_exterior_partition_accepts_only_complete_disjoint_selection(self) -> None:
        audit = audit_exterior_boundary_partition(
            exterior_boundary_ids=[3, 5, 12, 20, 48, 51],
            port_boundary_ids={"port_1": [3, 5], "port_2": [51]},
            open_boundary_ids=[12, 20, 48],
        )
        self.assertEqual(audit["status"], "pass")
        self.assertEqual(audit["port_boundary_count"], 3)
        self.assertEqual(audit["open_boundary_count"], 3)
        self.assertEqual(audit["exterior_boundary_missing_count"], 0)

    def test_exterior_partition_rejects_overlap_missing_and_nonexterior(self) -> None:
        cases = (
            (
                {"port_1": [3, 5], "port_2": [51]},
                [12, 20, 48, 51],
                "port_open_overlap",
            ),
            (
                {"port_1": [3, 5], "port_2": [51]},
                [12, 20],
                "missing",
            ),
            (
                {"port_1": [3, 5], "port_2": [51]},
                [12, 20, 48, 99],
                "nonexterior",
            ),
            (
                {"port_1": [3, 5], "port_2": [5]},
                [12, 20, 48, 51],
                "port selections overlap",
            ),
        )
        for ports, open_ids, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(
                InvalidInputError,
                message,
            ):
                audit_exterior_boundary_partition(
                    exterior_boundary_ids=[3, 5, 12, 20, 48, 51],
                    port_boundary_ids=ports,
                    open_boundary_ids=open_ids,
                )

    def test_evaluator_rejects_unknown_and_missing_parameters(self) -> None:
        parameters = self.parameters()
        self.assertEqual(evaluate_segmented_port_window(parameters)["length_unit"], "um")
        with self.assertRaisesRegex(InvalidInputError, "unknown segmented-port-window"):
            evaluate_segmented_port_window({**parameters, "expression": "system('x')"})
        without_x_min = {key: value for key, value in parameters.items() if key != "x_min_um"}
        with self.assertRaisesRegex(InvalidInputError, "missing segmented-port-window"):
            evaluate_segmented_port_window(without_x_min)

    def test_invalid_extents_and_nonfinite_values_fail_closed(self) -> None:
        cases = (
            ({"x_max_um": -30.0}, "x_min_um"),
            ({"y_max_um": -8.0}, "y_min_um"),
            ({"port_half_height_um": 0.0}, "positive"),
            ({"port_half_height_um": 9.0}, "strictly inside"),
            ({"selection_tolerance_um": 0.0}, "positive"),
            ({"selection_tolerance_um": 31.0}, "too large"),
            ({"port_center_y_um": math.inf}, "finite"),
        )
        baseline = self.parameters()
        for change, message in cases:
            with self.subTest(change=change), self.assertRaisesRegex(
                InvalidInputError,
                message,
            ):
                segmented_port_window_plan(**(baseline | change))

    def test_evaluator_rejects_malicious_json_types(self) -> None:
        baseline = self.parameters()
        invalid_cases = (
            {"x_min_um": "-30"},
            {"x_max_um": True},
            {"x_max_um": 10**400},
            {"port_center_y_um": [0.0]},
        )
        for change in invalid_cases:
            with self.subTest(change=change), self.assertRaises(InvalidInputError):
                evaluate_segmented_port_window(baseline | change)


if __name__ == "__main__":
    unittest.main()
