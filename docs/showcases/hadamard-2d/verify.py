"""Check exported Hadamard numbers only; does not rerun or authenticate COMSOL.

Usage: python verify.py [BUNDLE_DIRECTORY] [--output report.json]
Requires the checkout's inverse-design dependencies. Native receipts and omitted
native artifacts cannot be reverified from this compact public export.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from photonic_workflow.optimization.hadamard import DEFAULT_POLICY, decode_pairs, evaluate  # noqa: E402

MASK_SHA256 = "90bdfde4ff488e0e64b05933d9d9428ee6cc712d09a19f7f228b03b7ce3d4dc7"
RECIPE_SHA256 = "4ecf4d33722d2c1e89e8d0e92baaf2f964e329d5aa5073ba9ce41a9494b05be2"
FROZEN_POLICY = {
    "fidelity_floor": 0.987,
    "transmission_floor": 0.9,
    "ratio_min": 0.9,
    "ratio_max": 1.1,
    "passivity_tolerance": 0.005,
    "reciprocity_tolerance": 0.005,
}
EXTRA_POLICY = {"incoming_operator_norm": 0.005, "mirror_amplitude": 0.005, "signed_flux_closure": 0.005}
CONVERGENCE_POLICY = {"eta": 0.005, "all_input_eta": 0.005, "fidelity": 0.002, "ratio": 0.02}
MARKER_CHECKS = ("interior_flux_partition_pass", "pml_configuration_pass", "slit_ports_pass")


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ANALYZER = module("showcase_analyzer", ROOT / "examples/comsol-hadamard-inverse/analyze.py")
CAMPAIGN = module("showcase_campaign", ROOT / "examples/comsol-hadamard-inverse/campaign.py")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError("Duplicate JSON key: " + key)
            obj[key] = value
        return obj

    def invalid(value):
        raise ValueError("Nonfinite JSON constant: " + value)

    value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    finite_tree(value)
    return value


def finite_tree(value):
    if isinstance(value, dict):
        for child in value.values():
            finite_tree(child)
    elif isinstance(value, list):
        for child in value:
            finite_tree(child)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON number")


def same(actual, expected, label="value"):
    """Strict booleans/structure; roundoff tolerance only for numeric reports."""
    if isinstance(expected, bool):
        good = type(actual) is bool and actual is expected
    elif isinstance(expected, dict):
        good = isinstance(actual, dict) and set(actual) == set(expected)
        if good:
            for key in expected:
                same(actual[key], expected[key], label + "." + key)
            return
    elif isinstance(expected, list):
        good = isinstance(actual, list) and len(actual) == len(expected)
        if good:
            for index, (a, e) in enumerate(zip(actual, expected, strict=True)):
                same(a, e, f"{label}[{index}]")
            return
    elif isinstance(expected, (float, int)):
        good = (
            type(actual) in (int, float)
            and math.isfinite(actual)
            and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
        )
    else:
        good = type(actual) is type(expected) and actual == expected
    if not good:
        raise ValueError("Mismatch: " + label)


def exact(actual, expected, label):
    # JSON preserves bool/int distinction here rather than Python's True == 1.
    same(actual, expected, label)
    if json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
        # Config defaults mix integer/float representations; permit exactly equal
        # finite numbers, but never near-equal relaxed thresholds/configurations.
        def canonical(v):
            if type(v) in (int, float):
                return float(v)
            if isinstance(v, dict):
                return {k: canonical(x) for k, x in v.items()}
            if isinstance(v, list):
                return [canonical(x) for x in v]
            return v

        if canonical(actual) != canonical(expected):
            raise ValueError("Frozen value changed: " + label)


def recompute(row, temporary):
    matrix = decode_pairs(row["A"])
    incoming = decode_pairs(row["B"])
    if matrix.shape != (8, 8) or incoming.shape != (8, 8):
        raise ValueError("A and B must each be 8x8")
    report = evaluate(matrix, policy=FROZEN_POLICY)
    recorded = row["report"]
    exact(recorded["policy"], FROZEN_POLICY, "report.policy")
    for key in report:
        if key not in ("observed_matrix_scope", "acceptance_pass", "checks"):
            same(recorded[key], report[key], "report." + key)
    same(recorded["S"], row["A"], "report.S")
    lines = [
        f"MODAL_INCOMING={source + 1},{index + 1},{float(z.real)!r},{float(z.imag)!r}"
        for source in range(8)
        for index, z in enumerate(incoming[:, source])
    ]
    incident = ANALYZER.read_incoming("\n".join(lines))
    same(recorded["modal_incoming_evidence"], incident, "incoming")
    flux_rows = row["signed_flux_rows"]
    if not isinstance(flux_rows, list) or len(flux_rows) != 8:
        raise ValueError("Eight ordered signed flux rows required")
    for index, item in enumerate(flux_rows, 1):
        if not isinstance(item, dict) or set(item) != set(ANALYZER.POWER_COLUMNS):
            raise ValueError("Unexpected signed flux row schema")
        if type(item["source"]) is not int or item["source"] != index:
            raise ValueError("Flux sources must be uniquely ordered 1..8")
        if any(
            type(item[key]) not in (int, float) or not math.isfinite(item[key]) for key in ANALYZER.POWER_COLUMNS[1:]
        ):
            raise ValueError("Flux values must be finite numbers, no bool")
    power = temporary / "power.csv"
    with power.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANALYZER.POWER_COLUMNS)
        writer.writeheader()
        writer.writerows(flux_rows)
    flux = ANALYZER.read_power(power, matrix, 0.005, "slit_pml")
    same(recorded["measured_net_flux"], flux, "flux")
    coverage = ANALYZER.modal_coverage(row["config"], 2)
    same(recorded["propagating_mode_coverage"], coverage, "coverage")
    checks = report["checks"] | {
        "modal_incoming_normalization_pass": incident["normalization_pass"],
        "state_floor_mirror_assumption_pass": report["mirror_matrix_max_absolute_residual"] <= 0.005,
        "signed_flux_closure_pass": flux["closure_pass"],
        "propagating_mode_coverage_pass": coverage["coverage_pass"],
    }
    for key in MARKER_CHECKS:
        if type(row["native_marker_assertions"].get(key)) is not bool:
            raise ValueError("Native marker assertions must be bool")
        checks[key] = row["native_marker_assertions"][key]
    same(recorded["checks"], checks, "checks")
    same(recorded["acceptance_pass"], all(checks.values()), "acceptance_pass")
    same(recorded["matrix_acceptance_pass"], report["acceptance_pass"], "matrix_acceptance_pass")
    same(recorded["native_configuration"], row["config"], "native_configuration")
    for key, field in zip(
        MARKER_CHECKS, ("interior_partition_verified", "pml_configuration_verified", "slit_ports_verified"), strict=True
    ):
        same(recorded["boundary_evidence"][field], checks[key], "boundary_evidence." + field)
    for artifact in ("plan.json", "metrics.csv", "power.csv", "console.log"):
        same(
            recorded["evidence_sha256"][artifact],
            row["original_artifact_sha256"][artifact],
            "original_artifact." + artifact,
        )
    same(recorded["metrics_sha256"], row["original_artifact_sha256"]["metrics.csv"], "metrics_sha256")
    for field, expected in (
        ("amplitude_absolute_tolerance", 0.005),
        ("mirror_symmetry_required", True),
        ("objective_profile", "state_floor"),
        ("mirror_symmetry_pass", checks["state_floor_mirror_assumption_pass"]),
    ):
        exact(recorded["objective_assumption_evidence"][field], expected, "objective_assumption." + field)
    same(
        recorded["objective_assumption_evidence"]["mirror_matrix_max_absolute_residual"],
        report["mirror_matrix_max_absolute_residual"],
        "objective_assumption.mirror_matrix_max_absolute_residual",
    )
    return report | {"checks": checks, "acceptance_pass": all(checks.values())}


def verify(folder):
    folder = Path(folder)
    manifest = read_json(folder / "manifest.json")
    if manifest.get("schema") != "hadamard-2d-export-manifest-v1" or set(manifest.get("files", {})) != {
        "bundle.json",
        "mask.json",
    }:
        raise ValueError("Unexpected export manifest")
    for name, sha in manifest["files"].items():
        if digest(folder / name) != sha:
            raise ValueError("Export file hash mismatch: " + name)
    bundle = read_json(folder / "bundle.json")
    if bundle.get("schema") != "hadamard-2d-numerical-export-v1":
        raise ValueError("Unknown bundle schema")
    exact(DEFAULT_POLICY, FROZEN_POLICY, "runtime policy")
    exact(bundle["policy"], FROZEN_POLICY, "policy")
    exact(bundle["additional_policy"], EXTRA_POLICY, "additional_policy")
    exact(bundle["convergence_policy"], CONVERGENCE_POLICY, "convergence_policy")
    exact(bundle["native_receipts_reverified"], False, "native_receipts_reverified")
    if bundle["mask_sha256"] != MASK_SHA256 or digest(folder / "mask.json") != MASK_SHA256:
        raise ValueError("Locked mask hash mismatch")
    mask = read_json(folder / "mask.json")
    exact(mask["threshold"], 0.4683617431984674, "mask threshold")
    recipe = CAMPAIGN.plan()
    frozen_recipe = {key: recipe[key] for key in ("binary_nominal", "validation", "convergence_pairs")}
    fingerprint = hashlib.sha256(json.dumps(frozen_recipe, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != RECIPE_SHA256:
        raise ValueError("The runtime validation recipe differs from the frozen showcase recipe")
    exact(bundle["convergence_pairs"], recipe["convergence_pairs"], "convergence_pairs")
    expected_order = ["selected_binary"] + [name for name, _ in recipe["validation"]]
    rows = bundle["runs"]
    if not isinstance(rows, list) or [row.get("name") for row in rows] != expected_order:
        raise ValueError("Full numerical PASS requires center plus all 19 ordered validation runs")
    defaults = CAMPAIGN._RUNNER.configuration(None)
    configs = {"selected_binary": defaults | recipe["binary_nominal"]}
    configs.update({name: defaults | recipe["binary_nominal"] | changes for name, changes in recipe["validation"]})
    reports = {}
    with tempfile.TemporaryDirectory(prefix="hadamard-numeric-") as temporary:
        for row in rows:
            name = row["name"]
            exact(row["config"], configs[name], name + ".config")
            if row["mask_sha256"] != MASK_SHA256:
                raise ValueError("Per-run locked mask mismatch: " + name)
            if type(row["native_completed_assertion"]) is not bool or row["native_completed_assertion"] is not True:
                raise ValueError("Incomplete original native execution assertion")
            if not re.fullmatch(r"[0-9a-f]{64}", row["original_receipt_sha256"]):
                raise ValueError("Invalid original receipt provenance hash")
            for sha in row["original_artifact_sha256"].values():
                if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
                    raise ValueError("Invalid original artifact provenance hash")
            reports[name] = recompute(row, Path(temporary))
    comparisons = {
        name: CAMPAIGN.convergence(reports[a], reports[b]) for name, (a, b) in recipe["convergence_pairs"].items()
    }
    same(bundle["convergence"], comparisons, "convergence")
    passed = all(r["acceptance_pass"] for r in reports.values()) and all(c["pass"] for c in comparisons.values())
    return {
        "numeric_self_consistency_pass": passed,
        "full_numerical_suite_pass": passed,
        "native_receipts_reverified": False,
        "native_execution_reproduced": False,
        "completed_numeric_runs": len(reports),
        "completed_convergence_pairs": len(comparisons),
        "mask_sha256": MASK_SHA256,
        "scope": (
            "Exported numerical self-consistency only. Native marker assertions and original receipt/artifact hashes "
            "are provenance links, not reverified native evidence. Fresh licensed COMSOL runs are required "
            "for full reproduction."
        ),
        "checks": {name: r["checks"] for name, r in reports.items()},
        "convergence": comparisons,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, nargs="?", default=Path(__file__).parent / "evidence")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.bundle)
    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
        result = {
            "numeric_self_consistency_pass": False,
            "full_numerical_suite_pass": False,
            "native_receipts_reverified": False,
            "error": str(error),
        }
    encoded = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["full_numerical_suite_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
