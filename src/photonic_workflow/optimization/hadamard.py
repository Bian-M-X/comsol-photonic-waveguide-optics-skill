"""Fixed-gauge Hadamard surrogate metrics, independent of COMSOL.

CLI: python -m photonic_workflow.optimization.hadamard input.json [--output output.json]
JSON keys: S (NxN [real,imag] pairs), optional additional_modes (expanded
square observed matrix), input_indices, output_indices, convention, policy.
No fitted per-port phases. Unobserved power is not identified as absorption.
"""

import argparse
import json
import numbers

import numpy as np

DEFAULT_POLICY = dict(
    fidelity_floor=0.987,
    transmission_floor=0.9,
    ratio_min=0.9,
    ratio_max=1.1,
    passivity_tolerance=0.005,
    reciprocity_tolerance=0.005,
)


def _matrix(value, name):
    raw = np.asarray(value)
    if raw.ndim != 2 or raw.shape[0] != raw.shape[1] or raw.shape[0] < 4:
        raise ValueError(name + " must be square NxN, N>=4")
    if raw.dtype.kind not in "fciu" or raw.dtype.kind == "b":
        raise ValueError(name + " must contain numeric complex amplitudes, not bool/string")
    # Explicit object/nested bool check catches booleans silently promoted by numpy.
    for row in value:
        for v in row:
            if isinstance(v, (bool, np.bool_)):
                raise ValueError(name + " contains bool")
    arr = np.asarray(value, dtype=complex)
    if not np.isfinite(arr).all():
        raise ValueError(name + " contains nonfinite amplitudes")
    return arr


def _indices(value, n, name):
    if len(value) != 2 or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, numbers.Integral) for v in value):
        raise ValueError(name + " must contain two integer indices")
    if len(set(value)) != 2 or any(v < 0 or v >= n for v in value):
        raise ValueError(name + " invalid indices")
    return list(value)


def _observed(S, inputs, policy):
    singular = np.linalg.svd(S, compute_uv=False)
    rec = float(np.max(np.abs(S - S.T)))
    return dict(
        singular_values=singular.tolist(),
        sigma_max=float(singular[0]),
        passivity_pass=bool(singular[0] <= 1 + policy["passivity_tolerance"]),
        reciprocity_max_absolute_residual=rec,
        reciprocity_pass=bool(rec <= policy["reciprocity_tolerance"]),
        sum_observed_port_powers_per_input=np.sum(abs(S[:, inputs]) ** 2, axis=0).tolist(),
    )


