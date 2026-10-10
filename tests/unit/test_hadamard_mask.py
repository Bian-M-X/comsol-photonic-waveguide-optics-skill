import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse/extract_mask.py"
SPEC = importlib.util.spec_from_file_location("hadamard_mask_example", SCRIPT)
mask = None
if all(importlib.util.find_spec(name) is not None for name in ("scipy", "contourpy", "matplotlib")):
    mask = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(mask)


def samples(value):
    return np.array([[x, y, 0.9, value, 0.1] for x in (-0.65, 0.65) for y in (-0.65, 0.65)])


@unittest.skipIf(mask is None, "mask example requires the inverse-design optional dependencies")
class MaskTests(unittest.TestCase):
    def test_uniform_empty_full_and_equality(self):
        for density, expected in ((0.2, 0), (0.8, 1), (0.5, 0)):
            axis, field = mask.interpolate_density(samples(density))
            polygons = mask.polygons_from_grid(axis, field)
            self.assertEqual(len(polygons), expected)
            if expected:
                self.assertEqual(polygons[0]["holes"], [])
                self.assertEqual(len(polygons[0]["outer"]), 4)
                self.assertEqual(
                    {tuple(p) for p in polygons[0]["outer"]},
                    {(-0.65, -0.65), (-0.65, 0.65), (0.65, -0.65), (0.65, 0.65)},
                )

    def test_solid_with_hole(self):
        axis = np.linspace(-0.65, 0.65, 261)
        x, y = np.meshgrid(axis, axis)
        field = np.minimum(1.0, (x * x + y * y) / 0.04)
        polygons = mask.polygons_from_grid(axis, field)
        self.assertEqual(len(polygons), 1)
        self.assertEqual(len(polygons[0]["holes"]), 1)
        for ring in [polygons[0]["outer"], *polygons[0]["holes"]]:
            self.assertGreaterEqual(len(ring), 3)
            self.assertNotEqual(ring[0], ring[-1])
            self.assertTrue(np.isfinite(ring).all())
            self.assertTrue((np.abs(ring) <= 0.65).all())
        self.assertTrue((np.abs(polygons[0]["holes"][0]) < 0.21).all())

    def test_duplicate_filtered_averaging(self):
        original = samples(0.2)
        duplicate = samples(0.8)
        axis, field = mask.interpolate_density(np.vstack((original, duplicate)))
        self.assertTrue(np.allclose(field, 0.5))
        self.assertEqual(len(axis), 261)

    def test_mirror_projection_is_explicit_symmetric_and_minimum_change(self):
        field = np.array([[0.1, 0.2, 0.8], [0.7, 0.5, 0.4], [0.3, 0.9, 0.6]])
        unchanged, audit = mask.symmetry_projection(field, "none")
        np.testing.assert_array_equal(unchanged, field)
        self.assertEqual(audit["max_absolute_field_change"], 0)
        projected, audit = mask.symmetry_projection(field, "mirror_xy")
        np.testing.assert_array_equal(projected, projected.T)
        self.assertAlmostEqual(audit["max_absolute_field_change"], audit["max_mirror_residual_before"] / 2)
        self.assertEqual(audit["max_mirror_residual_after"], 0)
        # The removed antisymmetric component is orthogonal to any symmetric
        # perturbation: the Frobenius least-change property is observable.
        alternative = projected + np.array([[0.1, 0.2, 0.3], [0.2, 0.4, 0.5], [0.3, 0.5, 0.6]])
        self.assertAlmostEqual(
            np.linalg.norm(field - alternative) ** 2,
            np.linalg.norm(field - projected) ** 2 + np.linalg.norm(projected - alternative) ** 2,
        )
        again, _ = mask.symmetry_projection(projected, "mirror_xy")
        np.testing.assert_array_equal(again, projected)
        with self.assertRaises(ValueError):
            mask.symmetry_projection(field, "unknown")

    def test_mirror_contour_preserves_asymmetric_input_constraint(self):
        from matplotlib.path import Path as PlotPath

        axis = np.linspace(-0.65, 0.65, 131)
        x, y = np.meshgrid(axis, axis)
        field = 0.7 - ((x - 0.15) ** 2 + 2 * (y + 0.12) ** 2)
        field, _ = mask.symmetry_projection(field, "mirror_xy")
        polygons = mask.polygons_from_grid(axis, field)
        # Check the exported rings, not only the input array. Off-grid points
        # avoid accidental boundary classification differences.
        query_axis = np.linspace(-0.6461, 0.6461, 108)
        qx, qy = np.meshgrid(query_axis, query_axis)
        query = np.column_stack((qx.ravel(), qy.ravel()))
        inside = np.zeros(len(query), dtype=bool)
        for polygon in polygons:
            region = PlotPath(polygon["outer"]).contains_points(query)
            for ring in polygon["holes"]:
                region &= ~PlotPath(ring).contains_points(query)
            inside |= region
        inside = inside.reshape(qx.shape)
        np.testing.assert_array_equal(inside, inside.T)

    def test_native_boundary_roundoff_is_not_a_geometry_change(self):
        original = samples(0.8)
        original[:, :2] = np.nextafter(original[:, :2], np.sign(original[:, :2]) * np.inf)
        _, field = mask.interpolate_density(original)
        self.assertTrue(np.allclose(field, 0.8))

    def test_invalid_bounds_nonfinite_and_support(self):
        invalid = samples(0.2)
        invalid[0, 0] = -0.65000001
        nonfinite = samples(0.2)
        nonfinite[0, 3] = np.nan
        for data in (invalid, nonfinite, samples(0.2)[:3], np.zeros((4, 5)), np.zeros((4, 4))):
            with self.assertRaises(ValueError):
                mask.interpolate_density(data)
        with self.assertRaises(ValueError):
            mask.interpolate_density(samples(0.2), 0.006)
        with self.assertRaises(ValueError):
            mask.polygons_from_grid(np.linspace(-0.65, 0.65, 5), np.full((5, 5), np.inf))

    def test_clean_only_duplicates_and_collinear(self):
        ring = [[-0.65, -0.65], [0, -0.65], [0, -0.65], [0.65, -0.65], [0.65, 0.65], [-0.65, 0.65], [-0.65, -0.65]]
        self.assertEqual(len(mask.clean_ring(ring)), 4)
        with self.assertRaises(ValueError):
            mask.clean_ring([[0, 0], [0.1, 0], [0.2, 0]])

    def test_cli_public_safe_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = directory / "density.txt"
            source.write_text(
                "x_um,y_um,theta_c,theta_f,rho\n" + "\n".join(",".join(map(str, row)) for row in samples(0.8)),
                encoding="utf-8",
            )
            output = directory / "new-mask"
            command = [sys.executable, str(SCRIPT), str(source), "--output", str(output)]
            proc = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            raw = (output / "mask.json").read_text(encoding="utf-8")
            document = json.loads(raw)
            self.assertEqual(document["schema_version"], 1)
            self.assertEqual(document["units"], "um")
            self.assertEqual(document["design_bounds"], [-0.65, 0.65, -0.65, 0.65])
            self.assertEqual(document["density_quantity"], "theta_f")
            self.assertNotIn(str(source), raw)
            self.assertEqual(len(document["inputSHA256"]), 64)
            for name in ("density.png", "binary.png"):
                self.assertGreater((output / name).stat().st_size, 0)
            proc = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
            self.assertNotEqual(proc.returncode, 0)

    def test_csv_invalid(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.txt"
            for body in (
                "wrong,header\n1,2",
                "x_um,y_um,theta_c,theta_f,rho\n0,0,0,nan,0",
                "x_um,y_um,theta_c,theta_f,rho\n0,0,0,0",
                "x_um,y_um,theta_c,theta_f,rho\n",
            ):
                path.write_text(body, encoding="utf-8")
                with self.assertRaises(ValueError):
                    mask.read_density(path)


if __name__ == "__main__":
    unittest.main()
