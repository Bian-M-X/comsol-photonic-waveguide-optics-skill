"""Solver-independent fabrication diagnostics; no optical or yield acceptance.

These original numerical helpers do not implement a lithography model, BOSON,
PRISM, a robust optimizer, or an uncertainty distribution.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from photonic_workflow.exceptions import InvalidInputError


def _real_samples(value: Any, name: str) -> np.ndarray:
    """Reject booleans before NumPy can coerce mixed lists into numeric arrays."""
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in "iuf":
            raise InvalidInputError(f"{name} must contain finite real numbers, not booleans")
        # Numeric ndarray dtypes already exclude typed booleans. Avoid an
        # object allocation and Python loop over potentially large wafer maps.
        if not isinstance(value, np.ndarray):
            objects = np.asarray(value, dtype=object)
            if any(isinstance(item, (bool, np.bool_)) for item in objects.flat):
                raise InvalidInputError(f"{name} must contain finite real numbers, not booleans")
        with np.errstate(over="ignore", invalid="ignore"):
            result = raw.astype(float)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidInputError(f"{name} must be a rectangular array of finite real numbers") from exc
    if not result.size or not np.all(np.isfinite(result)):
        raise InvalidInputError(f"{name} must be nonempty and finite in float64")
    return result


def axial_scenarios(dimension: int) -> np.ndarray:
    """Return nominal, +e1, -e1, ... in normalized uncertainty coordinates.

    The shape is (2*dimension+1, dimension), with integer dimension in 1..64.
    This finite design of experiments screens individual axes only. It is not
    probabilistic quadrature or a global worst-case search: mixed interactions
    such as z1*z2 vanish on every returned row.
    """
    if (isinstance(dimension, (bool, np.bool_))
            or not isinstance(dimension, (int, np.integer)) or not 1 <= dimension <= 64):
        raise InvalidInputError("dimension must be an integer in 1..64, not a boolean")
    result = np.zeros((2 * dimension + 1, dimension))
    axes = np.eye(dimension)
    result[1::2] = axes
    result[2::2] = -axes
    return result


def weighted_pattern_loss(
    wafer: Any,
    target: Any,
    sensitivity: Any,
    *,
    quadrature_weights: Any = None,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Return (loss, derivative_wrt_wafer, Gamma) for ONE wafer scenario.

    wafer and target are identical-shape, nonempty, finite real arrays in [0,1].
    sensitivity has their shape and contains finite real values. With fixed
    sensitivity, Gamma = 0.5 + abs(sensitivity)/max(abs(sensitivity)); all-zero
    sensitivity instead gives Gamma=1. The loss is the normalized weighted mean
    of (Gamma*(wafer-target))**4. Its derivative is
    4*normalized_weights*Gamma**4*(wafer-target)**3. Gamma lies INSIDE the fourth
    power; the derivative holds sensitivity, target and weights fixed.

    Optional nonnegative quadrature weights must have the same shape and a
    positive total. They are normalized after scaling to avoid sum overflow.
    Without weights, equal sample weights apply; this is not a general FE nodal
    area integral. Supply appropriate cell/area/volume weights for that use.

    This PRISM-inspired diagnostic uses an explicit max normalization and mean
    rather than an unnormalized sum; it is not a paper replication. Evaluate each
    scenario separately BEFORE aggregating losses. Averaging wafer images first
    can cancel opposing errors. No solver, mask gradient or yield is computed.
    """
    actual = _real_samples(wafer, "wafer")
    desired = _real_samples(target, "target")
    gradient_weight = _real_samples(sensitivity, "sensitivity")
    if actual.shape != desired.shape or actual.shape != gradient_weight.shape:
        raise InvalidInputError("wafer, target and sensitivity must have identical shapes")
    if np.any((actual < 0) | (actual > 1)) or np.any((desired < 0) | (desired > 1)):
        raise InvalidInputError("wafer and target must be in [0, 1]; values are not clipped")
    if quadrature_weights is None:
        normalized = np.full(actual.shape, 1 / actual.size)
    else:
        supplied = _real_samples(quadrature_weights, "quadrature_weights")
        if supplied.shape != actual.shape or np.any(supplied < 0) or not np.any(supplied > 0):
            raise InvalidInputError("quadrature weights need the sample shape, nonnegative values and positive total")
        scaled = supplied / np.max(supplied)
        normalized = scaled / np.sum(scaled)
    magnitude = np.abs(gradient_weight)
    maximum = float(np.max(magnitude))
    gamma = np.ones(actual.shape) if maximum == 0 else 0.5 + magnitude / maximum
    error = actual - desired
    loss = float(np.sum(normalized * (gamma * error)**4))
    derivative = 4 * normalized * gamma**4 * error**3
    return loss, derivative, gamma