def evaluate(S, input_indices=(0, 1), output_indices=(2, 3), convention="paper", policy=None, additional_modes=None):
    """Return JSON-safe metrics. `convention` must be frozen before measurement.

    `additional_modes` is an optional expanded NxN scattering matrix including
    additional modes in the SAME normalization/gauge, with original indices
    retained. It is not a second disjoint matrix to sum blindly.
    """
    S = _matrix(S, "S")
    inputs = _indices(input_indices, len(S), "input_indices")
    outputs = _indices(output_indices, len(S), "output_indices")
    if set(inputs) & set(outputs):
        raise ValueError("Input and output indices must be disjoint")
    if convention not in ("paper", "conjugate"):
        raise ValueError("convention must be paper or conjugate; no auto selection")
    p = DEFAULT_POLICY.copy()
    if policy is not None:
        if not isinstance(policy, dict) or set(policy) - set(p):
            raise ValueError("Unknown threshold policy keys")
        for k, v in policy.items():
            if isinstance(v, bool) or not isinstance(v, numbers.Real) or not np.isfinite(v):
                raise ValueError("Policy values must be finite real numbers")
            p[k] = float(v)
    if not (
        0 <= p["fidelity_floor"] <= 1
        and 0 <= p["transmission_floor"] <= 1
        and 0 <= p["ratio_min"] <= p["ratio_max"]
        and p["passivity_tolerance"] >= 0
        and p["reciprocity_tolerance"] >= 0
    ):
        raise ValueError("Invalid threshold policy range")
    B = np.array([[1, 1j], [1j, 1]], complex) / np.sqrt(2)
    if convention == "conjugate":
        B = B.conj()
    T = S[np.ix_(outputs, inputs)]
    # Rayleigh minimum over every normalized complex logical input, without
    # assuming mirror symmetry or restricting the input to six test states.
    minimum_target_throughput = float(np.linalg.svd(T, compute_uv=False)[-1] ** 2)
    mirror_residual = float(max(abs(T[0, 0] - T[1, 1]), abs(T[0, 1] - T[1, 0])))
    states = dict(
        zero=[1, 0],
        one=[0, 1],
        plus=np.array([1, 1]) / np.sqrt(2),
        minus=np.array([1, -1]) / np.sqrt(2),
        plus_i=np.array([1, 1j]) / np.sqrt(2),
        minus_i=np.array([1, -1j]) / np.sqrt(2),
    )
    metrics = {}
    for name, psi in states.items():
        psi = np.asarray(psi, complex)
        actual = T @ psi
        throughput = float(np.vdot(actual, actual).real)
        if throughput <= 0:
            raise ValueError("Zero conditional normalization for " + name)
        fidelity = float(abs(np.vdot(B @ psi, actual)) ** 2 / throughput)
        metrics[name] = dict(conditional_fidelity=fidelity, target_throughput=throughput)
    norm = float(np.vdot(T, T).real)
    if norm <= 0:
        raise ValueError("Zero Choi normalization")
    choi = float(abs(np.trace(B.conj().T @ T)) ** 2 / (2 * norm))
    powers = abs(T) ** 2
    ratios = [float(powers[0, j] / powers[1, j]) if powers[1, j] > 0 else None for j in range(2)]
    split_pass = all(r is not None and p["ratio_min"] <= r <= p["ratio_max"] for r in ratios)
    obs = _observed(S, inputs, p)
    checks = dict(
        fidelity_pass=bool(
            min(v["conditional_fidelity"] for v in metrics.values()) >= p["fidelity_floor"]
            and choi >= p["fidelity_floor"]
        ),
        throughput_pass=bool(minimum_target_throughput >= p["transmission_floor"]),
        both_input_split_pass=bool(split_pass),
        observed_passivity_pass=obs["passivity_pass"],
        observed_reciprocity_pass=obs["reciprocity_pass"],
    )
    result = dict(
        schema_version=1,
        claim_label="2D Hadamard-equivalent surrogate evaluated against declared complex-matrix targets",
        observed_matrix_scope="fundamental-selected S"
        if len(S) == 4
        else "declared observed modal S; completeness unverified",
        input_indices=inputs,
        output_indices=outputs,
        target_convention=convention,
        target_matrix=[[[float(z.real), float(z.imag)] for z in row] for row in B],
        policy=p,
        policy_status="engineering policy; not paper experimental process fidelity or paper transmission floor",
        six_states=metrics,
        basis_states={k: metrics[k] for k in ("zero", "one")},
        min_six_state_conditional_fidelity=min(v["conditional_fidelity"] for v in metrics.values()),
        conditional_choi_overlap=choi,
        target_throughput_per_input=powers.sum(axis=0).tolist(),
        min_six_state_target_throughput=min(v["target_throughput"] for v in metrics.values()),
        minimum_target_throughput_all_inputs=minimum_target_throughput,
        mirror_matrix_max_absolute_residual=mirror_residual,
        both_input_split_ratios=ratios,
        observed_S=obs,
        checks=checks,
        acceptance_pass=all(checks.values()),
        power_boundary=(
            "Observed modal powers only; no absorption/loss inference from 1-R-T. No measured tomography claim."
        ),
    )
    if additional_modes is not None:
        expanded = _matrix(additional_modes, "additional_modes")
        if len(expanded) <= len(S):
            raise ValueError("additional_modes must expand observed matrix")
        if not np.allclose(expanded[: len(S), : len(S)], S, rtol=1e-10, atol=1e-12):
            raise ValueError("Expanded matrix must preserve original S block and common gauge")
        result["additional_modes_observed_S"] = _observed(expanded, inputs, p)
        result["checks"]["expanded_observed_passivity_pass"] = result["additional_modes_observed_S"]["passivity_pass"]
        result["checks"]["expanded_observed_reciprocity_pass"] = result["additional_modes_observed_S"][
            "reciprocity_pass"
        ]
        result["acceptance_pass"] = all(result["checks"].values())
    return result


def decode_pairs(value):
    if not isinstance(value, list) or not value:
        raise ValueError("S must be an array")
    rows = []
    for row in value:
        if not isinstance(row, list):
            raise ValueError("S rows must be arrays")
        decoded = []
        for pair in row:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) for v in pair)
            ):
                raise ValueError("Each S element must be a finite [real,imag] pair, no bool")
            decoded.append(complex(*pair))
        rows.append(decoded)
    return _matrix(rows, "S")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input")
    ap.add_argument("--output")
    args = ap.parse_args()
    try:
        with open(args.input, encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict) or set(doc) - {
            "S",
            "additional_modes",
            "input_indices",
            "output_indices",
            "convention",
            "policy",
        }:
            raise ValueError("Invalid input object or unknown keys")
        if "S" not in doc:
            raise ValueError("Missing S")
        doc["S"] = decode_pairs(doc["S"])
        if "additional_modes" in doc:
            doc["additional_modes"] = decode_pairs(doc["additional_modes"])
        report = evaluate(**doc)
        output = json.dumps(report, indent=2, allow_nan=False)
    except (OSError, ValueError, TypeError) as error:
        ap.error(str(error))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
    else:
        print(output)
    return 0 if report["acceptance_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
