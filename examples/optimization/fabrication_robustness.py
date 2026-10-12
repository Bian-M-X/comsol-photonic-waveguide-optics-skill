"""Analytic numerical counterexamples; no solver, device or yield validation.

Run after installing the package:
  python -B examples/optimization/fabrication_robustness.py
"""

from __future__ import annotations

import json

import numpy as np

from photonic_workflow.optimization.robustness import axial_scenarios, weighted_pattern_loss


def main() -> None:
    scenarios = axial_scenarios(2)
    axial_interactions = scenarios[:, 0] * scenarios[:, 1]
    target = np.array([0.5, 0.5])
    delta = np.array([0.1, -0.2])
    wafers = np.array([target + delta, target - delta])
    sensitivity = np.array([0.0, -2.0])
    area_weights = np.array([1.0, 3.0])
    losses = [weighted_pattern_loss(wafer, target, sensitivity, quadrature_weights=area_weights)[0]
              for wafer in wafers]
    image_loss, _, gamma = weighted_pattern_loss(np.mean(wafers, axis=0), target, sensitivity,
                                                quadrature_weights=area_weights)
    binary_wafers = np.array([[0.0], [0.0], [1.0]])
    binary_losses = [weighted_pattern_loss(wafer, [0.0], [0.0])[0] for wafer in binary_wafers]
    binary_image_loss = weighted_pattern_loss(np.mean(binary_wafers, axis=0), [0.0], [0.0])[0]
    print(json.dumps({
        "scope": "analytic software counterexamples only; no solver, device acceptance or statistical yield",
        "axial_screening": {
            "normalized_scenarios": scenarios.tolist(),
            "mixed_interaction_z1_times_z2": axial_interactions.tolist(),
            "maximum_on_axial_samples": float(np.max(axial_interactions)),
            "joint_corner": [1.0, 1.0],
            "joint_corner_interaction": 1.0,
            "limitation": "axis-only sampling misses mixed interactions; no global worst-case guarantee",
        },
        "mean_image_cancellation": {
            "target_scope": "gray target in the interior of [0,1] allows exact opposing-error cancellation",
            "wafer_scenarios": wafers.tolist(),
            "target": target.tolist(),
            "gamma": gamma.tolist(),
            "quadrature_weights": area_weights.tolist(),
            "per_scenario_losses": losses,
            "maximum_scenario_loss": max(losses),
            "mean_scenario_loss": float(np.mean(losses)),
            "loss_of_mean_wafer_image": image_loss,
            "limitation": "aggregate per-scenario losses after evaluation; opposing image errors cancel",
        },
        "binary_target_loss_underestimation": {
            "target": [0.0],
            "wafer_scenarios": binary_wafers.tolist(),
            "per_scenario_losses": binary_losses,
            "mean_scenario_loss": float(np.mean(binary_losses)),
            "maximum_scenario_loss": max(binary_losses),
            "loss_of_mean_wafer_image": binary_image_loss,
            "mean_loss_underestimation_factor": float(np.mean(binary_losses)) / binary_image_loss,
            "limitation": "binary-target errors have the same sign; fourth-power loss still hides scenario spread",
        },
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
