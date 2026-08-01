from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

import photonic_assembly


def write_two_port(path: Path, amplitude: float, wavelengths: tuple[float, ...] = (1540.0, 1550.0, 1560.0)) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=photonic_assembly.REQUIRED_COLUMNS)
        writer.writeheader()
        for wavelength in wavelengths:
            for out_port in ("o1", "o2"):
                for in_port in ("o1", "o2"):
                    value = amplitude if out_port != in_port else 0.0
                    writer.writerow(
                        {
                            "wavelength_nm": wavelength,
                            "out_port": out_port,
                            "in_port": in_port,
                            "s_real": value,
                            "s_imag": 0.0,
                        }
                    )


def write_directional_coupler(path: Path) -> None:
    ports = ("l1", "l2", "r1", "r2")
    coupling = 1 / math.sqrt(2)
    values = {
        ("r1", "l1"): complex(coupling, 0),
        ("r1", "l2"): complex(0, coupling),
        ("r2", "l1"): complex(0, coupling),
        ("r2", "l2"): complex(coupling, 0),
        ("l1", "r1"): complex(coupling, 0),
        ("l2", "r1"): complex(0, coupling),
        ("l1", "r2"): complex(0, coupling),
        ("l2", "r2"): complex(coupling, 0),
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=photonic_assembly.REQUIRED_COLUMNS)
        writer.writeheader()
        for out_port in ports:
            for in_port in ports:
                value = values.get((out_port, in_port), 0j)
                writer.writerow(
                    {
                        "wavelength_nm": 1550.0,
                        "out_port": out_port,
                        "in_port": in_port,
                        "s_real": value.real,
                        "s_imag": value.imag,
                    }
                )


def make_manifest(root: Path) -> Path:
    write_two_port(root / "a.csv", 0.9)
    write_two_port(root / "b.csv", 0.8)
    manifest = {
        "schema_version": "1.0",
        "conventions": {
            "wavelength_unit": "nm",
            "sparameter_normalization": "power-wave",
            "time_dependence": "exp(+iwt)",
        },
        "components": {
            "a": {
                "ports": ["o1", "o2"],
                "port_modes": {"o1": "TE0", "o2": "TE0"},
                "model_level": "reduced",
                "reference_plane": "component boundary",
                "sparameters": "a.csv",
                "passive": True,
            },
            "b": {
                "ports": ["o1", "o2"],
                "port_modes": {"o1": "TE0", "o2": "TE0"},
                "model_level": "reduced",
                "reference_plane": "component boundary",
                "sparameters": "b.csv",
                "passive": True,
            },
        },
        "instances": {"left": {"component": "a"}, "right": {"component": "b"}},
        "connections": [["left:o2", "right:o1"]],
        "external_ports": {"in": "left:o1", "out": "right:o2"},
    }
    path = root / "assembly.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


