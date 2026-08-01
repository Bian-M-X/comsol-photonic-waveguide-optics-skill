"""Bulk optical-material recipes with explicit applicability boundaries.

These helpers evaluate published bulk-material dispersion relations.  They do
not predict a waveguide mode, deposited-film properties, or foundry process
data.  Inputs are expressed in the units named by the function arguments and
outputs contain only JSON-safe values.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real
from typing import cast

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.types import JSONValue


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


def _parameters(
    value: object,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise InvalidInputError("recipe parameters must be an object")
    allowed = required | (optional or set())
    actual = set(value)
    missing = required - actual
    unknown = actual - allowed
    if missing or unknown:
        raise InvalidInputError(
            f"recipe parameter fields mismatch; missing={sorted(missing, key=repr)}, "
            f"unknown={sorted(unknown, key=repr)}"
        )
    return value


def li_silicon_1980(
    wavelength_um: float,
    temperature_k: float = 293.15,
) -> dict[str, object]:
    """Evaluate the Li (1980) crystalline-silicon bulk-index relation.

    ``wavelength_um`` is vacuum wavelength in micrometres and
    ``temperature_k`` is absolute temperature in kelvin.  The declared source
    range is 1.2--14 micrometres and 100--750 K.  The analytic derivative is
    with respect to wavelength measured in micrometres.
    """

    wavelength = _finite_real("wavelength_um", wavelength_um)
    temperature = _finite_real("temperature_k", temperature_k)
    if not 1.2 <= wavelength <= 14.0:
        raise InvalidInputError("wavelength_um is outside the Li 1980 range [1.2, 14.0]")
    if not 100.0 <= temperature <= 750.0:
        raise InvalidInputError("temperature_k is outside the Li 1980 range [100.0, 750.0]")

    if temperature < 293.0:
        relative_expansion = (
            -0.021e-2
            - 4.149e-7 * temperature
            - 4.620e-10 * temperature**2
            + 1.482e-11 * temperature**3
        )
        expansion_branch = "100_to_below_293_K"
    else:
        relative_expansion = (
            -0.071e-2
            + 1.887e-6 * temperature
            + 1.934e-9 * temperature**2
            - 4.544e-13 * temperature**3
        )
        expansion_branch = "293_K_and_above"

    long_wavelength_permittivity = (
        11.4445
        + 2.7739e-4 * temperature
        + 1.7050e-6 * temperature**2
        - 8.1347e-10 * temperature**3
    )
    dispersion_strength = math.exp(-3.0 * relative_expansion) * (
        0.8948
        + 4.3977e-4 * temperature
        + 7.3835e-8 * temperature**2
    )
    relative_permittivity = long_wavelength_permittivity + dispersion_strength / wavelength**2
    refractive_index = math.sqrt(relative_permittivity)
    derivative = -dispersion_strength / (refractive_index * wavelength**3)
    bulk_group_index = refractive_index - wavelength * derivative

    values = (
        relative_expansion,
        long_wavelength_permittivity,
        dispersion_strength,
        relative_permittivity,
        refractive_index,
        derivative,
        bulk_group_index,
    )
    if not all(math.isfinite(value) for value in values):
        raise InvalidInputError("Li 1980 evaluation produced a non-finite value")

    return {
        "schema_version": "1.0",
        "material": "crystalline_silicon",
        "model": "Li1980_equation_22",
        "source_doi": "10.1063/1.555624",
        "wavelength_um": wavelength,
        "temperature_K": temperature,
        "refractive_index": refractive_index,
        "relative_permittivity": relative_permittivity,
        "dn_dlambda_per_um": derivative,
        "bulk_group_index": bulk_group_index,
        "thermal_expansion_branch": expansion_branch,
        "relative_expansion_from_293_K": relative_expansion,
        "validity": {
            "wavelength_min_um": 1.2,
            "wavelength_max_um": 14.0,
            "temperature_min_K": 100.0,
            "temperature_max_K": 750.0,
        },
        "claim": {
            "level": "bulk_material_formula",
            "is_waveguide_modal_result": False,
            "statement": "Bulk crystalline-silicon dispersion only; not a waveguide modal index or process model.",
        },
    }


def malitson_fused_silica_1965(wavelength_um: float) -> dict[str, object]:
    """Evaluate the Malitson (1965) bulk fused-silica Sellmeier relation.

    ``wavelength_um`` is vacuum wavelength in micrometres.  The relation is
    restricted to its declared 0.21--3.71 micrometre range.  It is exposed as
    a fused-silica surrogate and must not be presented as deposited oxide,
    stressed film, or foundry metrology.
    """

    wavelength = _finite_real("wavelength_um", wavelength_um)
    if not 0.21 <= wavelength <= 3.71:
        raise InvalidInputError("wavelength_um is outside the Malitson 1965 range [0.21, 3.71]")

    coefficients = (
        (0.6961663, 0.0684043),
        (0.4079426, 0.1162414),
        (0.8974794, 9.896161),
    )
    wavelength_squared = wavelength**2
    relative_permittivity = 1.0 + sum(
        strength * wavelength_squared / (wavelength_squared - resonance_um**2)
        for strength, resonance_um in coefficients
    )
    refractive_index = math.sqrt(relative_permittivity)
    derivative = -sum(
        strength
        * wavelength
        * resonance_um**2
        / (wavelength_squared - resonance_um**2) ** 2
        for strength, resonance_um in coefficients
    ) / refractive_index
    bulk_group_index = refractive_index - wavelength * derivative

    values = (relative_permittivity, refractive_index, derivative, bulk_group_index)
    if not all(math.isfinite(value) for value in values):
        raise InvalidInputError("Malitson 1965 evaluation produced a non-finite value")

    return {
        "schema_version": "1.0",
        "material": "fused_silica",
        "model": "Malitson1965_equation_2",
        "source_doi": "10.1364/JOSA.55.001205",
        "wavelength_um": wavelength,
        "temperature_K": None,
        "refractive_index": refractive_index,
        "relative_permittivity": relative_permittivity,
        "dn_dlambda_per_um": derivative,
        "bulk_group_index": bulk_group_index,
        "validity": {
            "wavelength_min_um": 0.21,
            "wavelength_max_um": 3.71,
            "temperature_model": "not_in_relation",
        },
        "claim": {
            "level": "bulk_material_surrogate_formula",
            "is_waveguide_modal_result": False,
            "is_deposited_or_foundry_oxide_metrology": False,
            "statement": (
                "Bulk fused-silica surrogate only; not deposited oxide, stressed film, "
                "doped oxide, or foundry metrology."
            ),
        },
    }


def evaluate_li_silicon_1980(parameters: Mapping[str, JSONValue]) -> dict[str, JSONValue]:
    """Evaluate the Li recipe from a strict JSON-style parameter object."""

    values = _parameters(
        parameters,
        required={"wavelength_um"},
        optional={"temperature_k"},
    )
    result = li_silicon_1980(
        values["wavelength_um"],  # type: ignore[arg-type]
        values.get("temperature_k", 293.15),  # type: ignore[arg-type]
    )
    return cast(dict[str, JSONValue], result)


def evaluate_malitson_fused_silica_1965(
    parameters: Mapping[str, JSONValue],
) -> dict[str, JSONValue]:
    """Evaluate the Malitson recipe from a strict parameter object."""

    values = _parameters(parameters, required={"wavelength_um"})
    result = malitson_fused_silica_1965(values["wavelength_um"])  # type: ignore[arg-type]
    return cast(dict[str, JSONValue], result)
