from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse"
SPEC = importlib.util.spec_from_file_location("hadamard_discrete_gradient", EXAMPLE / "check_discrete_gradient.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def synthetic_log(adjoint_scale: float = 1.0, tie: bool = False) -> str:
    """An analytic quadratic log, independent of any private solver path/data."""
    lines = [checker.SEED_ASSOCIATION, checker.CONTRACT + checker.EXPECTED_OBJECTIVE]
    observations = {}
    for i, w in enumerate(checker.WAVELENGTHS):
        base = 0.4 if tie and i < 2 else 0.4 + 0.01 * i
        derivative = 0.8 + 0.1 * i
        for a in checker.STEPS:
            j = base + derivative * a + 0.5 * a * a
            dot = (derivative + a) * adjoint_scale
            observations[w, a] = (j, dot)
            lines.extend([
                "FRESH_CONTROL=probeSol/v1/comp1_theta_c,valuetype=complex,scale=1",
                f"SEED_READBACK={w},{a},max_error=0",
                f"OBSERVATION={w},{a},{j:.17g},{dot:.17g},mapped_fsens_max_imag=0",
            ])
        for h in (0.001, 0.0005):
            dot = observations[w, 0][1]
            fd = (observations[w, h][0] - observations[w, -h][0]) / (2 * h)
            error = abs(fd - dot) / max(1e-10, abs(fd), abs(dot))
            lines.append(f"COMPARISON={w},{h},{dot:.17g},{fd:.17g},{error:.17g}")
        lines.append(f"WAVELENGTH_DIAGNOSTIC_COMPLETE={w}")
    minima = {a: min(observations[w, a][0] for w in checker.WAVELENGTHS) for a in checker.STEPS}
    active = min(checker.WAVELENGTHS, key=lambda w: observations[w, 0][0])
    gap = min(observations[w, 0][0] for w in checker.WAVELENGTHS if w != active) - minima[0]
    tied = [observations[w, 0][1] for w in checker.WAVELENGTHS if observations[w, 0][0] - minima[0] <= 1e-9]
    right, left = min(tied), max(tied)
    lines.append(f"MIN_ACTIVE={active},{minima[0]:.17g},gap={gap:.17g},right_derivative={right:.17g},"
                 f"left_derivative={left:.17g},tie_tol=1e-9")
    for h in (0.001, 0.0005):
        central = (minima[h] - minima[-h]) / (2 * h)
        lines.append(f"MIN_FD={h},central={central:.17g},right={(minima[h]-minima[0])/h:.17g},"
                     f"left={(minima[0]-minima[-h])/h:.17g},central_expected={(right+left)/2:.17g}")
    lines.append(checker.COMPLETE)
    return "\n".join(lines) + "\n"


class DiscreteGradientTests(unittest.TestCase):
    def test_complete_quadratic_and_tied_minimum_are_recomputed(self) -> None:
        for tie in (False, True):
            result = checker.parse_diagnostic(synthetic_log(tie=tie))
            self.assertTrue(result["gradient_pass"])
            self.assertEqual(result["counts"]["observations"], 25)
            self.assertEqual(len(result["checks"]), 10)
            self.assertEqual(len(result["minimum"]["checks"]), 2)
            self.assertEqual(result["relative_tolerance"], 0.002)

    def test_self_consistent_disagreement_is_valid_but_scientifically_fails(self) -> None:
        result = checker.parse_diagnostic(synthetic_log(adjoint_scale=1.01))
        self.assertTrue(result["valid"])
        self.assertFalse(result["gradient_pass"])
        self.assertGreater(result["worst_relative_error"], 0.002)

    def test_every_missing_or_repeated_scientific_row_fails_closed(self) -> None:
        baseline = synthetic_log().splitlines()
        prefixes = ("OBSERVATION=", "COMPARISON=", "WAVELENGTH_DIAGNOSTIC_COMPLETE=",
                    "MIN_ACTIVE=", "MIN_FD=", "SEED_READBACK=", "FRESH_CONTROL=",
                    "DIAGNOSTIC_COMPLETE=", "SEED_STUDY_ASSOCIATION=", "LEGACY_COMPLEX_CVF_RETAINED=")
        for prefix in prefixes:
            index = next(i for i, line in enumerate(baseline) if line.startswith(prefix))
            for changed in (baseline[:index] + baseline[index + 1:], [*baseline, baseline[index]]):
                with self.subTest(prefix=prefix, count=len(changed)), self.assertRaises(ValueError):
                    checker.parse_diagnostic("\n".join(changed))

    def test_nan_bad_mapping_wrong_fixed_lambda_step_and_printed_mismatch_fail(self) -> None:
        baseline = synthetic_log()
        changes = (
            ("OBSERVATION=1580.0,0.0,0.40000000000000002", "OBSERVATION=1580.0,0.0,NaN"),
            ("mapped_fsens_max_imag=0", "mapped_fsens_max_imag=1e-5"),
            ("SEED_READBACK=1580.0,0.0,max_error=0", "SEED_READBACK=1580.0,0.0,max_error=3e-10"),
            ("OBSERVATION=1580.0,0.0", "OBSERVATION=1581.0,0.0"),
            ("OBSERVATION=1580.0,0.001", "OBSERVATION=1580.0,0.002"),
            ("COMPARISON=1580.0,0.001,0.80000000000000004", "COMPARISON=1580.0,0.001,0.9"),
            ("MIN_ACTIVE=1580.0", "MIN_ACTIVE=1565.0"),
            ("central_expected=0.80000000000000004", "central_expected=0.9"),
            ("valuetype=complex", "valuetype=real"),
            ("MIN_FD=0.001,central=", "MIN_FD=0.002,central="),
            (checker.EXPECTED_OBJECTIVE, "changed_objective"),
        )
        for before, after in changes:
            self.assertIn(before, baseline)
            with self.subTest(after=after), self.assertRaises(ValueError):
                checker.parse_diagnostic(baseline.replace(before, after, 1))
        with self.assertRaises(ValueError):
            checker.parse_diagnostic(baseline + "PROBE_EXCEPTION=synthetic failure\n")

    def test_native_source_retains_seed_problem_and_discrete_mapping_guards(self) -> None:
        text = (EXAMPLE / "CvfDiscreteGradientProbe.java").read_text(encoding="utf-8")
        self.assertEqual(text.count("public class "), 1)
        for required in ('"__RESTART_MODEL__"', '"__RUN_DIRECTORY__"', 'm.sol("probeSeed").study("std1")',
                         'm.sol("probeSeed").create("seedStep","StudyStep")', 'set("studystep","freq")',
                         'set("splitcomplex",true)', 'sameMap(s)', 'gradientImag[p]',
                         'dot+=gradient[p]*dir[k]', 'Stored perturbation readback mismatch'):
            self.assertIn(required, text)

    def _inputs(self, root: Path) -> list[str]:
        solver = root / "solver/bin/win64"
        solver.mkdir(parents=True)
        for name in ("comsolcompile.exe", "comsolbatch.exe"):
            (solver / name).write_bytes(b"fixture")
        restart = root / "seed.mph"
        restart.write_bytes(b"synthetic checkpoint input")
        return ["--solver-root", str(root / "solver"), "--restart", str(restart), "--output", str(root / "run")]

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_default_plan_neither_writes_nor_executes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            args = self._inputs(root)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            output = io.StringIO()
            with patch.object(checker, "process") as execute, redirect_stdout(output):
                self.assertEqual(checker.main(args), 0)
            execute.assert_not_called()
            self.assertFalse((root / "run").exists())
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()})
            plan = json.loads(output.getvalue())
            self.assertFalse(plan["execute"])
            self.assertEqual(plan["processors"], 8)
            self.assertEqual(plan["timeout_seconds"], 900)
            self.assertEqual(plan["restart_sha256"], checker.digest(root / "seed.mph"))

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_execute_exit_codes_and_completion_separate_from_gradient(self) -> None:
        for variant, expected in (("pass", 0), ("gradient_fail", 2), ("malformed", 1), ("compile_fail", 1),
                                  ("batch_fail", 1), ("missing_class", 1), ("missing_batch_log", 1)):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = [*self._inputs(root), "--execute"]

                def native_process(command, cwd, log, timeout, variant=variant):
                    if log.name == "compile.log":
                        log.write_text("synthetic compile", encoding="utf-8")
                        if variant != "missing_class":
                            (cwd / "CvfDiscreteGradientProbe.class").write_bytes(b"synthetic class")
                        return (1 if variant == "compile_fail" else 0), 0.1
                    text = synthetic_log(adjoint_scale=1.01 if variant == "gradient_fail" else 1)
                    if variant == "malformed":
                        text = text.replace("WAVELENGTH_DIAGNOSTIC_COMPLETE=1580.0\n", "")
                    log.write_text(text, encoding="utf-8")
                    if variant != "missing_batch_log":
                        (cwd / "batch.log").write_text("synthetic batch", encoding="utf-8")
                    return (1 if variant == "batch_fail" else 0), 0.2

                with patch.object(checker, "process", side_effect=native_process), redirect_stdout(io.StringIO()):
                    self.assertEqual(checker.main(args), expected)
                receipt = json.loads((root / "run/receipt.json").read_text(encoding="utf-8"))
                self.assertEqual(receipt["completed"], variant in {"pass", "gradient_fail", "malformed"})
                self.assertEqual(receipt["gradient_pass"], variant == "pass")
                self.assertIn("plan_sha256", receipt)
                self.assertIn("CvfDiscreteGradientProbe.java", receipt["artifacts"])

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_existing_directory_missing_entrypoints_and_bad_seed_reject_before_process(self) -> None:
        for variant in ("output_exists", "missing_entrypoint", "empty_seed", "wrong_extension"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                args = [*self._inputs(root), "--execute"]
                if variant == "output_exists":
                    (root / "run").mkdir()
                elif variant == "missing_entrypoint":
                    (root / "solver/bin/win64/comsolcompile.exe").unlink()
                elif variant == "empty_seed":
                    (root / "seed.mph").write_bytes(b"")
                else:
                    seed = root / "seed.txt"
                    seed.write_bytes(b"fixture")
                    args[args.index("--restart") + 1] = str(seed)
                with patch.object(checker, "process") as execute, redirect_stdout(io.StringIO()):
                    self.assertEqual(checker.main(args), 1)
                execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
