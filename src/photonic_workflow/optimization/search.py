"""Bounded single-fidelity candidate suggestions; never launches a solver.

NumPy-only Matérn-5/2 GP expected improvement with a mixed local/global pool.
This is deliberately a small reference proposer, not TuRBO, qMFKG, or an adjoint.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

import numpy as np

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import OptimizationSpec, OptimizationTrial, Validity

ALGORITHM_VERSION = "mixed-gp-ei-v1"


def spec_fingerprint(spec: OptimizationSpec) -> str:
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise InvalidInputError(f"{name} must be a finite number")
    return float(value)


def _name(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        raise InvalidInputError("names must be identifiers of at most 64 ASCII characters")
    return value


def _configuration(
    spec: OptimizationSpec,
) -> tuple[list[str], np.ndarray, str, float, list[tuple[str, float, float]], int]:
    if spec.validity in (Validity.INVALID, Validity.EXPIRED, Validity.OUT_OF_ENVELOPE):
        raise InvalidInputError("invalid/expired/out-of-envelope specification cannot propose candidates")
    if not 1 <= len(spec.variables) <= 20 or not 2 <= spec.evaluation_budget <= 512:
        raise InvalidInputError("suggest supports 1..20 continuous variables and a total budget of 2..512 trials")
    if spec.random_seed is None or isinstance(spec.random_seed, bool) or not 0 <= spec.random_seed < 2**32:
        raise InvalidInputError("suggest requires an explicit random_seed in [0, 2**32)")
    if spec.failure_penalty is not None:
        raise InvalidInputError("suggest excludes failed solves; it does not train on invented failure penalties")
    names, bounds = [], []
    for variable in spec.variables:
        if set(variable) != {"name", "lower", "upper", "unit"}:
            raise InvalidInputError("suggest variable requires exactly name, lower, upper, unit")
        name = _name(variable["name"])
        lo, hi = _number(variable["lower"], name), _number(variable["upper"], name)
        if lo >= hi or not math.isfinite(hi - lo):
            raise InvalidInputError("variable lower must be below upper with a finite range")
        if not isinstance(variable["unit"], str) or not variable["unit"].strip():
            raise InvalidInputError("each variable needs an explicit unit, including '1' for dimensionless")
        names.append(name)
        bounds.append((lo, hi))
    if len(set(names)) != len(names):
        raise InvalidInputError("duplicate variable names")
    if len(spec.objectives) != 1 or set(spec.objectives[0]) != {"name", "sense"}:
        raise InvalidInputError("suggest requires one objective with exactly name and sense")
    objective = _name(spec.objectives[0]["name"])
    sense = spec.objectives[0]["sense"]
    if sense not in ("minimize", "maximize"):
        raise InvalidInputError("objective sense must be minimize or maximize")
    constraints = []
    for constraint in spec.constraints:
        if set(constraint) != {"name", "upper", "scale"}:
            raise InvalidInputError("suggest constraint requires exactly name, upper, scale; residual <= upper")
        name = _name(constraint["name"])
        upper, scale = _number(constraint["upper"], name), _number(constraint["scale"], name)
        if scale <= 0:
            raise InvalidInputError("constraint scale must be positive")
        constraints.append((name, upper, scale))
    if len(constraints) > 8 or len({row[0] for row in constraints}) != len(constraints):
        raise InvalidInputError("at most eight uniquely named constraints are supported")
    reserve = spec.promotion_rule.get("validation_reserve")
    if type(reserve) is not int or not 1 <= reserve < spec.evaluation_budget:
        raise InvalidInputError("promotion_rule.validation_reserve must be an integer >=1 below the total budget")
    return names, np.asarray(bounds), objective, 1.0 if sense == "minimize" else -1.0, constraints, reserve


def _lhs(count: int, dimension: int, rng: np.random.Generator) -> np.ndarray:
    return np.column_stack([(rng.permutation(count) + rng.random(count)) / count for _ in range(dimension)])


def _distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Avoid allocating a (pool, observations, dimensions) tensor.
    return np.maximum(np.sum(a * a, axis=1)[:, None] + np.sum(b * b, axis=1)[None, :] - 2 * a @ b.T, 0)


def _kernel(distance_squared: np.ndarray, length: float) -> np.ndarray:
    r = np.sqrt(5 * distance_squared) / length
    return (1 + r + r * r / 3) * np.exp(-r)


def _posterior(x: np.ndarray, y: np.ndarray, pool: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # Normalize before summing/squaring; finite raw values can still overflow std().
    magnitude = max(float(np.abs(y).max()), 1e-10)
    unit = y / magnitude
    mean = float(unit.mean())
    scale = max(float(unit.std()), 1e-10 / magnitude)
    normalized = (unit - mean) / scale
    distance = _distance(x, x)
    winner = None
    for length in (0.08, 0.2, 0.5, 1.0):
        matrix = _kernel(distance, length) + np.eye(len(x)) * 1e-6
        try:
            chol = np.linalg.cholesky(matrix)
            alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, normalized))
        except np.linalg.LinAlgError:
            continue
        likelihood = 0.5 * float(normalized @ alpha) + float(np.log(np.diag(chol)).sum())
        if winner is None or likelihood < winner[0]:
            winner = likelihood, length, chol, alpha
    if winner is None:
        raise InvalidInputError("GP factorization failed; inspect duplicate/noisy observations")
    _, length, chol, alpha = winner
    cross = _kernel(_distance(x, pool), length)
    solved = np.linalg.solve(chol, cross)
    variance = np.maximum(1 - np.sum(solved * solved, axis=0), 1e-12)
    with np.errstate(over="ignore", invalid="ignore"):
        mu = magnitude * (mean + scale * (cross.T @ alpha))
        sigma = magnitude * scale * np.sqrt(variance)
    if not np.all(np.isfinite(mu)) or not np.all(np.isfinite(sigma)):
        raise InvalidInputError("GP prediction overflow; rescale objective or constraint units")
    return mu, sigma


def _normal_cdf(values: np.ndarray) -> np.ndarray:
    return np.asarray([0.5 * math.erfc(-float(z) / math.sqrt(2)) for z in values])


def suggest_candidate(
    spec: OptimizationSpec, trials: list[OptimizationTrial], *, pool_size: int = 1024, local_radius: float = 0.25,
) -> dict[str, Any]:
    """Deterministic, read-only ask step using frozen OptimizationSpec/Trial.

    Every trial must carry ``optimization-spec-sha256:<fingerprint>`` in
    provenance. Pending trials block further asks (one solver worker). Trials
    from different fidelities require distinct frozen specs, never pooling.
    """
    names, bounds, objective, sign, constraints, reserve = _configuration(spec)
    if type(pool_size) is not int or not 64 <= pool_size <= 4096:
        raise InvalidInputError("pool_size must be an integer in [64, 4096]")
    radius = _number(local_radius, "local_radius")
    if not 0 < radius <= 1:
        raise InvalidInputError("local_radius must be in (0, 1] in normalized coordinates")
    if len(trials) > spec.evaluation_budget:
        raise InvalidInputError("history exceeds the declared total evaluation budget")
    fingerprint = spec_fingerprint(spec)
    marker = "optimization-spec-sha256:" + fingerprint
    all_x, good_x, y, constraint_y = [], [], [], []
    pending = 0
    identities: set[str] = set()
    run_ids: set[str] = set()
    ordered = sorted(trials, key=lambda item: (item.created_at, item.stable_id))
    for trial in ordered:
        if trial.stable_id in identities or not trial.run_id or trial.run_id in run_ids:
            raise InvalidInputError("history needs unique trial IDs and nonempty unique run IDs")
        identities.add(trial.stable_id)
        run_ids.add(trial.run_id)
        if trial.optimization_spec_id != spec.stable_id or marker not in trial.provenance:
            raise InvalidInputError("trial does not match this exact frozen optimization specification")
        if set(trial.parameters) != set(names):
            raise InvalidInputError("trial parameters differ from the specification")
        values = np.asarray([_number(trial.parameters[name], name) for name in names])
        if np.any(values < bounds[:, 0]) or np.any(values > bounds[:, 1]):
            raise InvalidInputError("trial parameters outside bounds")
        normalized = (values - bounds[:, 0]) / (bounds[:, 1] - bounds[:, 0])
        all_x.append(normalized)
        if trial.status in ("planned", "running"):
            pending += 1
            continue
        if trial.status == "failed":
            if not trial.failure:
                raise InvalidInputError("failed trial needs a failure class")
            continue
        if trial.status != "succeeded" or trial.failure:
            raise InvalidInputError("use planned, running, succeeded or failed status with consistent failure")
        if trial.validity in (Validity.INVALID, Validity.EXPIRED, Validity.OUT_OF_ENVELOPE):
            raise InvalidInputError("invalid/expired/out-of-envelope result cannot train the surrogate")
        if set(trial.objectives) != {objective} or set(trial.constraint_results) != {c[0] for c in constraints}:
            raise InvalidInputError("successful trial needs exactly the declared objective and constraint results")
        good_x.append(normalized)
        y.append(sign * _number(trial.objectives[objective], objective))
        residuals = [(_number(trial.constraint_results[name], name) - upper) / scale
                     for name, upper, scale in constraints]
        if not all(math.isfinite(value) for value in residuals):
            raise InvalidInputError("constraint normalization overflow")
        constraint_y.append(residuals)
    initial_target = max(4, 2 * len(names) + 1)
    remaining_initial = max(0, initial_target - len(y))
    search_slots = max(0, spec.evaluation_budget - reserve - len(trials))
    receipt: dict[str, Any] = {
        "will_execute": False, "algorithm_version": ALGORITHM_VERSION,
        "spec_sha256": fingerprint, "trial_provenance_marker": marker,
        "fidelity": spec.fidelity.value, "trials_consumed_or_reserved": len(trials),
        "validation_reserve": reserve, "search_slots_remaining": search_slots,
        "initial_successes_required": initial_target, "remaining_initialization": remaining_initial,
        "possible_model_guided_slots": max(0, search_slots - remaining_initial),
        "successful_observations": len(y), "pool_size": pool_size, "local_radius": radius,
        "claim_boundary": "experimental suggestion; GP uncertainty is not calibrated evidence; no device gate changes",
    }
    if pending:
        return {**receipt, "action": "wait_for_pending", "pending_trials": pending}
    if receipt["search_slots_remaining"] == 0:
        return {**receipt, "action": "stop_search_preserve_validation"}
    repeated_failure = len(ordered) >= 3 and all(t.status == "failed" for t in ordered[-3:])
    if repeated_failure and len({t.failure for t in ordered[-3:]}) == 1:
        return {**receipt, "action": "diagnose_repeated_failure"}
    rng = np.random.default_rng(np.random.SeedSequence([spec.random_seed, len(trials)]))
    pool = _lhs(pool_size, len(names), rng)
    losses = np.asarray(y)
    residuals = np.asarray(constraint_y).reshape(len(y), len(constraints))
    feasible = np.all(residuals <= 0, axis=1)
    if y:
        incumbent = int(np.argmin(np.where(feasible, losses, np.inf))) if feasible.any() else int(
            np.argmin(np.maximum(residuals, 0).sum(axis=1)))
        center = good_x[incumbent]
        count = 3 * pool_size // 4
        lower, upper = np.maximum(0, center - radius), np.minimum(1, center + radius)
        pool[:count] = lower + (upper - lower) * pool[:count]
    else:
        pool[0] = 0.5
    if all_x:
        distances = _distance(pool, np.asarray(all_x)).min(axis=1)
        available = distances > 1e-14
        pool, distances = pool[available], distances[available]
        if len(pool) == 0:
            return {**receipt, "action": "candidate_pool_exhausted"}
    else:
        distances = np.zeros(len(pool))
    prediction = None
    if len(y) < initial_target:
        chosen = int(np.argmax(distances)) if all_x else 0
        reason = "space_filling_initialization"
    else:
        x = np.asarray(good_x)
        mu, sigma = _posterior(x, losses, pool)
        probability = np.ones(len(pool))
        violation = np.zeros(len(pool))
        for column in range(len(constraints)):
            cmu, csigma = _posterior(x, residuals[:, column], pool)
            probability *= _normal_cdf(-cmu / csigma)
            violation += np.maximum(cmu - csigma, 0)
        if feasible.any():
            # EI in scaled units preserves its ordering and avoids overflow.
            acquisition_scale = max(float(np.abs(losses).max()), float(np.abs(mu).max()),
                                    float(sigma.max()), 1e-10)
            improvement = float(losses[feasible].min()) / acquisition_scale - mu / acquisition_scale
            scaled_sigma = sigma / acquisition_scale
            with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
                z = np.divide(improvement, scaled_sigma, out=np.zeros_like(improvement), where=scaled_sigma > 0)
                expected = (improvement * _normal_cdf(z)
                            + scaled_sigma * np.exp(-z * z / 2) / math.sqrt(2 * math.pi))
            expected = np.where(scaled_sigma > 0, expected, np.maximum(improvement, 0))
            score = np.maximum(expected, 0) * probability
            chosen = int(np.argmax(score)) if score.max() > 1e-14 else int(np.argmax(distances))
            reason = "expected_improvement_times_model_feasibility" if score.max() > 1e-14 else "space_filling_fallback"
        else:
            chosen = int(np.lexsort((-distances, -probability, violation))[0])
            reason = "seek_feasibility"
        prediction = {"objective_mean": sign * float(mu[chosen]), "objective_model_std": float(sigma[chosen]),
                      "model_feasibility_probability": float(probability[chosen])}
    candidate = bounds[:, 0] + pool[chosen] * (bounds[:, 1] - bounds[:, 0])
    return {**receipt, "action": "evaluate_candidate", "reason": reason,
            "parameters": dict(zip(names, candidate.tolist(), strict=True)), "prediction": prediction}
