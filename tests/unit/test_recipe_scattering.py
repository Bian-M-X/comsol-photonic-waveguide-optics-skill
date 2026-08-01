from __future__ import annotations

import json
import math
import unittest
from collections.abc import Callable

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.scattering import (
    audit_two_port_common_basis,
    evaluate_two_port_common_basis,
    largest_singular_value_2x2,
)


def _unitary_fixture() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    reflection = 0.2
    transmission = math.sqrt(1.0 - reflection**2)
    values = {
        (1, 1): complex(reflection, 0.0),
        (1, 2): complex(0.0, transmission),
        (2, 1): complex(0.0, transmission),
        (2, 2): complex(reflection, 0.0),
    }
    entries = [
        {
            "row": row,
            "column": column,
            "source_solution_index": column,
            "real": value.real,
            "imag": value.imag,
            "power": abs(value) ** 2,
        }
        for (row, column), value in values.items()
    ]
    ledgers = [
        {
            "source_port": source,
            "input_power_w": 1.0,
            "reflection_power_fraction": reflection**2,
            "transmission_power_fraction": transmission**2,
            "signed_nonport_exterior_flux_w": 0.0,
            "material_absorption_w": 0.0,
            "accounted_power_fraction": 1.0,
            "closure_residual_fraction": 0.0,
        }
        for source in (1, 2)
    ]
    return entries, ledgers


def _audit(
    entries: list[dict[str, object]],
    ledgers: list[dict[str, object]],
) -> dict[str, object]:
    return audit_two_port_common_basis(
        entries,
        ledgers,
        model_instance_id="synthetic-two-port",
        phase_basis_id="synthetic-frozen-basis-v1",
        phase_basis_frozen=True,
        nonport_flux_sign_convention="positive_outward",
        material_absorption_sign_convention="positive_absorbed",
    )


