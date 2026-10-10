"""Verify an exported source-conditioned matrix; no solver execution."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from photonic_workflow.optimization.hadamard import evaluate

BOUNDARY_MARKER = "EXTERIOR_BOUNDARY_PARTITION_VERIFIED=true"
INTERIOR_BOUNDARY_MARKER = "INTERIOR_FLUX_PARTITION_VERIFIED=true"
PML_CONFIGURATION_MARKER = "PML_CONFIGURATION_VERIFIED=true"
SLIT_PORTS_MARKER = "SLIT_PORTS_VERIFIED=true"
INCOMING_PREFIX = "MODAL_INCOMING="
INCOMING_AMPLITUDE_TOLERANCE = 0.005
MIRROR_AMPLITUDE_TOLERANCE = 0.005
DEFAULT_CLOSURE_TOLERANCE = 0.005
POWER_COLUMNS = ("source", "net_p1", "net_p2", "net_p3", "net_p4", "open_outward", "closed_surface_residual")


def validate_guided_modes(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (1, 2):
        raise ValueError("guided_modes must be integer 1 or 2")
    return value


def modal_coverage(config: dict, declared: int) -> dict:
    """Count bound Hz slab branches for this fixed 400 nm fixture only."""
    declared = validate_guided_modes(declared)
    wavelength = config.get("wavelength_nm", 1550)
    core = config.get("eps_core", 12.1)
    clad = config.get("eps_clad", 2.1)
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (wavelength, core, clad)
    ) or not (wavelength > 0 and core > clad > 0):
        raise ValueError("Invalid wavelength/permittivity for the fixed slab mode-coverage check")
    wavelength_m = wavelength * 1e-9
    if wavelength_m <= 0:
        raise ValueError("Wavelength underflows the slab-coverage calculation")
    normalized_frequency = 2 * math.pi / wavelength_m * 0.2e-6 * math.sqrt(core - clad)
    if not math.isfinite(normalized_frequency) or normalized_frequency <= 0:
        raise ValueError("Slab normalized frequency must be positive and finite")
    # Branch m is bound iff V > m*pi/2; at equality q=0 is not normalizable.
    expected = math.ceil(math.nextafter(2 * normalized_frequency / math.pi, -math.inf))
    return {
        "V": normalized_frequency,
        "expected_bound_modes_per_physical_port": expected,
        "declared_modes_per_physical_port": declared,
        "coverage_pass": declared >= expected,
        "scope": "Analytic bound Hz modes of this fixed 400 nm symmetric infinite-height slab only; "
        "not a general waveguide completeness test or a 220 nm SOI strip model",
        "cutoff_rule": "Mode m is bound only when V > m*pi/2; exact cutoff is excluded",
        "width_um": 0.4,
        "wavelength_nm": wavelength,
        "eps_core": core,
        "eps_clad": clad,
    }


def checked_artifact(folder: Path, receipt: dict, name: str) -> tuple[Path, str]:
    path = folder / name
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if receipt.get("artifacts", {}).get(name, {}).get("sha256") != digest:
        raise ValueError(f"{name} no longer matches its execution receipt")
    return path, digest


def read_power(path: Path, matrix: np.ndarray, tolerance: float, boundary_model: str = "exterior_modal") -> dict:
    if matrix.shape not in ((4, 4), (8, 8)) or not np.isfinite(matrix).all():
        raise ValueError("Expected a finite 4x4 or 8x8 observed modal matrix")
    sources = len(matrix)
    rows = []
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(POWER_COLUMNS):
            raise ValueError("Unexpected power.csv columns")
        for row in reader:
            if set(row) != set(POWER_COLUMNS) or any(v is None for v in row.values()):
                raise ValueError("Malformed power row")
            source = int(row["source"])
            values = np.asarray([float(row[key]) for key in POWER_COLUMNS[1:]])
            if not np.isfinite(values).all():
                raise ValueError("Nonfinite power row")
            if source != len(rows) + 1 or source > sources:
                raise ValueError(f"Power source order must be uniquely 1..{sources}")
            net = values[:4]
            open_outward, recorded = values[4:]
            summed = float(np.sum(net) + open_outward)
            if not np.isclose(summed, recorded, rtol=0, atol=1e-12):
                raise ValueError("Power row sum does not match closed_surface_residual")
            observed_power = np.asarray([np.sum(abs(matrix[port::4, source - 1]) ** 2) for port in range(4)])
            selected_net = observed_power.copy()
            selected_net[(source - 1) % 4] -= 1
            rows.append(
                {
                    "source": source,
                    "source_physical_port": (source - 1) % 4 + 1,
                    "source_mode": (source - 1) // 4,
                    "net_port_flux": net.tolist(),
                    "observed_modal_outward_power_per_physical_port": observed_power.tolist(),
                    "open_outward_flux": float(open_outward),
                    "closed_surface_residual": summed,
                    "closure_pass": bool(abs(summed) <= tolerance),
                    "net_minus_observed_modal_expectation_unresolved_difference": (net - selected_net).tolist(),
                }
            )
    if len(rows) != sources:
        raise ValueError(f"{sources} source-conditioned power rows are required")
    return {
        "normalization": "signed outward flux divided by declared 1 W/m incident port power",
        "scope": (
            ("Signed source-free interior closed-surface closure only; " if boundary_model == "slit_pml"
             else "Signed exterior-surface closure only; ")
            + "modal-versus-net-flux differences are reported separately "
            "and are not validated by this check"
        ),
        "closure_absolute_tolerance": tolerance,
        "closure_policy_status": "engineering policy: 0.5% of declared Pin by default; not a paper tolerance",
        "sources": rows,
        "closure_pass": all(row["closure_pass"] for row in rows),
        "interpretation": "Unresolved differences are not assigned to higher modes, absorption, or loss.",
    }


def complex_pairs(matrix: np.ndarray) -> list:
    return [[[float(v.real), float(v.imag)] for v in row] for row in matrix]


def read_incoming(console: str) -> dict:
    """Read the raw eight-source incident basis without correcting exported S."""
    cells: dict[tuple[int, int], complex] = {}
    for line in console.splitlines():
        if not line.startswith(INCOMING_PREFIX):
            continue
        fields = line[len(INCOMING_PREFIX):].split(",")
        if len(fields) != 4:
            raise ValueError("Malformed MODAL_INCOMING record")
        try:
            source, row = int(fields[0]), int(fields[1])
            value = complex(float(fields[2]), float(fields[3]))
        except ValueError as error:
            raise ValueError("Malformed MODAL_INCOMING record") from error
        if not 1 <= source <= 8 or not 1 <= row <= 8 or (row, source) in cells:
            raise ValueError("Duplicate or invalid MODAL_INCOMING source/row")
        if not np.isfinite(value):
            raise ValueError("Nonfinite MODAL_INCOMING amplitude")
        cells[row, source] = value
    if len(cells) != 64:
        raise ValueError("All 64 MODAL_INCOMING source-conditioned entries are required for slit_pml")
    incoming = np.array([[cells[row, source] for source in range(1, 9)] for row in range(1, 9)])
    error = incoming - np.eye(8)
    maximum = float(np.max(abs(error)))
    operator_norm = float(np.linalg.norm(error, ord=2))
    offdiagonal = incoming.copy()
    np.fill_diagonal(offdiagonal, 0)
    return {
        "B": complex_pairs(incoming),
        "B_minus_identity": complex_pairs(error),
        "max_absolute_identity_residual": maximum,
        "operator_norm_identity_residual": operator_norm,
        "max_offdiagonal_amplitude": float(np.max(abs(offdiagonal))),
        "amplitude_absolute_tolerance": INCOMING_AMPLITUDE_TOLERANCE,
        "normalization_pass": bool(operator_norm <= INCOMING_AMPLITUDE_TOLERANCE),
        "policy_status": "engineering amplitude tolerance; not a paper tolerance",
        "scope": "Raw exact two-direction analytic TM projection for a 2D lossless real-mode basis only; "
                 "rows are incoming modes and columns are independent sources",
        "interpretation": "S is retained as exported; no fitting, inversion, or renormalization by B",
    }


def analyze(folder: Path, closure_tolerance: float = DEFAULT_CLOSURE_TOLERANCE) -> dict:
    if isinstance(closure_tolerance, bool) or not np.isfinite(closure_tolerance) or closure_tolerance < 0:
        raise ValueError("Closure tolerance must be finite and nonnegative")
    receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or receipt.get("completed") is not True:
        raise ValueError("The native execution did not complete")
    artifacts = {
        name: checked_artifact(folder, receipt, name)
        for name in ("plan.json", "metrics.csv", "power.csv", "console.log")
    }
    plan = json.loads(artifacts["plan.json"][0].read_text(encoding="utf-8"))
    config = plan["config"]
    boundary_model = config.get("boundary_model", "exterior_modal")
    if not isinstance(boundary_model, str) or boundary_model not in ("exterior_modal", "slit_pml"):
        raise ValueError("boundary_model must be exterior_modal or slit_pml")
    objective_profile = config.get("objective_profile", "coherent")
    if not isinstance(objective_profile, str) or objective_profile not in ("coherent", "state_floor"):
        raise ValueError("objective_profile must be coherent or state_floor")
    guided_modes = validate_guided_modes(config.get("guided_modes", 1))
    if boundary_model == "slit_pml" and guided_modes != 2:
        raise ValueError("slit_pml requires the full eight-channel TM0/TM1 analytic basis")
    matrix = read_matrix(artifacts["metrics.csv"][0], guided_modes)
    report = evaluate(matrix)
    report["guided_modes_per_physical_port"] = guided_modes
    report["observed_modal_port_count"] = 4 * guided_modes
    report["declared_modal_basis"] = [
        {
            "modal_port": 4 * mode + port + 1,
            "physical_port": port + 1,
            "physical_location": location,
            "mode": f"TM{mode}",
        }
        for mode in range(guided_modes)
        for port, location in enumerate(("left", "bottom", "top", "right"))
    ]
    report["observed_matrix_scope"] = (
        "fundamental-selected S"
        if guided_modes == 1
        else "TM0/TM1 observed modal S; declared two-mode slab basis, boundary/continuum completeness unverified"
    )
    report["matrix_acceptance_pass"] = report["acceptance_pass"]
    report["propagating_mode_coverage"] = modal_coverage(config, guided_modes)
    report["measured_net_flux"] = read_power(artifacts["power.csv"][0], matrix, closure_tolerance, boundary_model)
    console = artifacts["console.log"][0].read_text(encoding="utf-8", errors="replace")
    markers = console.splitlines()
    if boundary_model == "slit_pml":
        boundary_verified = markers.count(INTERIOR_BOUNDARY_MARKER) == 1
        pml_verified = markers.count(PML_CONFIGURATION_MARKER) == 1
        slit_verified = markers.count(SLIT_PORTS_MARKER) == 1
        report["boundary_evidence"] = {
            "boundary_model": boundary_model,
            "required_console_marker": INTERIOR_BOUNDARY_MARKER,
            "required_console_markers": [INTERIOR_BOUNDARY_MARKER, PML_CONFIGURATION_MARKER, SLIT_PORTS_MARKER],
            "interior_partition_verified": boundary_verified,
            "pml_configuration_verified": pml_verified,
            "slit_ports_verified": slit_verified,
            "scope": "Native set equality for a source-free interior closed flux surface, partitioned into "
                     "modal observation windows and open segments; the outer PML boundary is not this surface",
            "model_scope": "2D lossless material model with real analytic TM0/TM1 profiles only; "
                           "PML and projection checks do not establish general cross-section or 3D validity",
        }
        report["modal_incoming_evidence"] = read_incoming(console)
        report["raw_export_amplitude_scope"] = (
            "Raw outgoing A per nominal 1 W/m source, treated as an approximate unit incoming basis "
            "only within the reported operator-norm bound on B-I; S fields retain A without A B^-1"
        )
        report["checks"]["interior_flux_partition_pass"] = boundary_verified
        report["checks"]["pml_configuration_pass"] = pml_verified
        report["checks"]["slit_ports_pass"] = slit_verified
        report["checks"]["modal_incoming_normalization_pass"] = report["modal_incoming_evidence"]["normalization_pass"]
    else:
        boundary_verified = markers.count(BOUNDARY_MARKER) == 1
        report["boundary_evidence"] = {
            "required_console_marker": BOUNDARY_MARKER,
            "exterior_partition_verified": boundary_verified,
            "scope": "Native set equality: all exterior boundaries appear exactly once in ports or open selection",
        }
        report["checks"]["exterior_boundary_partition_pass"] = boundary_verified
    mirror_pass = report["mirror_matrix_max_absolute_residual"] <= MIRROR_AMPLITUDE_TOLERANCE
    report["objective_assumption_evidence"] = {
        "objective_profile": objective_profile,
        "mirror_symmetry_required": objective_profile == "state_floor",
        "mirror_matrix_max_absolute_residual": report["mirror_matrix_max_absolute_residual"],
        "amplitude_absolute_tolerance": MIRROR_AMPLITUDE_TOLERANCE,
        "mirror_symmetry_pass": bool(mirror_pass),
        "scope": "Measured logical 2x2 block symmetry required for the state_floor objective assumption; "
                 "all-input throughput is independently evaluated without this assumption",
    }
    if objective_profile == "state_floor":
        report["checks"]["state_floor_mirror_assumption_pass"] = bool(mirror_pass)
    report["checks"]["signed_flux_closure_pass"] = report["measured_net_flux"]["closure_pass"]
    report["checks"]["propagating_mode_coverage_pass"] = report["propagating_mode_coverage"]["coverage_pass"]
    report["acceptance_pass"] = all(report["checks"].values())
    report["evidence_sha256"] = {name: item[1] for name, item in artifacts.items()}
    report["metrics_sha256"] = artifacts["metrics.csv"][1]
    report["native_configuration"] = plan["config"]
    report["S"] = complex_pairs(matrix)
    return report


def read_matrix(path: Path, guided_modes: int = 1) -> np.ndarray:
    sources = 4 * validate_guided_modes(guided_modes)
    cells: dict[tuple[int, int], complex] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            source, output = int(row["source"]), int(row["row"])
            if not 1 <= source <= sources or not 1 <= output <= sources or (output, source) in cells:
                raise ValueError("duplicate or invalid source-conditioned matrix entry")
            if int(row["source_solution_index"]) != source:
                raise ValueError("source/solution mapping mismatch")
            cells[output, source] = complex(float(row["real"]), float(row["imag"]))
    if len(cells) != sources * sources:
        raise ValueError(f"All {sources * sources} independently exported modal matrix entries are required")
    matrix = np.array([[cells[i, j] for j in range(1, sources + 1)] for i in range(1, sources + 1)])
    if not np.isfinite(matrix).all():
        raise ValueError("nonfinite matrix")
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--closure-tolerance", type=float, default=DEFAULT_CLOSURE_TOLERANCE)
    args = parser.parse_args()
    try:
        folder = args.run.resolve(strict=True)
        report = analyze(folder, args.closure_tolerance)
        encoded = json.dumps(report, indent=2, allow_nan=False)
        (folder / "verification.json").write_text(encoded + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "acceptance_pass",
                    "min_six_state_conditional_fidelity",
                    "conditional_choi_overlap",
                    "target_throughput_per_input",
                    "min_six_state_target_throughput",
                    "minimum_target_throughput_all_inputs",
                    "mirror_matrix_max_absolute_residual",
                    "both_input_split_ratios",
                    "checks",
                )
            },
            indent=2,
        )
    )
    return 0 if report["acceptance_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
