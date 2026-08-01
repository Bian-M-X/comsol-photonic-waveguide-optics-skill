from __future__ import annotations

import json
import math
import unittest

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.materials import (
    evaluate_li_silicon_1980,
    evaluate_malitson_fused_silica_1965,
    li_silicon_1980,
    malitson_fused_silica_1965,
)


class MaterialRecipeTests(unittest.TestCase):
    def test_li_reference_point_and_bulk_claim_are_json_safe(self) -> None:
        result = li_silicon_1980(1.55, 293.15)
        self.assertAlmostEqual(result["refractive_index"], 3.4757150826645455, places=14)
        self.assertAlmostEqual(result["relative_permittivity"], 12.080595335861808, places=13)
        self.assertAlmostEqual(result["dn_dlambda_per_um"], -0.07958432374788112, places=14)
        self.assertFalse(result["claim"]["is_waveguide_modal_result"])
        json.dumps(result, allow_nan=False)

    def test_li_derivative_and_bulk_group_index_crosscheck(self) -> None:
        wavelength = 1.63
        step = 1e-6
        result = li_silicon_1980(wavelength)
        derivative = (
            li_silicon_1980(wavelength + step)["refractive_index"]
            - li_silicon_1980(wavelength - step)["refractive_index"]
        ) / (2.0 * step)
        self.assertAlmostEqual(result["dn_dlambda_per_um"], derivative, delta=2e-9)
        self.assertAlmostEqual(
            result["bulk_group_index"],
            result["refractive_index"] - wavelength * result["dn_dlambda_per_um"],
            places=14,
        )

    def test_malitson_is_explicitly_a_bulk_surrogate(self) -> None:
        wavelength = 1.55
        step = 1e-6
        result = malitson_fused_silica_1965(wavelength)
        self.assertAlmostEqual(result["refractive_index"], 1.444023621703261, places=14)
        self.assertAlmostEqual(result["dn_dlambda_per_um"], -0.011982491736057425, places=14)
        derivative = (
            malitson_fused_silica_1965(wavelength + step)["refractive_index"]
            - malitson_fused_silica_1965(wavelength - step)["refractive_index"]
        ) / (2.0 * step)
        self.assertAlmostEqual(result["dn_dlambda_per_um"], derivative, delta=2e-9)
        self.assertAlmostEqual(
            result["bulk_group_index"],
            result["refractive_index"] - wavelength * result["dn_dlambda_per_um"],
            places=14,
        )
        self.assertEqual(result["claim"]["level"], "bulk_material_surrogate_formula")
        self.assertFalse(result["claim"]["is_deposited_or_foundry_oxide_metrology"])
        json.dumps(result, allow_nan=False)

    def test_material_inputs_fail_closed(self) -> None:
        invalid_calls = (
            lambda: li_silicon_1980(True),
            lambda: li_silicon_1980(math.nan),
            lambda: li_silicon_1980(10**10000),
            lambda: li_silicon_1980(1.0),
            lambda: li_silicon_1980(1.55, 751.0),
            lambda: malitson_fused_silica_1965(float("inf")),
            lambda: malitson_fused_silica_1965(10**10000),
            lambda: malitson_fused_silica_1965(4.0),
        )
        for call in invalid_calls:
            with self.subTest(call=call), self.assertRaises(InvalidInputError):
                call()

    def test_strict_evaluators_reject_unknown_parameter_keys(self) -> None:
        li = evaluate_li_silicon_1980({"wavelength_um": 1.55})
        malitson = evaluate_malitson_fused_silica_1965({"wavelength_um": 1.55})
        self.assertEqual(li["model"], "Li1980_equation_22")
        self.assertEqual(malitson["model"], "Malitson1965_equation_2")
        with self.assertRaisesRegex(InvalidInputError, "unknown"):
            evaluate_li_silicon_1980({"wavelength_um": 1.55, "units": "nm"})
        with self.assertRaisesRegex(InvalidInputError, "unknown"):
            evaluate_malitson_fused_silica_1965({"wavelength_um": 1.55, "temperature_k": 293.15})


if __name__ == "__main__":
    unittest.main()
