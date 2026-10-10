import hashlib
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse/analyze.py"
SPEC = importlib.util.spec_from_file_location("hadamard_analysis_example", SCRIPT)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


def refresh_receipt(folder):
    receipt = {
        "completed": True,
        "artifacts": {
            name: {"sha256": hashlib.sha256((folder / name).read_bytes()).hexdigest()}
            for name in ("plan.json", "metrics.csv", "power.csv", "console.log")
        },
    }
    (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


def fixture(folder, guided_modes=1, matrix=None, boundary_model=None, objective_profile=None, incoming=None):
    config = {
        "mode": "binary",
        "guided_modes": guided_modes,
        "eps_core": 4 if guided_modes == 1 else 12.1,
        "eps_clad": 2.1,
    }
    if boundary_model is not None:
        config["boundary_model"] = boundary_model
    if objective_profile is not None:
        config["objective_profile"] = objective_profile
    (folder / "plan.json").write_text(
        json.dumps({"config": config}),
        encoding="utf-8",
    )
    if boundary_model == "slit_pml":
        incoming = np.eye(8, dtype=complex) if incoming is None else incoming
        console = [analysis.INTERIOR_BOUNDARY_MARKER, analysis.PML_CONFIGURATION_MARKER, analysis.SLIT_PORTS_MARKER]
        console += [
            f"{analysis.INCOMING_PREFIX}{source},{row},{incoming[row - 1, source - 1].real},"
            f"{incoming[row - 1, source - 1].imag}"
            for source in range(1, 9) for row in range(1, 9)
        ]
    else:
        console = [analysis.BOUNDARY_MARKER]
    (folder / "console.log").write_text("\n".join(console) + "\n", encoding="utf-8")
    b = np.array([[1, 1j], [1j, 1]]) / np.sqrt(2)
    s = np.zeros((4 * guided_modes, 4 * guided_modes), complex)
    s[2:4, :2] = b
    s[:2, 2:4] = b.T
    if guided_modes == 2:
        s[4:, 4:] = np.eye(4)
    if matrix is not None:
        s = matrix
    lines = ["source,row,source_solution_index,real,imag"]
    powers = [",".join(analysis.POWER_COLUMNS)]
    for source in range(1, len(s) + 1):
        for row in range(1, len(s) + 1):
            z = s[row - 1, source - 1]
            lines.append(f"{source},{row},{source},{z.real},{z.imag}")
        net = np.array([np.sum(abs(s[port::4, source - 1]) ** 2) for port in range(4)])
        net[(source - 1) % 4] -= 1
        outward = -sum(net)
        powers.append(",".join(map(str, [source, *net, outward, 0])))
    (folder / "metrics.csv").write_text("\n".join(lines), encoding="utf-8")
    (folder / "power.csv").write_text("\n".join(powers), encoding="utf-8")
    refresh_receipt(folder)
    return s


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        fixture(self.folder)

    def test_ideal_matrix_and_closed_flux(self):
        report = analysis.analyze(self.folder)
        self.assertTrue(report["acceptance_pass"])
        self.assertTrue(report["matrix_acceptance_pass"])
        self.assertEqual(report["measured_net_flux"]["closure_absolute_tolerance"], 0.005)
        self.assertEqual(len(report["measured_net_flux"]["sources"]), 4)
        self.assertIn("evaluated against", report["claim_label"])
        json.dumps(report, allow_nan=False)

    def test_closed_exterior_does_not_claim_modal_flux_agreement(self):
        path = self.folder / "power.csv"
        rows = path.read_text().splitlines()
        row = rows[1].split(",")
        row[1] = str(float(row[1]) + .1)
        row[2] = str(float(row[2]) - .1)
        rows[1] = ",".join(row)
        path.write_text("\n".join(rows))
        refresh_receipt(self.folder)
        report = analysis.analyze(self.folder)
        flux = report["measured_net_flux"]
        self.assertTrue(flux["closure_pass"])
        self.assertIn("closure only", flux["scope"])
        self.assertAlmostEqual(flux["sources"][0]["net_minus_observed_modal_expectation_unresolved_difference"][0], .1)
        self.assertAlmostEqual(report["min_six_state_target_throughput"], 1)

    def test_tamper_each_required_artifact(self):
        for name in ("plan.json", "metrics.csv", "power.csv", "console.log"):
            with self.subTest(name=name):
                fixture(self.folder)
                with (self.folder / name).open("a", encoding="utf-8") as stream:
                    stream.write(" ")
                with self.assertRaisesRegex(ValueError, "receipt"):
                    analysis.analyze(self.folder)

    def test_missing_power(self):
        (self.folder / "power.csv").unlink()
        with self.assertRaises(OSError):
            analysis.analyze(self.folder)

    def test_unclosed_flux_cannot_pass_ideal_matrix(self):
        path = self.folder / "power.csv"
        rows = path.read_text().splitlines()
        row = rows[1].split(",")
        row[-2], row[-1] = "0.02", "0.02"
        rows[1] = ",".join(row)
        path.write_text("\n".join(rows))
        refresh_receipt(self.folder)
        report = analysis.analyze(self.folder)
        self.assertTrue(report["matrix_acceptance_pass"])
        self.assertFalse(report["acceptance_pass"])
        self.assertFalse(report["checks"]["signed_flux_closure_pass"])

    def test_false_reported_closure_rejected(self):
        path = self.folder / "power.csv"
        rows = path.read_text().splitlines()
        row = rows[1].split(",")
        row[-2], row[-1] = "0.02", "0"
        rows[1] = ",".join(row)
        path.write_text("\n".join(rows))
        refresh_receipt(self.folder)
        with self.assertRaisesRegex(ValueError, "sum"):
            analysis.analyze(self.folder)

    def test_source_order_missing_duplicate(self):
        path = self.folder / "power.csv"
        original = path.read_text().splitlines()
        for rows in (
            original[:1] + original[2:3] + original[1:2] + original[3:],
            original[:2] + original[1:2] + original[3:],
            original[:-1],
        ):
            path.write_text("\n".join(rows))
            refresh_receipt(self.folder)
            with self.assertRaises(ValueError):
                analysis.analyze(self.folder)

    def test_boundary_missing_or_duplicate_fails_closed(self):
        for console in ("", (analysis.BOUNDARY_MARKER + "\n") * 2):
            (self.folder / "console.log").write_text(console)
            refresh_receipt(self.folder)
            report = analysis.analyze(self.folder)
            self.assertTrue(report["matrix_acceptance_pass"])
            self.assertFalse(report["acceptance_pass"])

    def test_nonfinite_power_and_policy(self):
        path = self.folder / "power.csv"
        path.write_text(path.read_text().replace("-1.0", "nan", 1))
        refresh_receipt(self.folder)
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            analysis.analyze(self.folder)
        for value in (float("nan"), -1, True):
            with self.assertRaises(ValueError):
                analysis.analyze(self.folder, value)

    def test_eight_modal_sources_success(self):
        fixture(self.folder, guided_modes=2)
        report = analysis.analyze(self.folder)
        self.assertTrue(report["acceptance_pass"])
        self.assertEqual(report["observed_modal_port_count"], 8)
        self.assertEqual(report["guided_modes_per_physical_port"], 2)
        self.assertEqual(len(report["declared_modal_basis"]), 8)
        self.assertEqual(report["declared_modal_basis"][4]["physical_location"], "left")
        self.assertEqual(report["declared_modal_basis"][4]["mode"], "TM1")
        self.assertEqual(report["measured_net_flux"]["sources"][4]["source_physical_port"], 1)
        self.assertEqual(len(report["measured_net_flux"]["sources"]), 8)

    def test_eight_modal_wrong_solution_mapping_and_missing_odd_column(self):
        path = self.folder / "metrics.csv"
        fixture(self.folder, guided_modes=2)
        original = path.read_text().splitlines()
        mapped = original.copy()
        row = mapped[-1].split(",")
        row[2] = "7"
        mapped[-1] = ",".join(row)
        path.write_text("\n".join(mapped))
        refresh_receipt(self.folder)
        with self.assertRaisesRegex(ValueError, "mapping"):
            analysis.analyze(self.folder)
        path.write_text("\n".join(line for line in original if not line.startswith("8,")))
        refresh_receipt(self.folder)
        with self.assertRaisesRegex(ValueError, "64"):
            analysis.analyze(self.folder)

    def test_grouped_modal_flux_leakage_and_unresolved_difference(self):
        matrix = fixture(self.folder, guided_modes=2) * 0.95
        matrix[4:, 4:] = 0.5 * np.eye(4)
        matrix[4, 0] = matrix[0, 4] = 0.05
        fixture(self.folder, guided_modes=2, matrix=matrix)
        path = self.folder / "power.csv"
        rows = path.read_text().splitlines()
        row = rows[5].split(",")  # Source 5: TM1 at physical left.
        row[4] = str(float(row[4]) + 0.0002)
        row[-1] = "0.0002"
        rows[5] = ",".join(row)
        path.write_text("\n".join(rows))
        refresh_receipt(self.folder)
        report = analysis.analyze(self.folder)
        first = report["measured_net_flux"]["sources"][0]
        odd = report["measured_net_flux"]["sources"][4]
        self.assertAlmostEqual(first["observed_modal_outward_power_per_physical_port"][0], 0.0025)
        self.assertTrue(np.allclose(first["net_minus_observed_modal_expectation_unresolved_difference"], 0))
        self.assertAlmostEqual(odd["net_port_flux"][0], 0.0025 + 0.25 - 1)
        self.assertAlmostEqual(odd["net_minus_observed_modal_expectation_unresolved_difference"][3], 0.0002)
        self.assertIn("not assigned", report["measured_net_flux"]["interpretation"])

    def test_guided_mode_count_and_missing_odd_power_rejected(self):
        for value in (True, 0, 3, 2.0, "2"):
            with self.assertRaises(ValueError):
                analysis.read_matrix(self.folder / "metrics.csv", value)
        fixture(self.folder, guided_modes=2)
        path = self.folder / "power.csv"
        path.write_text("\n".join(path.read_text().splitlines()[:-1]))
        refresh_receipt(self.folder)
        with self.assertRaisesRegex(ValueError, "8 source"):
            analysis.analyze(self.folder)

    def test_default_material_four_channel_false_positive_blocked(self):
        path = self.folder / "plan.json"
        path.write_text(json.dumps({"config": {"mode": "binary", "guided_modes": 1}}))
        refresh_receipt(self.folder)
        report = analysis.analyze(self.folder)
        self.assertTrue(report["matrix_acceptance_pass"])
        self.assertTrue(report["checks"]["signed_flux_closure_pass"])
        self.assertFalse(report["acceptance_pass"])
        self.assertFalse(report["checks"]["propagating_mode_coverage_pass"])
        self.assertEqual(report["propagating_mode_coverage"]["expected_bound_modes_per_physical_port"], 2)

    def test_slab_coverage_cutoff_and_invalid_physics(self):
        cutoff_nm = 2 * 400 * math.sqrt(12.1 - 2.1)
        at_cutoff = analysis.modal_coverage({"wavelength_nm": cutoff_nm}, 1)
        self.assertEqual(at_cutoff["expected_bound_modes_per_physical_port"], 1)
        below_cutoff = analysis.modal_coverage({"wavelength_nm": cutoff_nm * (1 - 1e-6)}, 1)
        self.assertEqual(below_cutoff["expected_bound_modes_per_physical_port"], 2)
        for config in ({"eps_core": True}, {"eps_core": 2.1}, {"wavelength_nm": 0}, {"eps_clad": float("nan")}):
            with self.assertRaises(ValueError):
                analysis.modal_coverage(config, 1)

    def test_pml_full_raw_basis_and_interior_flux_success(self):
        incoming = np.eye(8, dtype=complex)
        incoming[2, 5] = 0.003j
        matrix = fixture(self.folder, guided_modes=2, boundary_model="slit_pml", incoming=incoming)
        report = analysis.analyze(self.folder)
        self.assertTrue(report["acceptance_pass"])
        evidence = report["modal_incoming_evidence"]
        self.assertEqual(evidence["B"][2][5], [0, 0.003])
        self.assertEqual(evidence["B_minus_identity"][0][0], [0, 0])
        self.assertAlmostEqual(evidence["max_absolute_identity_residual"], .003)
        self.assertAlmostEqual(evidence["operator_norm_identity_residual"], .003)
        self.assertAlmostEqual(evidence["max_offdiagonal_amplitude"], .003)
        self.assertEqual(report["S"], analysis.complex_pairs(matrix))
        self.assertIn("no fitting, inversion, or renormalization", evidence["interpretation"])
        self.assertIn("nominal 1 W/m", report["raw_export_amplitude_scope"])
        self.assertIn("source-free interior", report["measured_net_flux"]["scope"])
        self.assertNotIn("exterior_boundary_partition_pass", report["checks"])
        self.assertEqual(report["boundary_evidence"]["required_console_marker"], analysis.INTERIOR_BOUNDARY_MARKER)
        json.dumps(report, allow_nan=False)

    def test_pml_markers_exactly_once_and_exterior_cannot_substitute(self):
        required = (analysis.INTERIOR_BOUNDARY_MARKER, analysis.PML_CONFIGURATION_MARKER, analysis.SLIT_PORTS_MARKER)
        for marker in required:
            for mutation in ("missing", "duplicate", "false", "whitespace"):
                with self.subTest(marker=marker, mutation=mutation):
                    fixture(self.folder, guided_modes=2, boundary_model="slit_pml")
                    path = self.folder / "console.log"
                    console = path.read_text()
                    if mutation == "missing":
                        console = console.replace(marker + "\n", "")
                    elif mutation == "duplicate":
                        console += marker + "\n"
                    elif mutation == "false":
                        console = console.replace(marker, marker.replace("true", "false"))
                    else:
                        console = console.replace(marker, marker + " ")
                    console += analysis.BOUNDARY_MARKER + "\n"
                    path.write_text(console)
                    refresh_receipt(self.folder)
                    report = analysis.analyze(self.folder)
                    self.assertTrue(report["matrix_acceptance_pass"])
                    self.assertFalse(report["acceptance_pass"])

    def test_pml_requires_eight_channels(self):
        fixture(self.folder, boundary_model="slit_pml")
        with self.assertRaisesRegex(ValueError, "eight-channel"):
            analysis.analyze(self.folder)

    def test_pml_incoming_missing_duplicate_invalid_and_nonfinite_rejected(self):
        mutations = {
            "missing": lambda rows: rows[:-1],
            "all_missing": lambda rows: [row for row in rows if not row.startswith(analysis.INCOMING_PREFIX)],
            "duplicate": lambda rows: [*rows, rows[-1]],
            "source_out_of_range": lambda rows: [*rows[:-1], "MODAL_INCOMING=9,8,1,0"],
            "row_out_of_range": lambda rows: [*rows[:-1], "MODAL_INCOMING=8,0,1,0"],
            "noninteger": lambda rows: [*rows[:-1], "MODAL_INCOMING=8.0,8,1,0"],
            "malformed": lambda rows: [*rows[:-1], "MODAL_INCOMING=8,8,1"],
            "extra_field": lambda rows: [*rows[:-1], "MODAL_INCOMING=8,8,1,0,extra"],
            "nan": lambda rows: [*rows[:-1], "MODAL_INCOMING=8,8,nan,0"],
            "infinite_imaginary": lambda rows: [*rows[:-1], "MODAL_INCOMING=8,8,1,inf"],
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                fixture(self.folder, guided_modes=2, boundary_model="slit_pml")
                path = self.folder / "console.log"
                path.write_text("\n".join(mutate(path.read_text().splitlines())))
                refresh_receipt(self.folder)
                with self.assertRaisesRegex(ValueError, "MODAL_INCOMING"):
                    analysis.analyze(self.folder)

    def test_pml_incoming_amplitude_gate_no_normalization(self):
        for value, passed in ((.005, True), (.005001, False)):
            with self.subTest(value=value):
                incoming = np.eye(8, dtype=complex)
                incoming[0, 7] = value
                matrix = fixture(self.folder, guided_modes=2, boundary_model="slit_pml", incoming=incoming)
                report = analysis.analyze(self.folder)
                self.assertTrue(report["matrix_acceptance_pass"])
                self.assertEqual(report["acceptance_pass"], passed)
                self.assertEqual(report["checks"]["modal_incoming_normalization_pass"], passed)
                self.assertEqual(report["S"], analysis.complex_pairs(matrix))
        incoming = np.eye(8, dtype=complex) + np.full((8, 8), .001)
        fixture(self.folder, guided_modes=2, boundary_model="slit_pml", incoming=incoming)
        evidence = analysis.analyze(self.folder)["modal_incoming_evidence"]
        self.assertLess(evidence["max_absolute_identity_residual"], .005)
        self.assertAlmostEqual(evidence["operator_norm_identity_residual"], .008)
        self.assertFalse(evidence["normalization_pass"])

    def test_pml_console_receipt_binds_incoming(self):
        fixture(self.folder, guided_modes=2, boundary_model="slit_pml")
        path = self.folder / "console.log"
        path.write_text(path.read_text().replace("MODAL_INCOMING=1,1,1.0,0.0", "MODAL_INCOMING=1,1,0.5,0.0"))
        with self.assertRaisesRegex(ValueError, "receipt"):
            analysis.analyze(self.folder)

    def test_state_floor_requires_mirror_assumption_other_profiles_report(self):
        matrix = fixture(self.folder, guided_modes=2) * .99
        matrix[2, 0] += .006
        matrix[0, 2] += .006
        for boundary in ("exterior_modal", "slit_pml"):
            for profile in ("coherent", "state_floor"):
                with self.subTest(boundary=boundary, profile=profile):
                    fixture(self.folder, guided_modes=2, matrix=matrix,
                            boundary_model=boundary, objective_profile=profile)
                    report = analysis.analyze(self.folder)
                    self.assertTrue(report["matrix_acceptance_pass"])
                    self.assertEqual(report["acceptance_pass"], profile == "coherent")
                    self.assertAlmostEqual(report["mirror_matrix_max_absolute_residual"], .006)
                    self.assertFalse(report["objective_assumption_evidence"]["mirror_symmetry_pass"])
                    self.assertIn("minimum_target_throughput_all_inputs", report)
                    self.assertEqual("state_floor_mirror_assumption_pass" in report["checks"], profile == "state_floor")
        fixture(self.folder, guided_modes=2, boundary_model="slit_pml", objective_profile="state_floor")
        self.assertTrue(analysis.analyze(self.folder)["acceptance_pass"])

    def test_unknown_boundary_or_objective_rejected(self):
        for key in ("boundary_model", "objective_profile"):
            for value in ("unknown", [], True, None):
                with self.subTest(key=key, value=value):
                    fixture(self.folder)
                    path = self.folder / "plan.json"
                    plan = json.loads(path.read_text())
                    plan["config"][key] = value
                    path.write_text(json.dumps(plan))
                    refresh_receipt(self.folder)
                    with self.assertRaisesRegex(ValueError, key):
                        analysis.analyze(self.folder)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "preview needs inverse-design extras")
    def test_preview_recomputes_report_and_rejects_swapped_mask_or_field(self):
        spec = importlib.util.spec_from_file_location("hadamard_preview_bound", SCRIPT.with_name("plot_results.py"))
        preview = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preview)
        mask_path = self.folder / "mask.json"
        mask_path.write_text('{"polygons": []}', encoding="utf-8")
        field_path = self.folder / "field.txt"
        field_path.write_text("fixture source field", encoding="utf-8")
        plan_path = self.folder / "plan.json"
        plan = json.loads(plan_path.read_text())
        plan["mask_sha256"] = hashlib.sha256(mask_path.read_bytes()).hexdigest()
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        refresh_receipt(self.folder)
        receipt_path = self.folder / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["artifacts"]["field.txt"] = {"sha256": hashlib.sha256(field_path.read_bytes()).hexdigest()}
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        # A stale derived report cannot change the figure's scientific status.
        (self.folder / "verification.json").write_text('{"acceptance_pass": false}', encoding="utf-8")
        _, fresh, provenance = preview.verified_inputs(self.folder, mask_path)
        self.assertTrue(fresh["acceptance_pass"])
        self.assertTrue(provenance["acceptance_pass"])
        self.assertEqual(provenance["mask_sha256"], plan["mask_sha256"])
        mask_path.write_text('{"polygons": [1]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mask.*native run plan"):
            preview.verified_inputs(self.folder, mask_path)
        mask_path.write_text('{"polygons": []}', encoding="utf-8")
        field_path.write_text("different field", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "field.txt.*receipt"):
            preview.verified_inputs(self.folder, mask_path)


if __name__ == "__main__":
    unittest.main()
