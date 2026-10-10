"""Small, solver-independent inverse-design primitives (no physics acceptance)."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np

from photonic_workflow.exceptions import InvalidInputError


def _real_array(value: Any, name: str) -> np.ndarray:
    raw = np.asarray(value)
    if raw.dtype.kind not in "iuf" or not np.all(np.isfinite(raw)):
        raise InvalidInputError(f"{name} must contain finite real numbers, not booleans")
    return raw.astype(float)


def _positive(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise InvalidInputError(f"{name} must be finite and positive")
    return float(value)


def tanh_projection(density: Any, beta: float, eta: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Return projected density and its pointwise derivative; 1 denotes solid."""
    rho = _real_array(density, "density")
    beta = _positive(beta, "beta")
    if beta > 512 or isinstance(eta, bool) or not math.isfinite(eta) or not 0 < eta < 1:
        raise InvalidInputError("require beta <= 512 and 0 < eta < 1")
    if np.any((rho < 0) | (rho > 1)):
        raise InvalidInputError("density must be in [0, 1]; do not silently clip gradients")
    denominator = np.tanh(beta * eta) + np.tanh(beta * (1 - eta))
    t = np.tanh(beta * (rho - eta))
    return (np.tanh(beta * eta) + t) / denominator, beta * (1 - t * t) / denominator


def density_binarization_metrics(density: Any, *, weights: Any = None) -> dict[str, Any]:
    """Diagnose physical density; supplied weights may represent cell area/volume.

    These are field statistics, not optical acceptance or fabrication rules.
    Uniform weighting is meaningful for equal-volume samples, not general FE nodes.
    """
    rho = _real_array(density, "density")
    if not rho.size or np.any((rho < 0) | (rho > 1)):
        raise InvalidInputError("density must be nonempty and in [0, 1]")
    if weights is None:
        normalized = np.full(rho.shape, 1 / rho.size)
    else:
        supplied = _real_array(weights, "weights")
        if supplied.shape != rho.shape or np.any(supplied < 0) or not np.any(supplied > 0):
            raise InvalidInputError("weights need the density shape, nonnegative values and positive total")
        scaled = supplied / np.max(supplied)
        normalized = scaled / np.sum(scaled)

    def mean(value):
        return float(np.sum(normalized * value))

    grayness = mean(4 * rho * (1 - rho))
    discrepancy = mean(np.minimum(rho, 1 - rho))
    return {
        "sample_count": int(rho.size),
        "weighting": "uniform_samples" if weights is None else "supplied_normalized_weights",
        "density_range": [float(np.min(rho)), float(np.max(rho))],
        "mean_density": mean(rho),
        "grayness": grayness,
        "gray_fraction_10_90": mean((rho > 0.1) & (rho < 0.9)),
        "gray_fraction_01_99": mean((rho > 0.01) & (rho < 0.99)),
        "solid_fraction_above_half": mean(rho > 0.5),
        "mean_absolute_half_threshold_discrepancy": discrepancy,
        "discrepancy_bounds_from_grayness": [grayness / 4, grayness / 2],
        "scope": "Physical-density field statistics at threshold 0.5; no optical-error or DRC bound",
    }


class ConicFilter:
    """Normalized, truncated conic filter on a uniform 2-D grid and exact VJP.

    Radius is in pixels. Boundary normalization preserves a constant density;
    its transpose is NOT another normalized forward filtering operation.
    This filter is not the Helmholtz PDE filter and is not a minimum-size DRC.
    """

    def __init__(self, shape: tuple[int, int], radius: float) -> None:
        if len(shape) != 2 or any(type(n) is not int or n < 1 for n in shape) or math.prod(shape) > 1_000_000:
            raise InvalidInputError("filter shape must have 1..1000000 pixels in two dimensions")
        radius = _positive(radius, "radius")
        if radius > 32:
            raise InvalidInputError("radius above 32 pixels requires a sparse/PDE/FFT implementation")
        reach = math.ceil(radius) - 1
        stencil_bound = min(2 * reach + 1, 2 * shape[0] - 1) * min(2 * reach + 1, 2 * shape[1] - 1)
        if math.prod(shape) * stencil_bound > 100_000_000:
            raise InvalidInputError("filter work exceeds this reference implementation; use sparse/PDE/FFT filtering")
        self.shape = shape
        self.stencil: list[tuple[tuple[slice, slice], tuple[slice, slice], float]] = []
        self.normalization = np.zeros(shape)
        for dy in range(-min(reach, shape[0] - 1), min(reach, shape[0] - 1) + 1):
            for dx in range(-min(reach, shape[1] - 1), min(reach, shape[1] - 1) + 1):
                weight = max(0.0, radius - math.hypot(dy, dx))
                if weight == 0:
                    continue
                dest = (slice(max(0, dy), min(shape[0], shape[0] + dy)),
                        slice(max(0, dx), min(shape[1], shape[1] + dx)))
                source = (slice(max(0, -dy), min(shape[0], shape[0] - dy)),
                          slice(max(0, -dx), min(shape[1], shape[1] - dx)))
                self.stencil.append((dest, source, weight))
                self.normalization[dest] += weight

    def _check(self, value: Any) -> np.ndarray:
        array = _real_array(value, "filter input")
        if array.shape != self.shape:
            raise InvalidInputError("filter input shape mismatch")
        return array

    def forward(self, density: Any) -> np.ndarray:
        rho = self._check(density)
        result = np.zeros(self.shape)
        for dest, source, weight in self.stencil:
            result[dest] += weight * rho[source]
        return result / self.normalization

    def vjp(self, cotangent: Any) -> np.ndarray:
        scaled = self._check(cotangent) / self.normalization
        result = np.zeros(self.shape)
        for dest, source, weight in self.stencil:
            result[source] += weight * scaled[dest]
        return result


