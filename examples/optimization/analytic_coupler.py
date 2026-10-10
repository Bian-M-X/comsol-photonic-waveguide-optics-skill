"""Reproducible ask/tell experiment; analytic software fixture, not Maxwell data.

Run after installing the package:
  python examples/optimization/analytic_coupler.py --output NEW_DIRECTORY
The two methods share their initial five observations and search budget. Both
replay the winner on a denser analytic grid; remaining reserve is unspent.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from photonic_workflow.models import OptimizationSpec, OptimizationTrial
from photonic_workflow.models.io import write_contract
from photonic_workflow.optimization import spec_fingerprint, suggest_candidate

BOUNDS = np.array([[0.12, 0.35], [1.0, 12.0]])
NAMES = ("gap_um", "length_um")
STAMP = datetime(2026, 9, 29, tzinfo=UTC)


def evaluate(parameters: dict[str, float], *, validation: bool = False) -> dict[str, float]:
    """Lossy symmetric coupled-mode formula with explicitly invented coefficients.

    T_cross = exp(-alpha*L)*sin(kappa*L)^2, T_bar = exp(-alpha*L)*cos(kappa*L)^2.
    kappa = 0.2/um * exp(-(gap-0.2um)/0.12um) * (1+d*(lambda/1.55um-1)).
    These coefficients are NOT calibrated to any platform. Three gap corners
    and five wavelengths train; five corners and 41 wavelengths validate.
    """
    gap, length = (parameters[name] for name in NAMES)
    wavelengths = np.linspace(1.52, 1.58, 41 if validation else 5)
    corners = np.linspace(-0.01, 0.01, 5 if validation else 3)
    actual_gap = gap + corners[:, None]
    dispersion = 0.8 + 3 * (actual_gap - 0.12)
    kappa = 0.2 * np.exp(-(actual_gap - 0.2) / 0.12) * (1 + dispersion * (wavelengths / 1.55 - 1))
    throughput = np.exp(-0.003 * length)
    cross_fraction = np.sin(kappa * length) ** 2
    imbalance = float(np.max(np.abs(cross_fraction - 0.5)))
    return {"robust_loss": imbalance + 0.02 * (1 - float(throughput)),
            "worst_split_error": imbalance, "collected_power": float(throughput),
            "analytic_states": int(cross_fraction.size)}


def specification(seed: int, budget: int, reserve: int) -> OptimizationSpec:
    return OptimizationSpec(
        stable_id=f"optimization:analytic-coupler-{seed}", name="Analytic coupled-mode fixture",
        source="examples/optimization/analytic_coupler.py; coefficients uncalibrated",
        created_at=STAMP, fidelity="analytic", solver_backend="analytic-coupler-fixture-v1",
        variables=[{"name": name, "lower": float(bound[0]), "upper": float(bound[1]), "unit": "um"}
                   for name, bound in zip(NAMES, BOUNDS, strict=True)],
        objectives=[{"name": "robust_loss", "sense": "minimize"}], random_seed=seed,
        evaluation_budget=budget, promotion_rule={"validation_reserve": reserve},
        process_corners=["gap offset -0.01, 0, +0.01 um; wavelengths 1.52..1.58 um, five points"],
        provenance=["analytic software experiment; no device acceptance"],
    )


def experiment(destination: Path, seed: int, budget: int, reserve: int, pool_size: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    initial = np.column_stack([(rng.permutation(5) + rng.random(5)) / 5 for _ in NAMES])
    random_pool = rng.random((budget - reserve - 5, len(NAMES)))
    rows = []
    for method in ("gp_ei", "random"):
        folder = destination / f"seed-{seed}" / method
        trial_directory = folder / "trials"
        trial_directory.mkdir(parents=True, exist_ok=False)
        spec = specification(seed, budget, reserve)
        write_contract(folder / "spec.json", spec)
        marker = "optimization-spec-sha256:" + spec_fingerprint(spec)
        history = []
        proposal_seconds, evaluation_seconds = 0.0, 0.0
        for index in range(budget - reserve):
            start = time.perf_counter()
            if index < 5:
                coordinates = initial[index]
            elif method == "random":
                coordinates = random_pool[index - 5]
            else:
                proposal = suggest_candidate(spec, history, pool_size=pool_size)
                if proposal["action"] != "evaluate_candidate":
                    raise RuntimeError(f"unexpected optimizer stop: {proposal['action']}")
                coordinates = None
            parameters = (dict(zip(NAMES, (BOUNDS[:, 0] + coordinates * np.diff(BOUNDS).ravel()).tolist(),
                                   strict=True)) if coordinates is not None else proposal["parameters"])
            proposal_seconds += time.perf_counter() - start
            trial = OptimizationTrial(
                stable_id=f"trial:{method}-{seed}-{index}", name=f"{method} trial {index}",
                source="analytic-coupler-fixture-v1", created_at=STAMP + timedelta(seconds=index),
                optimization_spec_id=spec.stable_id, run_id=f"run:{method}-{seed}-{index}",
                parameters=parameters, status="planned", provenance=[marker],
            )
            path = trial_directory / f"{index:03d}.json"
            write_contract(path, trial)
            start = time.perf_counter()
            metrics = evaluate(parameters)
            evaluation_seconds += time.perf_counter() - start
            trial.objectives = {"robust_loss": metrics["robust_loss"]}
            trial.status = "succeeded"
            write_contract(path, trial)
            history.append(trial)
        stop = suggest_candidate(spec, history, pool_size=pool_size)
        if stop["action"] != "stop_search_preserve_validation":
            raise RuntimeError("search did not preserve validation slots")
        winner = min(history, key=lambda trial: trial.objectives["robust_loss"])
        validation = evaluate(winner.parameters, validation=True)
        row = {"seed": seed, "method": method, "search_evaluations": len(history),
               "search_analytic_states": 15 * len(history), "validation_evaluations": 1,
               "validation_analytic_states": validation["analytic_states"],
               "unused_reserve": reserve - 1, "spec_sha256": spec_fingerprint(spec),
               "best_training_loss": winner.objectives["robust_loss"],
               "parameters": winner.parameters, "validation": validation,
               "proposal_seconds": proposal_seconds, "evaluation_seconds": evaluation_seconds}
        (folder / "result.json").write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory; never overwritten")
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--reserve", type=int, default=6)
    parser.add_argument("--pool-size", type=int, default=256)
    args = parser.parse_args()
    if not 1 <= args.seeds <= 50 or not 8 <= args.budget <= 100 or not 1 <= args.reserve < args.budget - 5:
        parser.error("require seeds 1..50, budget 8..100 and 1 <= reserve < budget-5")
    if not 64 <= args.pool_size <= 4096:
        parser.error("pool-size must be 64..4096")
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for seed in range(args.seeds):
        rows.extend(experiment(args.output, seed, args.budget, args.reserve, args.pool_size))
    gp = np.array([r["validation"]["robust_loss"] for r in rows if r["method"] == "gp_ei"])
    random = np.array([r["validation"]["robust_loss"] for r in rows if r["method"] == "random"])
    summary = {"claim_boundary": "uncalibrated analytic fixture; no measured full-wave speedup or general superiority",
               "paired_seeds": args.seeds, "budget_per_method": args.budget,
               "search_per_method": args.budget - args.reserve, "shared_initial_points": 5,
               "gp_median_validation_loss": float(np.median(gp)),
               "random_median_validation_loss": float(np.median(random)),
               "gp_strict_wins": int(np.sum(gp < random)),
               "gp_median_proposal_s": float(np.median([
                   r["proposal_seconds"] for r in rows if r["method"] == "gp_ei"])),
               "rows": rows}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
