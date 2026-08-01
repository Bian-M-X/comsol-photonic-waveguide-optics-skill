"""Fail-closed arithmetic audits for two-port common-basis S matrices."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from numbers import Complex, Integral, Real
from typing import cast

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.types import JSONValue

_ENTRY_FIELDS = {
    "row",
    "column",
    "source_solution_index",
    "real",
    "imag",
    "power",
}
_LEDGER_FIELDS = {
    "source_port",
    "input_power_w",
    "reflection_power_fraction",
    "transmission_power_fraction",
    "signed_nonport_exterior_flux_w",
    "material_absorption_w",
    "accounted_power_fraction",
    "closure_residual_fraction",
}
_MATRIX_KEYS = ((1, 1), (1, 2), (2, 1), (2, 2))
_EVALUATOR_REQUIRED_FIELDS = {
    "source_conditioned_entries",
    "power_ledgers",
    "model_instance_id",
    "phase_basis_id",
    "phase_basis_frozen",
    "nonport_flux_sign_convention",
    "material_absorption_sign_convention",
}
_EVALUATOR_OPTIONAL_FIELDS = {
    "arithmetic_tolerance",
    "closure_tolerance",
    "reciprocity_tolerance",
    "passivity_tolerance",
    "unitarity_tolerance",
}


def _finite_real(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidInputError(f"{name} must be a real number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise InvalidInputError(f"{name} is outside the supported numeric range") from exc
    if not math.isfinite(result):
        raise InvalidInputError(f"{name} must be finite")
    return result


def _positive_integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise InvalidInputError(f"{name} must be an integer")
    result = int(value)
    if result <= 0:
        raise InvalidInputError(f"{name} must be positive")
    return result


def _finite_complex(name: str, value: object) -> complex:
    if isinstance(value, bool) or not isinstance(value, Complex):
        raise InvalidInputError(f"{name} must be a complex-compatible number")
    try:
        result = complex(value)
    except OverflowError as exc:
        raise InvalidInputError(f"{name} is outside the supported numeric range") from exc
    if not math.isfinite(result.real) or not math.isfinite(result.imag):
        raise InvalidInputError(f"{name} must be finite")
    return result


def _squared_magnitude(name: str, value: complex) -> float:
    magnitude = math.hypot(value.real, value.imag)
    result = magnitude * magnitude
    if not math.isfinite(result):
        raise InvalidInputError(f"{name} magnitude is too large")
    return result


def _exact_mapping(
    label: str,
    value: object,
    expected_fields: set[str],
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidInputError(f"{label} must be an object")
    actual_fields = set(value)
    missing = expected_fields - actual_fields
    unknown = actual_fields - expected_fields
    if missing or unknown:
        raise InvalidInputError(
            f"{label} fields mismatch; missing={sorted(missing, key=repr)}, "
            f"unknown={sorted(unknown, key=repr)}"
        )
    return value


def _items(label: str, value: object, expected_count: int) -> list[object]:
    if isinstance(value, (str, bytes, bytearray, Mapping)):
        raise InvalidInputError(f"{label} must be an iterable of objects")
    try:
        result = list(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise InvalidInputError(f"{label} must be iterable") from exc
    if len(result) != expected_count:
        raise InvalidInputError(f"{label} must contain exactly {expected_count} items")
    return result


def _close(left: float, right: float, tolerance: float) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def largest_singular_value_2x2(
    s11: complex,
    s12: complex,
    s21: complex,
    s22: complex,
) -> float:
    """Return ``sigma_max`` from ``S^H S`` without trace/determinant cancellation."""

    a = _finite_complex("s11", s11)
    b = _finite_complex("s12", s12)
    c = _finite_complex("s21", s21)
    d = _finite_complex("s22", s22)
    h11 = _squared_magnitude("s11", a) + _squared_magnitude("s21", c)
    h22 = _squared_magnitude("s12", b) + _squared_magnitude("s22", d)
    h12 = a.conjugate() * b + c.conjugate() * d
    if not all(math.isfinite(value) for value in (h11, h22, h12.real, h12.imag)):
        raise InvalidInputError("S^H S contains a non-finite value")
    eigenvalue_gap = math.hypot(h11 - h22, 2.0 * abs(h12))
    largest_eigenvalue = 0.5 * (h11 + h22 + eigenvalue_gap)
    if not math.isfinite(largest_eigenvalue):
        raise InvalidInputError("S^H S largest eigenvalue is non-finite")
    return math.sqrt(max(0.0, largest_eigenvalue))


def audit_two_port_common_basis(
    source_conditioned_entries: Iterable[Mapping[str, object]],
    power_ledgers: Iterable[Mapping[str, object]],
    *,
    model_instance_id: str,
    phase_basis_id: str,
    phase_basis_frozen: bool,
    nonport_flux_sign_convention: str,
    material_absorption_sign_convention: str,
    arithmetic_tolerance: float = 1e-10,
    closure_tolerance: float = 1e-3,
    reciprocity_tolerance: float = 1e-3,
    passivity_tolerance: float = 1e-6,
    unitarity_tolerance: float = 1e-3,
) -> dict[str, object]:
    """Audit one two-port, two-source diagnostic in a frozen common basis.

    Matrix entries must use exact fields ``row``, ``column``,
    ``source_solution_index``, ``real``, ``imag``, and ``power``.  Each power
    ledger must use the exact fields named by ``_LEDGER_FIELDS``.  Structural
    or arithmetic inconsistency raises :class:`InvalidInputError`.

    Physical tolerances are reported as diagnostic checks instead of being
    promoted to a verification gate.  A returned result does not establish
    broadband behavior, convergence, or full-wave validation.
    """

    if not isinstance(model_instance_id, str) or not model_instance_id.strip():
        raise InvalidInputError("model_instance_id must be a non-empty string")
    if not isinstance(phase_basis_id, str) or not phase_basis_id.strip():
        raise InvalidInputError("phase_basis_id must be a non-empty string")
    if phase_basis_frozen is not True:
        raise InvalidInputError("phase_basis_frozen must be explicitly true")
    if nonport_flux_sign_convention != "positive_outward":
        raise InvalidInputError(
            "nonport_flux_sign_convention must be exactly 'positive_outward'"
        )
    if material_absorption_sign_convention != "positive_absorbed":
        raise InvalidInputError(
            "material_absorption_sign_convention must be exactly 'positive_absorbed'"
        )

    tolerances = {
        "arithmetic": _finite_real("arithmetic_tolerance", arithmetic_tolerance),
        "closure": _finite_real("closure_tolerance", closure_tolerance),
        "reciprocity": _finite_real("reciprocity_tolerance", reciprocity_tolerance),
        "passivity": _finite_real("passivity_tolerance", passivity_tolerance),
        "unitarity": _finite_real("unitarity_tolerance", unitarity_tolerance),
    }
    if any(value < 0.0 for value in tolerances.values()):
        raise InvalidInputError("audit tolerances must be non-negative")

    entry_items = _items("source_conditioned_entries", source_conditioned_entries, 4)
    matrix: dict[tuple[int, int], dict[str, object]] = {}
    values: dict[tuple[int, int], complex] = {}
    for index, item in enumerate(entry_items):
        row_data = _exact_mapping(f"source_conditioned_entries[{index}]", item, _ENTRY_FIELDS)
        row = _positive_integer(f"entry[{index}].row", row_data["row"])
        column = _positive_integer(f"entry[{index}].column", row_data["column"])
        source_index = _positive_integer(
            f"entry[{index}].source_solution_index",
            row_data["source_solution_index"],
        )
        key = (row, column)
        if key not in _MATRIX_KEYS or key in matrix:
            raise InvalidInputError(f"invalid or duplicate two-port matrix entry {key}")
        if source_index != column:
            raise InvalidInputError(f"matrix entry {key} must come from source solution {column}")
        real = _finite_real(f"entry[{index}].real", row_data["real"])
        imag = _finite_real(f"entry[{index}].imag", row_data["imag"])
        reported_power = _finite_real(f"entry[{index}].power", row_data["power"])
        if reported_power < 0.0:
            raise InvalidInputError(f"matrix entry {key} power must be non-negative")
        value = complex(real, imag)
        recomputed_power = _squared_magnitude(f"matrix entry {key}", value)
        if not _close(reported_power, recomputed_power, tolerances["arithmetic"]):
            raise InvalidInputError(f"matrix entry {key} power does not match its complex value")
        values[key] = value
        matrix[key] = {
            "row": row,
            "column": column,
            "source_solution_index": source_index,
            "real": real,
            "imag": imag,
            "power": recomputed_power,
            "phase_rad": math.atan2(imag, real),
        }
    if set(matrix) != set(_MATRIX_KEYS):
        raise InvalidInputError("two-port matrix must contain every physical entry exactly once")

    ledger_items = _items("power_ledgers", power_ledgers, 2)
    columns: dict[int, dict[str, object]] = {}
    for index, item in enumerate(ledger_items):
        row_data = _exact_mapping(f"power_ledgers[{index}]", item, _LEDGER_FIELDS)
        source = _positive_integer(f"power_ledgers[{index}].source_port", row_data["source_port"])
        if source not in (1, 2) or source in columns:
            raise InvalidInputError(f"invalid or duplicate power ledger source {source}")
        numeric = {
            field: _finite_real(f"power_ledgers[{index}].{field}", row_data[field])
            for field in _LEDGER_FIELDS - {"source_port"}
        }
        input_power = numeric["input_power_w"]
        if input_power <= 0.0:
            raise InvalidInputError(f"power ledger {source} input_power_w must be positive")
        reflection = float(matrix[(source, source)]["power"])
        transmission = float(matrix[(3 - source, source)]["power"])
        if numeric["reflection_power_fraction"] < 0.0 or numeric["transmission_power_fraction"] < 0.0:
            raise InvalidInputError(f"power ledger {source} modal powers must be non-negative")
        if not _close(numeric["reflection_power_fraction"], reflection, tolerances["arithmetic"]):
            raise InvalidInputError(f"power ledger {source} reflection does not match S{source}{source}")
        if not _close(numeric["transmission_power_fraction"], transmission, tolerances["arithmetic"]):
            raise InvalidInputError(f"power ledger {source} transmission does not match its S column")
        minimum_absorption = -tolerances["arithmetic"] * input_power
        if numeric["material_absorption_w"] < minimum_absorption:
            raise InvalidInputError(f"power ledger {source} has nonphysical negative absorption")
        material_absorption = max(0.0, numeric["material_absorption_w"])
        modal_fraction = reflection + transmission
        accounted = modal_fraction + (
            numeric["signed_nonport_exterior_flux_w"] + material_absorption
        ) / input_power
        closure = 1.0 - accounted
        if not math.isfinite(accounted) or not math.isfinite(closure):
            raise InvalidInputError(f"power ledger {source} closure arithmetic is non-finite")
        if not _close(numeric["accounted_power_fraction"], accounted, tolerances["arithmetic"]):
            raise InvalidInputError(f"power ledger {source} accounted fraction is inconsistent")
        if not _close(numeric["closure_residual_fraction"], closure, tolerances["arithmetic"]):
            raise InvalidInputError(f"power ledger {source} closure residual is inconsistent")
        columns[source] = {
            "source_port": source,
            "input_power_w": input_power,
            "reflection_power_fraction": reflection,
            "transmission_power_fraction": transmission,
            "modal_output_power_fraction": modal_fraction,
            "signed_nonport_exterior_flux_w": numeric["signed_nonport_exterior_flux_w"],
            "material_absorption_w": material_absorption,
            "accounted_power_fraction": accounted,
            "closure_residual_fraction": closure,
            "closure_within_tolerance": abs(closure) <= tolerances["closure"],
        }
    if set(columns) != {1, 2}:
        raise InvalidInputError("power ledgers must contain source ports 1 and 2 exactly once")

    s11, s12, s21, s22 = (values[key] for key in _MATRIX_KEYS)
    cross_scale = max(abs(s12), abs(s21), 1e-300)
    reciprocity_error = abs(s21 - s12) / cross_scale
    sigma_max = largest_singular_value_2x2(s11, s12, s21, s22)
    diagonal_1 = _squared_magnitude("S column 1", s11) + _squared_magnitude("S column 1", s21) - 1.0
    diagonal_2 = _squared_magnitude("S column 2", s12) + _squared_magnitude("S column 2", s22) - 1.0
    off_diagonal = s11.conjugate() * s12 + s21.conjugate() * s22
    if not math.isfinite(off_diagonal.real) or not math.isfinite(off_diagonal.imag):
        raise InvalidInputError("unitarity calculation is non-finite")
    unitarity_frobenius = math.hypot(diagonal_1, diagonal_2, math.sqrt(2.0) * abs(off_diagonal))

    checks = {
        "source_column_mapping_consistent": True,
        "complex_power_consistent": True,
        "power_ledger_arithmetic_consistent": True,
        "all_columns_close_within_tolerance": all(
            bool(columns[source]["closure_within_tolerance"]) for source in (1, 2)
        ),
        "reciprocity_within_tolerance": reciprocity_error <= tolerances["reciprocity"],
        "passivity_within_tolerance": sigma_max <= 1.0 + tolerances["passivity"],
        "unitarity_within_tolerance": unitarity_frobenius <= tolerances["unitarity"],
    }
    checks["within_declared_diagnostic_tolerances"] = all(checks.values())

    return {
        "schema_version": "1.0",
        "status": "diagnostic_only",
        "claim_level": "same_model_common_basis_two_port_diagnostic",
        "model_instance_id": model_instance_id.strip(),
        "phase_basis": {
            "id": phase_basis_id.strip(),
            "frozen": True,
            "evidence_level": "caller_declared",
        },
        "power_sign_conventions": {
            "signed_nonport_exterior_flux_w": "positive_outward",
            "material_absorption_w": "positive_absorbed",
        },
        "matrix": [matrix[key] for key in _MATRIX_KEYS],
        "columns": [columns[1], columns[2]],
        "metrics": {
            "largest_singular_value": sigma_max,
            "largest_singular_value_method": "hermitian_2x2_hypot",
            "complex_reciprocity_relative_error": reciprocity_error,
            "unitarity_frobenius": unitarity_frobenius,
        },
        "tolerances": tolerances,
        "checks": checks,
        "limitations": [
            "diagnostic_not_a_physical_verification_gate",
            "no_independent_proof_of_common_port_mode_gauge",
            "single_two_port_snapshot_only",
            "no_broadband_phase_or_group_delay_claim",
            "no_mesh_boundary_or_material_convergence_claim",
        ],
    }


def evaluate_two_port_common_basis(
    parameters: Mapping[str, JSONValue],
) -> dict[str, JSONValue]:
    """Run the two-port audit from a strict JSON-style parameter object."""

    if not isinstance(parameters, Mapping):
        raise InvalidInputError("two-port recipe parameters must be an object")
    actual_fields = set(parameters)
    values = _exact_mapping(
        "two-port recipe parameters",
        parameters,
        _EVALUATOR_REQUIRED_FIELDS | (actual_fields & _EVALUATOR_OPTIONAL_FIELDS),
    )
    missing = _EVALUATOR_REQUIRED_FIELDS - set(values)
    unknown = set(values) - _EVALUATOR_REQUIRED_FIELDS - _EVALUATOR_OPTIONAL_FIELDS
    if missing or unknown:
        raise InvalidInputError(
            f"two-port recipe parameter fields mismatch; missing={sorted(missing, key=repr)}, "
            f"unknown={sorted(unknown, key=repr)}"
        )
    result = audit_two_port_common_basis(
        values["source_conditioned_entries"],  # type: ignore[arg-type]
        values["power_ledgers"],  # type: ignore[arg-type]
        model_instance_id=values["model_instance_id"],  # type: ignore[arg-type]
        phase_basis_id=values["phase_basis_id"],  # type: ignore[arg-type]
        phase_basis_frozen=values["phase_basis_frozen"],  # type: ignore[arg-type]
        nonport_flux_sign_convention=values["nonport_flux_sign_convention"],  # type: ignore[arg-type]
        material_absorption_sign_convention=values["material_absorption_sign_convention"],  # type: ignore[arg-type]
        arithmetic_tolerance=values.get("arithmetic_tolerance", 1e-10),  # type: ignore[arg-type]
        closure_tolerance=values.get("closure_tolerance", 1e-3),  # type: ignore[arg-type]
        reciprocity_tolerance=values.get("reciprocity_tolerance", 1e-3),  # type: ignore[arg-type]
        passivity_tolerance=values.get("passivity_tolerance", 1e-6),  # type: ignore[arg-type]
        unitarity_tolerance=values.get("unitarity_tolerance", 1e-3),  # type: ignore[arg-type]
    )
    return cast(dict[str, JSONValue], result)
