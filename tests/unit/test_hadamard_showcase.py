"""Actual exported-bundle regressions; no solver or native-authentication claim."""

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SHOWCASE = Path(__file__).resolve().parents[2] / "docs/showcases/hadamard-2d"
SPEC = importlib.util.spec_from_file_location("hadamard_showcase_verifier", SHOWCASE / "verify.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def update_bundle(folder, mutate):
    """Refresh export integrity so tests exercise numerical/frozen-value checks."""
    bundle = verifier.read_json(SHOWCASE / "evidence/bundle.json")
    mutate(bundle)
    (folder / "bundle.json").write_text(json.dumps(bundle, allow_nan=False), encoding="utf-8")
    manifest = verifier.read_json(folder / "manifest.json")
    manifest["files"]["bundle.json"] = verifier.digest(folder / "bundle.json")
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class ShowcaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hadamard-showcase-test-")
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        for name in ("bundle.json", "mask.json", "manifest.json"):
            shutil.copyfile(SHOWCASE / "evidence" / name, self.folder / name)

    def test_actual_bundle_recomputes_full_numeric_suite(self):
        result = verifier.verify(self.folder)
        self.assertIs(result["full_numerical_suite_pass"], True)
        self.assertEqual(result["completed_numeric_runs"], 20)
        self.assertEqual(result["completed_convergence_pairs"], 13)
        self.assertIs(result["native_receipts_reverified"], False)

    def test_computed_mirror_residual_accepts_roundoff(self):
        for delta in (-1e-13, 1e-13):
            with self.subTest(delta=delta):

                def mutate(bundle, offset=delta):
                    for run in bundle["runs"]:
                        run["report"]["objective_assumption_evidence"]["mirror_matrix_max_absolute_residual"] += offset

                update_bundle(self.folder, mutate)
                self.assertIs(verifier.verify(self.folder)["full_numerical_suite_pass"], True)

    def test_computed_mirror_residual_rejects_material_tamper(self):
        for delta in (-5e-8, 5e-8):
            with self.subTest(delta=delta):

                def mutate(bundle, offset=delta):
                    evidence = bundle["runs"][0]["report"]["objective_assumption_evidence"]
                    evidence["mirror_matrix_max_absolute_residual"] += offset

                update_bundle(self.folder, mutate)
                with self.assertRaisesRegex(ValueError, r"objective_assumption\.mirror_matrix_max_absolute_residual"):
                    verifier.verify(self.folder)

    def test_objective_configuration_and_gates_remain_exact(self):
        for field, value in (
            ("amplitude_absolute_tolerance", 0.005 + 1e-13),
            ("mirror_symmetry_required", 1),
            ("objective_profile", "coherent"),
            ("mirror_symmetry_pass", 1),
        ):
            with self.subTest(field=field):

                def mutate(bundle, key=field, replacement=value):
                    bundle["runs"][0]["report"]["objective_assumption_evidence"][key] = replacement

                update_bundle(self.folder, mutate)
                with self.assertRaisesRegex(ValueError, "objective_assumption"):
                    verifier.verify(self.folder)

    def test_all_policy_numbers_remain_exact(self):
        cases = (
            [("policy", key) for key in verifier.FROZEN_POLICY]
            + [("additional_policy", key) for key in verifier.EXTRA_POLICY]
            + [("convergence_policy", key) for key in verifier.CONVERGENCE_POLICY]
        )
        for group, field in cases:
            with self.subTest(group=group, field=field):

                def mutate(bundle, category=group, key=field):
                    bundle[category][key] += 1e-13

                update_bundle(self.folder, mutate)
                with self.assertRaisesRegex(ValueError, "Frozen value changed"):
                    verifier.verify(self.folder)
