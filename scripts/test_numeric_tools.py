from __future__ import annotations

import importlib.util
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


SCRIPT_DIR = Path(__file__).resolve().parent


def load_script(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SWEEP = load_script("parse_comsol_sweep", "parse-comsol-sweep.py")
BEND = load_script("emit_analytic_bend_java_helper", "emit-analytic-bend-java-helper.py")


def spectral_row(wavelength_nm: float, t21: float) -> dict[str, float]:
    return {
        "freq_GHz": 0.0,
        "lambda_nm": wavelength_nm,
        "S11": 0.0,
        "T21": t21,
        "T21_dB": -math.inf if t21 <= 0.0 else 10.0 * math.log10(t21),
        "S11_plus_T21": t21,
    }


class SweepSummaryTests(unittest.TestCase):
    def test_fsr_is_positive_and_identical_for_ascending_and_descending_input(self) -> None:
        rows = [
            spectral_row(1500.0, 0.0),
            spectral_row(1510.0, 1.0),
            spectral_row(1520.0, 0.0),
            spectral_row(1530.0, 0.0),
            spectral_row(1540.0, 0.8),
            spectral_row(1550.0, 0.0),
        ]
        ascending = SWEEP.summary_row("ascending", rows, 0.1)
        descending = SWEEP.summary_row("descending", list(reversed(rows)), 0.1)

        self.assertEqual(ascending["peak_lambdas_nm"], "1510.00000|1540.00000")
        self.assertEqual(ascending["peak_spacings_nm"], "30.00000")
        self.assertEqual(descending["peak_lambdas_nm"], ascending["peak_lambdas_nm"])
        self.assertEqual(descending["peak_spacings_nm"], ascending["peak_spacings_nm"])

    def test_flat_top_peak_is_counted_once_at_endpoint_midpoint(self) -> None:
        rows = [
            spectral_row(1500.0, 0.0),
            spectral_row(1510.0, 1.0),
            spectral_row(1520.0, 1.0),
            spectral_row(1530.0, 0.0),
            spectral_row(1540.0, 0.8),
            spectral_row(1550.0, 0.0),
        ]
        summary = SWEEP.summary_row("plateau", rows, 0.1)

        self.assertEqual(summary["peak_lambdas_nm"], "1515.00000|1540.00000")
        self.assertEqual(summary["peak_T21s"], "1.000000|0.800000")
        self.assertEqual(summary["peak_spacings_nm"], "25.00000")

    def test_all_zero_trace_and_zero_peak_never_emit_nan_or_divide_by_zero(self) -> None:
        all_zero = [spectral_row(1500.0 + 10.0 * i, 0.0) for i in range(5)]
        summary = SWEEP.summary_row("zero", all_zero, 0.0)
        self.assertEqual(summary["peak_lambdas_nm"], "")
        self.assertEqual(summary["weak_strong_ratio"], "")
        self.assertNotIn("nan", repr(summary).lower())

        zero_peak = [spectral_row(1500.0, -0.1), spectral_row(1510.0, 0.0), spectral_row(1520.0, -0.1)]
        zero_peak_summary = SWEEP.summary_row("zero-peak", zero_peak, 0.0)
        self.assertEqual(zero_peak_summary["peak_lambdas_nm"], "1510.00000")
        self.assertEqual(zero_peak_summary["weak_strong_ratio"], "")
        self.assertNotIn("nan", repr(zero_peak_summary).lower())

        with tempfile.TemporaryDirectory() as temp_dir:
            table = Path(temp_dir) / "zero.txt"
            table.write_text("195.0 1.500 0.0 0.0\n194.0 1.510 0.0 0.0\n", encoding="utf-8")
            parsed = SWEEP.parse_table(table)
        self.assertTrue(all(not math.isnan(row["T21_dB"]) for row in parsed))

    def test_non_finite_primary_values_and_thresholds_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            table = Path(temp_dir) / "nonfinite.txt"
            table.write_text("195.0 1.500 0.0 nan\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite primary"):
                SWEEP.parse_table(table)
        with self.assertRaisesRegex(ValueError, "peak_threshold must be finite"):
            SWEEP.summary_row("bad-threshold", [spectral_row(1500.0, 1.0)], math.nan)


class CircularBendTests(unittest.TestCase):
    def assert_bend(self, angle_deg: float, radius: float) -> dict[str, object]:
        length = 20.0
        angle = math.radians(angle_deg)
        result = BEND.compute_circular_bend(
            (-length, 0.0),
            (0.0, 0.0),
            (length * math.cos(angle), length * math.sin(angle)),
            radius,
        )
        expected_cutback = radius * math.tan(0.5 * abs(angle))
        self.assertAlmostEqual(result["cutback"], expected_cutback, places=12)
        self.assertEqual(result["radius"], radius)
        center = result["center"]
        for tangent_key in ("t1", "t2"):
            tangent = result[tangent_key]
            distance = math.hypot(tangent[0] - center[0], tangent[1] - center[1])
            self.assertAlmostEqual(distance, radius, places=12)
        self.assertAlmostEqual(result["a1"] - result["a0"], angle, places=12)
        return result

    def test_60_degree_turn_uses_angle_dependent_cutback(self) -> None:
        result = self.assert_bend(60.0, 3.0)
        self.assertAlmostEqual(result["cutback"], math.sqrt(3.0), places=12)

    def test_90_degree_turn_uses_one_radius_cutback(self) -> None:
        result = self.assert_bend(90.0, 3.0)
        self.assertAlmostEqual(result["cutback"], 3.0, places=12)

    def test_obtuse_turn_preserves_requested_radius(self) -> None:
        result = self.assert_bend(120.0, 3.0)
        self.assertAlmostEqual(result["cutback"], 3.0 * math.sqrt(3.0), places=12)

    def test_degenerate_and_unconstructible_corners_fail_clearly(self) -> None:
        cases = [
            (((0.0, 0.0), (0.0, 0.0), (1.0, 0.0), 1.0), "zero-length"),
            (((-1.0, 0.0), (0.0, 0.0), (1.0, 1e-12), 1.0), "close to 0"),
            (((-1.0, 0.0), (0.0, 0.0), (-1.0, 1e-12), 1.0), "close to 180"),
            (((-1.0, 0.0), (0.0, 0.0), (0.0, 1.0), 2.0), "does not fit"),
        ]
        for args, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                BEND.compute_circular_bend(*args)

    def test_emitted_java_uses_same_cutback_and_never_clamps_radius(self) -> None:
        self.assertIn("radius * Math.tan(0.5 * absTurn)", BEND.HELPER)
        self.assertNotIn("Math.min(radius", BEND.HELPER)
        self.assertIn("tangent points do not lie on the requested-radius circle", BEND.HELPER)


if __name__ == "__main__":
    unittest.main()