class ScatteringRecipeTests(unittest.TestCase):
    def test_common_basis_audit_recomputes_complete_diagnostic(self) -> None:
        entries, ledgers = _unitary_fixture()
        result = _audit(entries, ledgers)
        self.assertEqual(result["status"], "diagnostic_only")
        self.assertTrue(result["phase_basis"]["frozen"])
        self.assertTrue(result["checks"]["within_declared_diagnostic_tolerances"])
        self.assertAlmostEqual(result["metrics"]["largest_singular_value"], 1.0, places=14)
        self.assertAlmostEqual(result["metrics"]["unitarity_frobenius"], 0.0, places=14)
        json.dumps(result, allow_nan=False)

    def test_stable_near_unitary_singular_value_avoids_cancellation(self) -> None:
        theta = 0.37
        cosine = math.cos(theta)
        sine = math.sin(theta)
        sigma_1 = 1.0 - 1e-12
        sigma_2 = 1.0 - 2e-12
        s11 = sigma_1 * cosine**2 + sigma_2 * sine**2
        s12 = (sigma_1 - sigma_2) * cosine * sine
        s22 = sigma_1 * sine**2 + sigma_2 * cosine**2
        stable = largest_singular_value_2x2(s11, s12, s12, s22)

        trace = s11**2 + 2.0 * s12**2 + s22**2
        determinant_power = (s11 * s22 - s12**2) ** 2
        cancellation_prone = math.sqrt(
            0.5 * (trace + math.sqrt(max(0.0, trace**2 - 4.0 * determinant_power)))
        )
        self.assertAlmostEqual(stable, sigma_1, places=15)
        self.assertGreater(abs(cancellation_prone - stable), 1e-13)

    def test_unknown_nonfinite_duplicate_and_wrong_source_inputs_fail_closed(self) -> None:
        cases: list[tuple[str, Callable[[], object]]] = []

        entries, ledgers = _unitary_fixture()
        entries[0]["unexpected"] = 1
        cases.append(("unknown", lambda entries=entries, ledgers=ledgers: _audit(entries, ledgers)))

        entries, ledgers = _unitary_fixture()
        entries[0]["real"] = math.nan
        cases.append(("nonfinite", lambda entries=entries, ledgers=ledgers: _audit(entries, ledgers)))

        entries, ledgers = _unitary_fixture()
        entries[0]["real"] = 10**10000
        cases.append(("overflow", lambda entries=entries, ledgers=ledgers: _audit(entries, ledgers)))

        entries, ledgers = _unitary_fixture()
        entries[1] = dict(entries[0])
        cases.append(("duplicate", lambda entries=entries, ledgers=ledgers: _audit(entries, ledgers)))

        entries, ledgers = _unitary_fixture()
        entries[1]["source_solution_index"] = 1
        cases.append(("wrong_source", lambda entries=entries, ledgers=ledgers: _audit(entries, ledgers)))

        for label, call in cases:
            with self.subTest(label=label), self.assertRaises(InvalidInputError):
                call()

        with self.assertRaises(InvalidInputError):
            largest_singular_value_2x2(10**10000, 0.0, 0.0, 1.0)

    def test_power_ledger_arithmetic_and_frozen_basis_fail_closed(self) -> None:
        entries, ledgers = _unitary_fixture()
        ledgers[0]["closure_residual_fraction"] = 1e-2
        with self.assertRaisesRegex(InvalidInputError, "closure residual"):
            _audit(entries, ledgers)

        entries, ledgers = _unitary_fixture()
        with self.assertRaisesRegex(InvalidInputError, "explicitly true"):
            audit_two_port_common_basis(
                entries,
                ledgers,
                model_instance_id="synthetic-two-port",
                phase_basis_id="synthetic-basis",
                phase_basis_frozen=False,
                nonport_flux_sign_convention="positive_outward",
                material_absorption_sign_convention="positive_absorbed",
            )

        entries, ledgers = _unitary_fixture()
        for ledger in ledgers:
            ledger["input_power_w"] = 1e-12
            ledger["signed_nonport_exterior_flux_w"] = 1e-10
            ledger["material_absorption_w"] = -1e-10
        with self.assertRaisesRegex(InvalidInputError, "negative absorption"):
            _audit(entries, ledgers)

        entries, ledgers = _unitary_fixture()
        with self.assertRaisesRegex(InvalidInputError, "positive_outward"):
            audit_two_port_common_basis(
                entries,
                ledgers,
                model_instance_id="synthetic-two-port",
                phase_basis_id="synthetic-basis",
                phase_basis_frozen=True,
                nonport_flux_sign_convention="positive_inward",
                material_absorption_sign_convention="positive_absorbed",
            )

    def test_large_physical_residual_is_reported_not_promoted_to_gate(self) -> None:
        entries, ledgers = _unitary_fixture()
        for ledger in ledgers:
            ledger["signed_nonport_exterior_flux_w"] = -0.01
            ledger["accounted_power_fraction"] = 0.99
            ledger["closure_residual_fraction"] = 0.01
        result = _audit(entries, ledgers)
        self.assertFalse(result["checks"]["all_columns_close_within_tolerance"])
        self.assertFalse(result["checks"]["within_declared_diagnostic_tolerances"])
        self.assertEqual(result["status"], "diagnostic_only")

    def test_strict_evaluator_calls_audit_and_rejects_unknown_keys(self) -> None:
        entries, ledgers = _unitary_fixture()
        parameters = {
            "source_conditioned_entries": entries,
            "power_ledgers": ledgers,
            "model_instance_id": "synthetic-two-port",
            "phase_basis_id": "synthetic-frozen-basis-v1",
            "phase_basis_frozen": True,
            "nonport_flux_sign_convention": "positive_outward",
            "material_absorption_sign_convention": "positive_absorbed",
        }
        result = evaluate_two_port_common_basis(parameters)
        self.assertEqual(result["status"], "diagnostic_only")
        with self.assertRaisesRegex(InvalidInputError, "unknown"):
            evaluate_two_port_common_basis({**parameters, "physical_gate": "G1"})


if __name__ == "__main__":
    unittest.main()