class PhotonicAssemblyTests(unittest.TestCase):
    def test_bundled_four_port_mzi_template(self) -> None:
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "templates"
            / "hierarchical-device"
            / "mzi-4port"
            / "circuits"
            / "assembly.json"
        )
        manifest, component_data = photonic_assembly.validate_manifest(manifest_path)
        rows, summary = photonic_assembly.compose(manifest, component_data)
        cross = next(
            row
            for row in rows
            if row["wavelength_nm"] == "1550"
            and row["out_port"] == "out_bottom"
            and row["in_port"] == "in_top"
        )
        through = next(
            row
            for row in rows
            if row["wavelength_nm"] == "1550"
            and row["out_port"] == "out_top"
            and row["in_port"] == "in_top"
        )
        self.assertEqual(summary["instance_count"], 4)
        self.assertEqual(summary["external_ports"], ["in_top", "in_bottom", "out_top", "out_bottom"])
        self.assertAlmostEqual(float(cross["power"]), 1.0, places=12)
        self.assertAlmostEqual(float(through["power"]), 0.0, places=12)

    def test_two_stage_cascade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = make_manifest(Path(temp_dir))
            manifest, component_data = photonic_assembly.validate_manifest(manifest_path)
            rows, summary = photonic_assembly.compose(manifest, component_data)
            forward = next(
                row
                for row in rows
                if row["wavelength_nm"] == "1550" and row["out_port"] == "out" and row["in_port"] == "in"
            )
            self.assertAlmostEqual(float(forward["s_real"]), 0.72, places=12)
            self.assertAlmostEqual(float(forward["power"]), 0.5184, places=12)
            self.assertEqual(summary["instance_count"], 2)

    def test_balanced_mzi_from_four_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_directional_coupler(root / "dc.csv")
            write_two_port(root / "arm.csv", 1.0, wavelengths=(1550.0,))
            manifest = {
                "schema_version": "1.0",
                "conventions": {
                    "wavelength_unit": "nm",
                    "sparameter_normalization": "power-wave",
                    "time_dependence": "exp(+iwt)",
                },
                "components": {
                    "dc": {
                        "ports": ["l1", "l2", "r1", "r2"],
                        "port_modes": {port: "TE0" for port in ("l1", "l2", "r1", "r2")},
                        "model_level": "analytic",
                        "reference_plane": "coupler access boundary",
                        "sparameters": "dc.csv",
                        "passive": True,
                    },
                    "arm": {
                        "ports": ["o1", "o2"],
                        "port_modes": {"o1": "TE0", "o2": "TE0"},
                        "model_level": "analytic",
                        "reference_plane": "arm boundary",
                        "sparameters": "arm.csv",
                        "passive": True,
                    },
                },
                "instances": {
                    "dc1": {"component": "dc"},
                    "top": {"component": "arm"},
                    "bottom": {"component": "arm"},
                    "dc2": {"component": "dc"},
                },
                "connections": [
                    ["dc1:r1", "top:o1"],
                    ["top:o2", "dc2:l1"],
                    ["dc1:r2", "bottom:o1"],
                    ["bottom:o2", "dc2:l2"],
                ],
                "external_ports": {
                    "in_top": "dc1:l1",
                    "in_bottom": "dc1:l2",
                    "out_top": "dc2:r1",
                    "out_bottom": "dc2:r2",
                },
            }
            path = root / "mzi.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            payload, component_data = photonic_assembly.validate_manifest(path)
            rows, _ = photonic_assembly.compose(payload, component_data)
            cross = next(row for row in rows if row["out_port"] == "out_bottom" and row["in_port"] == "in_top")
            through = next(row for row in rows if row["out_port"] == "out_top" and row["in_port"] == "in_top")
            self.assertAlmostEqual(float(cross["power"]), 1.0, places=12)
            self.assertAlmostEqual(float(through["power"]), 0.0, places=12)

    def test_mode_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = make_manifest(Path(temp_dir))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["components"]["b"]["port_modes"]["o1"] = "TM0"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(photonic_assembly.AssemblyError, "mode mismatch"):
                photonic_assembly.validate_manifest(manifest_path)

    def test_manifest_contract_rejects_ambiguous_or_unsafe_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = make_manifest(Path(temp_dir))
            baseline = json.loads(manifest_path.read_text(encoding="utf-8"))
            cases = {
                "is reused by": lambda payload: payload["external_ports"].update(
                    {"duplicate_in": "left:o1"}
                ),
                "non-empty strings": lambda payload: payload["components"]["a"]["port_modes"].update(
                    {"o1": ""}
                ),
                "relative to the manifest": lambda payload: payload["components"]["a"].update(
                    {"sparameters": str((Path(temp_dir) / "a.csv").resolve())}
                ),
                "must be a boolean": lambda payload: payload["components"]["a"].update(
                    {"passive": "yes"}
                ),
            }
            for expected, mutate in cases.items():
                with self.subTest(expected=expected):
                    payload = json.loads(json.dumps(baseline))
                    mutate(payload)
                    errors = photonic_assembly.validate_structure(payload)
                    self.assertTrue(any(expected in error for error in errors), errors)

    def test_non_finite_complex_entries_are_rejected_before_composition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = make_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["components"]["a"]["passive"] = False
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with (root / "a.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["s_real"] = "nan"
            with (root / "a.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=photonic_assembly.REQUIRED_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

            with self.assertRaisesRegex(photonic_assembly.AssemblyError, "non-finite"):
                photonic_assembly.validate_manifest(manifest_path)

    def test_sparameter_path_must_stay_below_manifest_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_dir = root / "manifest"
            manifest_dir.mkdir()
            manifest_path = make_manifest(manifest_dir)
            outside = root / "outside.csv"
            write_two_port(outside, 0.5)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["components"]["a"]["sparameters"] = "../outside.csv"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(photonic_assembly.AssemblyError, "outside manifest directory"):
                photonic_assembly.validate_manifest(manifest_path)


if __name__ == "__main__":
    unittest.main()
