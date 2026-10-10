"""Extract a binary square design from continuous filtered density samples.

Usage: python extract_mask.py density.txt --output NEW_DIRECTORY
The 5 nm interpolation grid resolves a threshold contour; it is not a
fabrication-error or mesh-convergence guarantee. No hole/bridge removal occurs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from itertools import pairwise
from pathlib import Path

import contourpy
import numpy as np
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import QhullError

BOUNDS = (-0.65, 0.65, -0.65, 0.65)
COLUMNS = ("x_um", "y_um", "theta_c", "theta_f", "rho")


def read_density(path: Path) -> tuple[np.ndarray, str]:
    """Read/hash the identical bytes; never select discontinuous theta_c."""
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    if reader.fieldnames != list(COLUMNS):
        raise ValueError("Expected density CSV columns: " + ",".join(COLUMNS))
    rows = []
    for row in reader:
        if set(row) != set(COLUMNS) or any(value is None for value in row.values()):
            raise ValueError("Malformed density CSV row")
        try:
            rows.append([float(row[key]) for key in COLUMNS])
        except (ValueError, TypeError) as error:
            raise ValueError("Density CSV contains a nonnumeric value") from error
    values = np.asarray(rows, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(COLUMNS) or not np.isfinite(values).all():
        raise ValueError("Density CSV must contain finite sample rows")
    return values, hashlib.sha256(raw).hexdigest()


def interpolate_density(values: np.ndarray, grid_spacing_um: float = 0.005):
    """Average theta_f at exact duplicate coordinates and require full support."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != 5 or not np.isfinite(values).all():
        raise ValueError("Samples must be a finite Nx5 density table")
    points = values[:, :2]
    if np.any(points < BOUNDS[0] - 1e-12) or np.any(points > BOUNDS[1] + 1e-12):
        raise ValueError("Density samples lie outside the fixed design bounds")
    # Native coordinate export can round a square edge by one floating-point ULP.
    points = np.clip(points, BOUNDS[0], BOUNDS[1])
    if not np.isfinite(grid_spacing_um) or grid_spacing_um <= 0:
        raise ValueError("Grid spacing must be positive and finite")
    intervals = round((BOUNDS[1] - BOUNDS[0]) / grid_spacing_um)
    if intervals < 1 or not np.isclose(intervals * grid_spacing_um, 1.3, rtol=0, atol=1e-12):
        raise ValueError("Grid spacing must divide the 1.3 um square")
    unique, inverse = np.unique(points, axis=0, return_inverse=True)
    filtered = np.bincount(inverse, weights=values[:, 3]) / np.bincount(inverse)
    if len(unique) < 3 or np.linalg.matrix_rank(unique - unique[0]) < 2:
        raise ValueError("Need noncollinear interpolation support")
    axis = np.linspace(BOUNDS[0], BOUNDS[1], intervals + 1)
    x, y = np.meshgrid(axis, axis)
    try:
        field = LinearNDInterpolator(unique, filtered)(x, y)
    except QhullError as error:
        raise ValueError("Invalid interpolation support") from error
    if not np.isfinite(field).all():
        raise ValueError("Interpolation support does not cover the full design square; no zero filling allowed")
    return axis, np.asarray(field)


def clean_ring(points: np.ndarray) -> list[list[float]]:
    """Remove only repeated and numerically collinear consecutive vertices."""
    ring = np.asarray(points, dtype=float)
    if ring.ndim != 2 or ring.shape[1] != 2 or not np.isfinite(ring).all():
        raise ValueError("Invalid contour ring")
    if np.any(ring < BOUNDS[0] - 1e-12) or np.any(ring > BOUNDS[1] + 1e-12):
        raise ValueError("Contour ring exceeds design bounds")
    # Roundoff clipping affects only points at the declared square boundary.
    ring = np.clip(ring, BOUNDS[0], BOUNDS[1])
    if len(ring) > 1 and np.array_equal(ring[0], ring[-1]):
        ring = ring[:-1]
    if len(ring):
        ring = ring[np.any(ring != np.roll(ring, 1, axis=0), axis=1)]
    while len(ring) >= 3:
        before = ring - np.roll(ring, 1, axis=0)
        after = np.roll(ring, -1, axis=0) - ring
        cross = before[:, 0] * after[:, 1] - before[:, 1] * after[:, 0]
        scale = np.linalg.norm(before, axis=1) * np.linalg.norm(after, axis=1)
        collinear = (np.abs(cross) <= 1e-14 * scale) & (np.sum(before * after, axis=1) >= 0)
        if not collinear.any():
            break
        ring = ring[~collinear]
    if len(ring) < 3:
        raise ValueError("Degenerate contour ring; no silent geometry deletion")
    area = np.sum(ring[:, 0] * np.roll(ring[:, 1], -1) - ring[:, 1] * np.roll(ring[:, 0], -1)) / 2
    if area == 0:
        raise ValueError("Contour ring has zero area")
    return ring.tolist()


