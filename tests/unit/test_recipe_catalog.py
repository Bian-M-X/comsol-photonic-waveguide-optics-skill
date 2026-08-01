from __future__ import annotations

import unittest

from photonic_workflow.exceptions import IncompatibleVersionError, InvalidInputError
from photonic_workflow.recipes import (
    evaluate_recipe,
    inspect_recipe,
    list_recipes,
    parse_recipe_request,
)
from photonic_workflow.recipes.catalog import RECIPE_CATALOG
from photonic_workflow.recipes.renderers import (
    COMSOL_INTERNAL_RECIPE_IDS,
    COMSOL_RECIPE_BINDINGS,
)
from photonic_workflow.recipes.service import (
    MAX_RECIPE_JSON_DEPTH,
    MAX_RECIPE_REQUEST_BYTES,
)
from photonic_workflow.recipes.types import RecipeRenderer

EXPECTED_RECIPE_IDS = (
    "geometry.circular-route",
    "geometry.symmetric-euler-bend",
    "materials.li-silicon-1980",
    "materials.malitson-fused-silica-1965",
    "scattering.two-port-common-basis",
    "waveguide.segmented-port-window",
)


class RecipeCatalogTests(unittest.TestCase):
    def test_catalog_is_frozen_complete_and_fail_closed(self) -> None:
        descriptors = list_recipes()
        self.assertEqual(
            tuple(item.recipe_id for item in descriptors),
            EXPECTED_RECIPE_IDS,
        )
        self.assertTrue(all(item.recipe_version == "1.0.0" for item in descriptors))
        self.assertTrue(
            all(
                item.support_level.value
                in {"documented", "unit-tested", "configuration-audited"}
                for item in descriptors
            )
        )
        self.assertTrue(
            all(item.to_payload()["physics_accepted"] is False for item in descriptors)
        )
        self.assertTrue(all(item.parameter_contract for item in descriptors))
        circular_contract = inspect_recipe(
            "geometry.circular-route"
        ).to_payload()["parameter_contract"]
        self.assertEqual(
            [item["name"] for item in circular_contract],
            ["vertices_um", "radius_um", "width_um"],
        )
        self.assertEqual(circular_contract[0]["json_type"], "array")
        self.assertEqual(circular_contract[0]["items"], "array[number, number]")
        self.assertEqual(circular_contract[0]["unit"], "um")
        self.assertTrue(circular_contract[0]["required"])
        self.assertEqual(circular_contract[1]["exclusive_minimum"], 0.0)
        with self.assertRaises(TypeError):
            RECIPE_CATALOG["unexpected"] = RECIPE_CATALOG[EXPECTED_RECIPE_IDS[0]]  # type: ignore[index]

    def test_unknown_recipe_and_version_mismatch_are_distinct(self) -> None:
        with self.assertRaisesRegex(InvalidInputError, "unknown modeling recipe"):
            inspect_recipe("geometry.not-a-recipe")
        with self.assertRaisesRegex(IncompatibleVersionError, "available version"):
            inspect_recipe("geometry.circular-route", version="2.0.0")

    def test_comsol_renderer_binding_is_one_closed_registry(self) -> None:
        advertised = {
            descriptor.recipe_id
            for descriptor in list_recipes()
            if RecipeRenderer.COMSOL_JAVA_FRAGMENT in descriptor.renderers
        }
        self.assertEqual(advertised, set(COMSOL_RECIPE_BINDINGS))
        self.assertEqual(
            COMSOL_INTERNAL_RECIPE_IDS,
            frozenset(COMSOL_RECIPE_BINDINGS.values()),
        )

    def test_structured_contract_applies_defaults_and_common_bounds(self) -> None:
        result = evaluate_recipe(
            "geometry.symmetric-euler-bend",
            {
                "turn_angle_deg": 90.0,
                "minimum_radius_um": 5.0,
                "width_um": 0.5,
            },
            version="1.0.0",
        )
        self.assertEqual(result.parameters["samples"], 64)
        with self.assertRaisesRegex(InvalidInputError, "exclusive minimum"):
            evaluate_recipe(
                "geometry.circular-route",
                {
                    "vertices_um": [[0.0, 0.0], [1.0, 0.0]],
                    "radius_um": 0.0,
                    "width_um": 0.5,
                },
            )

    def test_request_parser_rejects_duplicate_nonfinite_and_unknown_keys(self) -> None:
        base = (
            '{"schema_version":"1.0","recipe_id":"geometry.circular-route",'
            '"recipe_version":"1.0.0","parameters":{}}'
        )
        parsed = parse_recipe_request(base)
        self.assertEqual(parsed.recipe_id, "geometry.circular-route")

        invalid = {
            "duplicate": (
                '{"schema_version":"1.0","recipe_id":"geometry.circular-route",'
                '"recipe_version":"1.0.0","parameters":{"radius_um":1,"radius_um":2}}'
            ),
            "nonfinite": (
                '{"schema_version":"1.0","recipe_id":"geometry.circular-route",'
                '"recipe_version":"1.0.0","parameters":{"radius_um":NaN}}'
            ),
            "unknown": (
                '{"schema_version":"1.0","recipe_id":"geometry.circular-route",'
                '"recipe_version":"1.0.0","parameters":{},"execute":true}'
            ),
        }
        for label, text in invalid.items():
            with self.subTest(label=label), self.assertRaises(InvalidInputError):
                parse_recipe_request(text)

    def test_request_schema_version_mismatch_is_incompatible(self) -> None:
        with self.assertRaises(IncompatibleVersionError):
            parse_recipe_request(
                '{"schema_version":"2.0","recipe_id":"geometry.circular-route",'
                '"recipe_version":"1.0.0","parameters":{}}'
            )

    def test_request_size_is_bounded_before_json_parsing(self) -> None:
        with self.assertRaisesRegex(InvalidInputError, "exceeds"):
            parse_recipe_request(" " * (MAX_RECIPE_REQUEST_BYTES + 1))

    def test_pathological_json_depth_and_integer_fail_as_invalid_input(self) -> None:
        nested = "[" * (MAX_RECIPE_JSON_DEPTH + 1000) + "0" + "]" * (
            MAX_RECIPE_JSON_DEPTH + 1000
        )
        with self.assertRaises(InvalidInputError):
            parse_recipe_request(nested)
        with self.assertRaisesRegex(InvalidInputError, "invalid recipe request JSON"):
            parse_recipe_request("{" + '"n":' + "9" * 5000 + "}")

        deeply_nested: object = 0
        for _ in range(MAX_RECIPE_JSON_DEPTH + 1):
            deeply_nested = [deeply_nested]
        with self.assertRaisesRegex(InvalidInputError, "nesting depth"):
            evaluate_recipe(
                "geometry.circular-route",
                {
                    "vertices_um": deeply_nested,  # type: ignore[dict-item]
                    "radius_um": 2.0,
                    "width_um": 0.5,
                },
            )


if __name__ == "__main__":
    unittest.main()