def smooth_worst_case(losses: Any, temperature: float) -> tuple[float, np.ndarray]:
    """Unnormalized log-sum-exp: max(loss) <= result <= max(loss)+tau*log(N)."""
    values = _real_array(losses, "losses")
    if values.ndim != 1 or values.size == 0:
        raise InvalidInputError("losses must be a nonempty vector with comparable scales")
    tau = _positive(temperature, "temperature")
    maximum = float(values.max())
    weights = np.exp((values - maximum) / tau)
    weights /= weights.sum()
    result = maximum + tau * math.log(float(np.exp((values - maximum) / tau).sum()))
    if not math.isfinite(result):
        raise InvalidInputError("aggregated loss overflow")
    return result, weights


def complex_target_metrics(actual: Any, target: Any) -> dict[str, Any]:
    """Compare a fixed-basis transmission block, allowing only one global phase.

    Shape overlap is amplitude-scale invariant; column throughput and an
    amplitude-sensitive error are returned separately. No phase is fitted per
    port, and the block need not be a complete scattering matrix.
    """
    a, t = np.asarray(actual, dtype=complex), np.asarray(target, dtype=complex)
    if a.ndim != 2 or a.shape != t.shape or min(a.shape) < 1:
        raise InvalidInputError("actual and target must be nonempty matrices of equal shape")
    if not np.all(np.isfinite(a)) or not np.all(np.isfinite(t)):
        raise InvalidInputError("complex matrices must be finite")
    # Scale first to avoid overflow in inner products.
    scale = max(float(np.abs(a).max()), float(np.abs(t).max()))
    if scale == 0 or np.linalg.norm(t / scale) == 0:
        raise InvalidInputError("target cannot be zero")
    an, tn = a / scale, t / scale
    at = np.vdot(tn, an)
    aa, tt = float(np.vdot(an, an).real), float(np.vdot(tn, tn).real)
    if tt == 0 or (aa > 0 and aa * tt == 0):
        raise InvalidInputError("matrix scales are too different; rescale the comparison")
    phase = at / abs(at) if abs(at) else 1.0 + 0j
    overlap = float(abs(at) ** 2 / (aa * tt)) if aa else 0.0
    with np.errstate(over="ignore"):
        powers = np.sum(np.abs(a) ** 2, axis=0)
    if not np.all(np.isfinite(powers)):
        raise InvalidInputError("column power overflow")
    return {
        "shape_overlap": min(1.0, max(0.0, overlap)),
        "global_phase_rad": float(np.angle(phase)),
        "relative_error_after_global_phase": float(np.linalg.norm(an - phase * tn) / math.sqrt(tt)),
        "column_power": powers.tolist(),
        "claim_boundary": "fixed-basis block similarity, not quantum process fidelity or total power closure",
    }