def polygons_from_grid(axis: np.ndarray, field: np.ndarray, threshold: float = 0.5):
    """Extract OuterOffset rings: each polygon's first ring is its outer shell.

    Verified against installed contourpy 1.3.3 filled() docstring and primary
    convert._convert_filled_from_OuterOffset implementation: filled(level, inf)
    selects values above level; points are grouped per outer with offsets that
    delimit its shell and hole rings. No chunks are used.
    """
    axis = np.asarray(axis, dtype=float)
    field = np.asarray(field, dtype=float)
    if (
        axis.ndim != 1
        or len(axis) < 2
        or not np.isfinite(axis).all()
        or not np.all(np.diff(axis) > 0)
        or field.shape != (len(axis), len(axis))
        or not np.isfinite(field).all()
        or not np.isfinite(threshold)
    ):
        raise ValueError("Invalid contour grid or threshold")
    if axis[0] != BOUNDS[0] or axis[-1] != BOUNDS[1]:
        raise ValueError("Contour grid must cover the declared square")
    generator = contourpy.contour_generator(x=axis, y=axis, z=field, fill_type="OuterOffset")
    all_points, all_offsets = generator.filled(threshold, np.inf)
    polygons = []
    for points, offsets in zip(all_points, all_offsets, strict=True):
        rings = [clean_ring(points[start:end]) for start, end in pairwise(offsets)]
        if not rings:
            raise ValueError("Contour polygon has no outer ring")
        polygons.append({"outer": rings[0], "holes": rings[1:]})
    return polygons


def symmetry_projection(field: np.ndarray, symmetry: str):
    """Explicit orthogonal projection onto a declared x/y mirror constraint.

    Unstructured sample triangulation need not respect the native mirror, even
    when the underlying exported function does. This changes the reconstructed
    design field, not measured solver data. The resulting geometry needs its
    own full-wave verification; it is not an error bound on the native field.
    """
    field = np.asarray(field, dtype=float)
    if field.ndim != 2 or field.shape[0] != field.shape[1] or not np.isfinite(field).all():
        raise ValueError("Symmetry projection requires a finite square grid")
    if symmetry not in ("none", "mirror_xy"):
        raise ValueError("symmetry must be none or mirror_xy")
    before = float(np.max(np.abs(field - field.T)))
    projected = (field + field.T) / 2 if symmetry == "mirror_xy" else field.copy()
    return projected, {
        "constraint": symmetry,
        "method": "(theta_f(x,y)+theta_f(y,x))/2" if symmetry == "mirror_xy" else "identity",
        "max_mirror_residual_before": before,
        "max_mirror_residual_after": float(np.max(np.abs(projected - projected.T))),
        "max_absolute_field_change": float(np.max(np.abs(projected - field))),
        "scope": "Declared geometry reconstruction; not a bound on native field or device error",
    }


def extract(path: Path, threshold: float = 0.5, grid_spacing_um: float = 0.005, *, symmetry: str = "none"):
    if not np.isfinite(threshold) or not 0 < threshold < 1:
        raise ValueError("threshold must be finite and strictly between zero and one")
    samples, sha256 = read_density(path)
    axis, field = interpolate_density(samples, grid_spacing_um)
    field, symmetry_audit = symmetry_projection(field, symmetry)
    polygons = polygons_from_grid(axis, field, threshold)
    document = {
        "schema_version": 1,
        "units": "um",
        "design_bounds": list(BOUNDS),
        "threshold": threshold,
        "grid_spacing_um": grid_spacing_um,
        "inputSHA256": sha256,
        "density_quantity": "theta_f",
        "duplicate_coordinate_policy": "arithmetic mean of theta_f at exact duplicate coordinates",
        "symmetry_projection": symmetry_audit,
        "threshold_rule": "theta_f > threshold; equality contour is the polygon boundary",
        "polygons": polygons,
    }
    return document, axis, field


def previews(directory: Path, axis: np.ndarray, field: np.ndarray, threshold: float):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for name, values, title in (
        ("density", field, "Filtered density theta_f"),
        ("binary", field > threshold, "Binary contour preview"),
    ):
        fig, ax = plt.subplots(figsize=(5, 5))
        image = ax.pcolormesh(axis, axis, values, shading="nearest", cmap="gray", vmin=0, vmax=1)
        if name == "density":
            fig.colorbar(image, ax=ax, label="theta_f")
        ax.set(xlabel="x (um)", ylabel="y (um)", title=title, aspect="equal")
        fig.tight_layout()
        fig.savefig(directory / f"{name}.png", dpi=180)
        plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("density", type=Path)
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="binary geometry threshold; record calibrated values as design variables")
    parser.add_argument("--grid-spacing-um", type=float, default=0.005,
                        help="contour sampling step; must divide the 1.3 um square")
    parser.add_argument("--symmetry", choices=("none", "mirror_xy"), default="none",
                        help="explicit design constraint; mirror_xy restores the native Hadamard x/y symmetry")
    parser.add_argument("--output", type=Path, required=True, help="new directory; never overwrite")
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("Output directory must be new")
        document, axis, field = extract(args.density, args.threshold, args.grid_spacing_um, symmetry=args.symmetry)
        encoded = json.dumps(document, indent=2, allow_nan=False)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "mask.json").write_text(encoded + "\n", encoding="utf-8")
        previews(args.output, axis, field, document["threshold"])
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
