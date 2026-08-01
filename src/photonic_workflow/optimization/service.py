from __future__ import annotations

from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import OptimizationSpec


def plan_optimization(spec: OptimizationSpec) -> dict[str, Any]:
    if not spec.variables:
        raise InvalidInputError("optimization variables are A-class inputs and must be explicit")
    if not spec.objectives:
        raise InvalidInputError("optimization objectives are A-class inputs and must be explicit")
    if spec.evaluation_budget < 1:
        raise InvalidInputError("optimization evaluation_budget must be positive")
    return {
        "dry_run": True,
        "optimization_spec_id": spec.stable_id,
        "fidelity": spec.fidelity.value,
        "solver_backend": spec.solver_backend,
        "evaluation_budget": spec.evaluation_budget,
        "worker_policy": "commercial solvers default to one worker; each evaluation is an independent Run",
        "checkpoint_interval": spec.checkpoint_interval,
        "random_seed": spec.random_seed,
        "promotion_rule": spec.promotion_rule,
        "claim_boundary": "a best observed sample is not a proven global optimum",
    }