def directional_gradient_check(
    objective: Callable[[np.ndarray], float],
    point: Any,
    gradient: Any,
    direction: Any,
    steps: tuple[float, ...] = (1e-2, 1e-3, 1e-4),
    *,
    rtol: float = 1e-3,
    atol: float = 1e-8,
) -> dict[str, Any]:
    """Compare real directional derivatives at >=2 steps; all calls are explicit.

    Caller owns feasibility, frozen mesh, objective convention and solver cost.
    Requiring two passing steps avoids accepting one accidentally matching step.
    This is a sampled derivative check, not proof of a full Maxwell adjoint.
    """
    x, g, v = (_real_array(value, name) for value, name in
               ((point, "point"), (gradient, "gradient"), (direction, "direction")))
    if x.size == 0 or x.shape != g.shape or x.shape != v.shape:
        raise InvalidInputError("point, gradient and direction must have the same nonempty shape")
    norm = float(np.linalg.norm(v))
    if not math.isfinite(norm) or norm == 0:
        raise InvalidInputError("direction must have finite nonzero norm")
    v = v / norm
    if len(steps) < 2 or len(set(steps)) != len(steps):
        raise InvalidInputError("use at least two distinct finite-difference steps")
    _positive(rtol, "rtol")
    _positive(atol, "atol")
    analytic = float(np.sum(g * v))
    rows = []
    for step in steps:
        h = _positive(step, "step")
        plus, minus = float(objective(x + h * v)), float(objective(x - h * v))
        finite_difference = (plus - minus) / (2 * h)
        if not all(math.isfinite(value) for value in (plus, minus, finite_difference, analytic)):
            raise InvalidInputError("gradient-check objective/derivative must be finite")
        error = abs(finite_difference - analytic)
        rows.append({"step": h, "finite_difference": finite_difference, "absolute_error": error,
                     "passed": error <= atol + rtol * max(abs(analytic), abs(finite_difference))})
    return {"passed": sum(row["passed"] for row in rows) >= 2,
            "analytic_directional_derivative": analytic, "evaluations": 2 * len(steps), "rows": rows}


def compare_error_intervals(
    candidate_loss: float, baseline_loss: float, candidate_error: float, baseline_error: float,
    minimum_improvement: float = 0.0,
) -> dict[str, Any]:
    """Conservative ranking conditional on supplied absolute error bounds."""
    values = _real_array([candidate_loss, baseline_loss, candidate_error, baseline_error,
                          minimum_improvement], "interval inputs")
    if np.any(values[2:] < 0):
        raise InvalidInputError("errors and minimum improvement must be nonnegative")
    improvement = float(values[1] - values[0])
    uncertainty = float(values[2] + values[3])
    if not all(math.isfinite(v) for v in (improvement, uncertainty,
                                         improvement - uncertainty, improvement + uncertainty)):
        raise InvalidInputError("error interval overflow; rescale the objective")
    return {
        "observed_improvement": improvement,
        "lower_improvement_bound": improvement - uncertainty,
        "upper_improvement_bound": improvement + uncertainty,
        "decision": "improvement_resolved" if improvement - uncertainty > values[4] else "unresolved",
        "claim_boundary": "conditional on valid error bounds; empirical discrepancies are not certified bounds",
    }


def allocate_error_budget(
    sensitivities: Any, cost_factors: Any, total_error: float, cost_exponent: float = 2.0,
) -> dict[str, Any]:
    """Minimize sum(a_i/e_i**p) subject to sum(L_i*e_i) <= E, L_i,a_i>0.

    A conditional convex allocation, not a solver error estimator. L must bound
    the final task's sensitivity throughout the admissible perturbation region;
    pilot-fitted costs and point derivatives only give a heuristic allocation.
    """
    sensitivity, cost = _real_array(sensitivities, "sensitivities"), _real_array(cost_factors, "cost_factors")
    if sensitivity.ndim != 1 or sensitivity.size == 0 or sensitivity.shape != cost.shape:
        raise InvalidInputError("sensitivities and cost_factors must be matching nonempty vectors")
    if np.any(sensitivity <= 0) or np.any(cost <= 0):
        raise InvalidInputError("sensitivities and cost factors must be strictly positive")
    target, exponent = _positive(total_error, "total_error"), _positive(cost_exponent, "cost_exponent")
    log_weights = (np.log(cost) - np.log(sensitivity)) / (exponent + 1)
    weights = np.exp(log_weights - log_weights.max())
    denominator = float(np.dot(sensitivity, weights))
    if not math.isfinite(denominator) or denominator <= 0:
        raise InvalidInputError("ill-scaled allocation; rescale task and component units")
    errors = (target / denominator) * weights
    if not np.all(np.isfinite(errors)) or np.any(errors <= 0):
        raise InvalidInputError("ill-scaled error allocation")
    return {"component_errors": errors.tolist(), "weighted_total": float(np.dot(sensitivity, errors)),
            "cost_exponent": exponent,
            "claim_boundary": "optimal only for the declared separable power-law cost and valid sensitivity bounds"}
