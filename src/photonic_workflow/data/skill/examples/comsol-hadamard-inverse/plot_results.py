"""Original scientific previews of a binary design and source-1 field.

Usage: python plot_results.py --run RUN_DIR --mask mask.json --output NEW_DIR
Triangular interpolation and coordinate averaging are for visualization only,
not evidence of mesh convergence, flux conservation, or gate acceptance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import numpy as np
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath


def load_json(path):
    def reject_constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def verified_inputs(run, mask_path):
    """Bind the displayed geometry/field to one run and reanalyze its raw data."""
    analyzer_path = Path(__file__).with_name("analyze.py")
    spec = importlib.util.spec_from_file_location("hadamard_preview_analyzer", analyzer_path)
    analyzer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(analyzer)
    receipt = load_json(run / "receipt.json")
    plan_path, _ = analyzer.checked_artifact(run, receipt, "plan.json")
    plan = load_json(plan_path)
    if plan["config"].get("mode") != "binary":
        raise ValueError("Binary mask previews require a binary native run")
    mask_bytes = mask_path.read_bytes()
    mask_sha256 = hashlib.sha256(mask_bytes).hexdigest()
    if plan.get("mask_sha256") != mask_sha256:
        raise ValueError("Displayed mask does not match the native run plan")
    _, field_sha256 = analyzer.checked_artifact(run, receipt, "field.txt")
    # verification.json is a derived convenience file, not trusted evidence.
    # Recompute using the shipped verifier and its unchanged default tolerances.
    report = analyzer.analyze(run)
    provenance = {
        "schema_version": 1,
        "scope": "Single-run binary preview; not multi-wavelength qualification",
        "mask_sha256": mask_sha256,
        "field_sha256": field_sha256,
        "receipt_sha256": hashlib.sha256((run / "receipt.json").read_bytes()).hexdigest(),
        "analyzer_sha256": hashlib.sha256(analyzer_path.read_bytes()).hexdigest(),
        "plotter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "raw_evidence_sha256": report["evidence_sha256"],
        "acceptance_pass": report["acceptance_pass"],
    }
    return json.loads(mask_bytes), report, provenance


def field_samples(path, *, display_half=None, solved_half=None):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["x_um", "y_um", "Hz_abs_squared_source1"]:
            raise ValueError("Expected source-1 field CSV header")
        values = np.asarray([[float(row[key]) for key in reader.fieldnames] for row in reader])
    if values.ndim != 2 or values.shape[1] != 3 or not np.isfinite(values[:, :2]).all():
        raise ValueError("Field samples need finite two-dimensional coordinates")
    if solved_half is not None:
        bounds = np.concatenate((np.min(values[:, :2], axis=0), np.max(values[:, :2], axis=0)))
        expected = [-solved_half, -solved_half, solved_half, solved_half]
        if not np.allclose(bounds, expected, rtol=0, atol=1e-8):
            raise ValueError("Field sample bounds do not match the solved domain")
    # Transformed PML fields can be undefined at stretch interfaces. They are
    # outside this physical display, and must never set its peak normalization.
    if display_half is not None:
        values = values[np.all(np.abs(values[:, :2]) <= display_half + 1e-8, axis=1)]
    if not np.isfinite(values).all() or np.any(values[:, 2] < 0):
        raise ValueError("Field samples must be finite, nonnegative Nx3 values")
    points, inverse = np.unique(values[:, :2], axis=0, return_inverse=True)
    intensities = np.bincount(inverse, weights=values[:, 2]) / np.bincount(inverse)
    if len(points) < 3 or np.linalg.matrix_rank(points - points[0]) < 2 or intensities.max() <= 0:
        raise ValueError("Need supported nonzero two-dimensional field samples")
    return points, intensities / intensities.max(), len(values) - len(points)


def display_field_samples(path, configuration):
    """Check solved-domain bounds, then crop and normalize inside slit planes."""
    outer_half = configuration["outer_half_um"]
    if isinstance(outer_half, bool) or not isinstance(outer_half, (int, float)) or not np.isfinite(outer_half):
        raise ValueError("native_configuration outer_half_um must be a finite number")
    if outer_half <= 0.65:
        raise ValueError("Port-reference planes must extend beyond the design square")
    solved_half = outer_half
    boundary = configuration.get("boundary_model", "exterior_modal")
    if boundary == "slit_pml":
        thickness = configuration["pml_thickness_um"]
        if isinstance(thickness, bool) or not isinstance(thickness, (int, float)) or not np.isfinite(thickness):
            raise ValueError("PML thickness must be finite")
        if thickness <= 0:
            raise ValueError("PML thickness must be positive")
        solved_half += 0.25 + thickness
    elif boundary != "exterior_modal":
        raise ValueError("Unsupported boundary model")
    points, normalized, duplicate_count = field_samples(path, display_half=outer_half, solved_half=solved_half)
    return points, normalized, duplicate_count, outer_half, solved_half


def polygon_path(polygon):
    vertices, codes = [], []
    for index, raw in enumerate([polygon["outer"], *polygon["holes"]]):
        ring = np.asarray(raw, dtype=float)
        if ring.ndim != 2 or ring.shape[1] != 2 or len(ring) < 3 or not np.isfinite(ring).all():
            raise ValueError("Invalid mask ring")
        if np.any(np.abs(ring) > 0.65 + 1e-12):
            raise ValueError("Mask ring lies outside the design square")
        area = np.sum(ring[:, 0] * np.roll(ring[:, 1], -1) - ring[:, 1] * np.roll(ring[:, 0], -1))
        # Nonzero winding fill: outer counterclockwise, hole clockwise.
        if (area > 0) != (index == 0):
            ring = ring[::-1]
        vertices.extend([*ring.tolist(), ring[0].tolist()])
        codes.extend([MplPath.MOVETO, *([MplPath.LINETO] * (len(ring) - 1)), MplPath.CLOSEPOLY])
    return MplPath(vertices, codes)


def geometry(ax, paths, extent, filled=False):
    xmin, xmax, ymin, ymax = extent
    if filled:
        for bounds in (
            (xmin, -0.2, -0.65 - xmin, 0.4),
            (0.65, -0.2, xmax - 0.65, 0.4),
            (-0.2, ymin, 0.4, -0.65 - ymin),
            (-0.2, 0.65, 0.4, ymax - 0.65),
        ):
            ax.add_patch(Rectangle(bounds[:2], *bounds[2:], facecolor="0.65", edgecolor="none"))
    for path in paths:
        ax.add_patch(
            PathPatch(
                path, facecolor="black" if filled else "none", edgecolor="black" if filled else "white", linewidth=0.5
            )
        )
    ax.add_patch(Rectangle((-0.65, -0.65), 1.3, 1.3, fill=False, edgecolor="tab:cyan", linewidth=1, linestyle="--"))
    ax.set(xlim=(xmin, xmax), ylim=(ymin, ymax), xlabel="x (um)", ylabel="y (um)", aspect="equal")


def metric_rows(report):
    pairs = [
        ("Minimum six-state conditional fidelity", report["min_six_state_conditional_fidelity"]),
        ("Conditional Choi overlap", report["conditional_choi_overlap"]),
        ("Input 1 / input 2 target throughput", report["target_throughput_per_input"]),
        ("Minimum six-state target throughput", report["min_six_state_target_throughput"]),
        ("Minimum target throughput over all logical inputs", report["minimum_target_throughput_all_inputs"]),
        ("Input 1 / input 2 split ratio", report["both_input_split_ratios"]),
        ("Observed S maximum singular value", report["observed_S"]["sigma_max"]),
        ("Reciprocity maximum absolute residual", report["observed_S"]["reciprocity_max_absolute_residual"]),
    ]
    rows = []
    for label, value in pairs:
        items = value if isinstance(value, list) else [value]
        if any(v is not None and (isinstance(v, bool) or not np.isfinite(v)) for v in items):
            raise ValueError("Invalid metric in verification report")
        rows.append((label, " / ".join("undefined" if v is None else f"{v:.6g}" for v in items)))
    return rows


def render(run, mask_path, output):
    if output.exists():
        raise ValueError("Output directory must be new")
    mask, report, provenance = verified_inputs(run, mask_path)
    if mask.get("units") != "um" or mask.get("design_bounds") != [-0.65, 0.65, -0.65, 0.65]:
        raise ValueError("Expected a 1.3 um square binary mask in um")
    accepted = report.get("acceptance_pass")
    if not isinstance(accepted, bool):
        raise ValueError("Verification report must explicitly declare boolean acceptance_pass")
    status = "PASS" if accepted else "FAIL"
    paths = [polygon_path(polygon) for polygon in mask["polygons"]]
    configuration = report["native_configuration"]
    wavelength = configuration["wavelength_nm"]
    points, normalized, duplicate_count, outer_half, solved_half = display_field_samples(
        run / "field.txt", configuration
    )
    xmin = ymin = -outer_half
    xmax = ymax = outer_half
    extent = (xmin, xmax, ymin, ymax)
    rows = metric_rows(report)
    checks = report.get("checks", {})
    if not isinstance(checks, dict) or any(not isinstance(v, bool) for v in checks.values()):
        raise ValueError("Verification checks must be boolean")
    triangulation = mtri.Triangulation(points[:, 0], points[:, 1])
    output.mkdir(parents=True, exist_ok=False)
    scope = "2D material-index surrogate"
    fig, ax = plt.subplots(figsize=(6, 6))
    geometry(ax, paths, extent, filled=True)
    ax.set_title(f"Binary design | single-run checks {status}\n{scope}, {wavelength:g} nm")
    positions = (
        (xmin + 0.45, 0.3, "Port 1\nsource"),
        (0.35, ymin + 0.18, "Port 2"),
        (0.35, ymax - 0.3, "Port 3"),
        (xmax - 0.4, 0.3, "Port 4"),
    )
    for x, y, label in positions:
        ax.text(x, y, label, fontsize=9, ha="center")
    ax.text(0, 0.78, "1.3 um design square", fontsize=9, ha="center")
    fig.text(0.5, 0.02, "Black: Si mask | white: clad | gray: fixed 400 nm access guides", ha="center", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(output / "design.png", dpi=200)
    plt.close(fig)
    for name, values, levels, label in (
        ("field_linear", normalized, np.linspace(0, 1, 101), r"$|H_z|^2 / \max |H_z|^2$"),
        (
            "field_db",
            10 * np.log10(np.maximum(normalized, 1e-4)),
            np.linspace(-40, 0, 101),
            "Normalized intensity (dB)",
        ),
    ):
        fig, ax = plt.subplots(figsize=(7, 6))
        image = ax.tricontourf(triangulation, values, levels=levels, cmap="magma")
        geometry(ax, paths, extent)
        ax.annotate(
            "Source 1: left",
            xy=(xmin + 0.02, 0),
            xytext=(xmin + 0.25, -0.8),
            color="cyan",
            arrowprops={"arrowstyle": "->", "color": "cyan"},
            fontsize=9,
        )
        ax.set_title(f"Source-1 field | single-run checks {status}\n{scope}, {wavelength:g} nm")
        colorbar = fig.colorbar(image, ax=ax, label=label)
        if name == "field_db":
            colorbar.set_ticks([-40, -30, -20, -10, 0])
        fig.text(
            0.5,
            0.015,
            "Duplicate-coordinate intensity means; triangular visualization only, not mesh/flux evidence.",
            ha="center",
            fontsize=7,
        )
        fig.tight_layout(rect=(0, 0.04, 1, 1))
        fig.savefig(output / f"{name}.png", dpi=200)
        plt.close(fig)
    table = [
        f"Single-run checks at {wavelength:g} nm: **{status}**",
        "",
        scope + "; " + report["observed_matrix_scope"],
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    table.extend(f"| {label} | {value} |" for label, value in rows)
    table.extend(
        ["", "Declared checks:"] + [f"- {key}: {'PASS' if value else 'FAIL'}" for key, value in checks.items()]
    )
    table.extend(
        [
            "",
            f"Duplicate field rows averaged inside the display window: {duplicate_count}.",
            f"Solved-domain half-width: {solved_half:g} um; display/port-plane half-width: {outer_half:g} um.",
            "PML/backing regions are cropped before display peak normalization; incident power is not inferred.",
            "Transformed PML sample values are excluded; every retained physical-window value must be finite.",
            "The displayed interpolated field is not mesh convergence, signed flux, or completeness evidence.",
            "Acceptance is freshly recomputed from receipt-bound raw data with the shipped verifier.",
            "The mask and field hashes match the native plan and receipt; see preview-receipt.json.",
            "A passing single run does not establish a passing multi-wavelength qualification campaign.",
        ]
    )
    (output / "metrics.md").write_text("\n".join(table) + "\n", encoding="utf-8")
    (output / "verification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    provenance["artifacts"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.iterdir()) if path.is_file()
    }
    (output / "preview-receipt.json").write_text(
        json.dumps(provenance, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        render(args.run, args.mask, args.output)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
