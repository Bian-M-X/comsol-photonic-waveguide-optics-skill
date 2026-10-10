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

EXAMPLE = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse/run.py"
SPEC = importlib.util.spec_from_file_location("hadamard_example_runner", EXAMPLE)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

# Accepted rows from the independent local 2026-10-04 discriminator logs.
GCMMA_TRACE = """<---- Study 1/Solution 1 (sol1): Optimization Solver 1 ----
  Iter  Inner  nEval      Error  Objective  MaxInfeas
     0      -      1          -     0.4001          -
     1      2      3      0.252     0.5834          -
     2      4      7     0.0893     0.5935          -
     3      7     14     0.0155     0.5969          -
     4      5     19    0.00778     0.5978          -
     5      7     26      0.311     0.6111          -
----- Study 1/Solution 1 (sol1): Optimization Solver 1 ---->
Iter      SolEst     Damping    Stepsize #Res #Jac #Sol   LinErr   LinRes
1 0.05 1 1 3 1 1 1e-15 1e-14
"""
MMA_TRACE = """<---- Study 1/Solution 1 (sol1): Optimization Solver 1 ----
  Iter  Inner  nEval      Error  Objective  MaxInfeas
     0      -      1          -     0.4001          -
     1      0      2      0.428     0.5516          -
     2      0      3      0.382     0.5811          -
     3      0      4      0.457      0.476          -
     4      0      5        0.5     0.6022          -
     5      0      6        0.5     0.5607          -
     6      0      7        0.5     0.6194          -
     7      0      8        0.5     0.5956          -
     8      0      9        0.5     0.6232          -
     9      0     10        0.5     0.6246          -
    10      0     11        0.5     0.6149          -
----- Study 1/Solution 1 (sol1): Optimization Solver 1 ---->
"""


class HadamardRunnerTests(unittest.TestCase):
    def test_actual_mma_and_gcmma_cost_include_initial_and_inner_evaluations(self) -> None:
        config = runner.configuration(None) | {"mode": "optimize", "training_band": "five"}
        for trace, evaluations, iterations, inner in ((MMA_TRACE, 11, 10, 0), (GCMMA_TRACE, 26, 5, 25)):
            with self.subTest(evaluations=evaluations):
                result = runner.parse_optimization_trace(trace, config)
                self.assertTrue(result["completed_requested_stages"])
                self.assertEqual(result["observed_band_evaluations"], evaluations)
                self.assertEqual(result["nominal_training_frequency_state_evaluations"], 5 * evaluations)
                self.assertEqual(result["stages"][0]["outer_iterations"], iterations)
                self.assertEqual(result["stages"][0]["inner_iterations"], inner)
        rows = runner.parse_optimization_trace(GCMMA_TRACE, config)["stages"][0]["rows"]
        self.assertEqual([r["evaluations"] for r in rows], [1, 3, 7, 14, 19, 26])
        self.assertEqual(rows[-1]["objective_rounded"], 0.6111)
        multistage = runner.parse_optimization_trace(MMA_TRACE + GCMMA_TRACE, config | {"stages": 2})
        self.assertTrue(multistage["completed_requested_stages"])
        self.assertEqual([s["evaluations"] for s in multistage["stages"]], [11, 26])
        self.assertEqual(multistage["observed_band_evaluations"], 37)

    def test_continuation_resets_counters_and_keeps_interrupted_lower_bound(self) -> None:
        first = """<---- 研究 1/解 1 (sol1) 中的“优化求解器 1” ----
Iter Inner nEval Error Objective MaxInfeas
0 - 1 - -0.7609 -
1 0 2 0.417 -0.4414 -
2 0 3 0.411 -0.1898 -
3 0 4 0.476 0.03004 -
4 0 5 0.5 0.1723 -
5 0 6 0.369 0.1789 -
6 0 7 0.5 0.2276 -
7 0 8 0.109 0.2395 -
8 0 9 1.11e-15 0.2395 -
----- 研究 1/解 1 (sol1) 中的“优化求解器 1” ---->
"""
        next_stage = first.split("Iter Inner", 1)[0] + "Iter Inner nEval Error Objective MaxInfeas\n0 - 1 - 0.1705 -\n"
        result = runner.parse_optimization_trace(first + next_stage, {"stages": 2, "training_band": "three"})
        self.assertFalse(result["completed_requested_stages"])
        self.assertEqual([s["completed"] for s in result["stages"]], [True, False])
        self.assertEqual([s["evaluations"] for s in result["stages"]], [9, 1])
        self.assertEqual(result["observed_band_evaluations"], 10)
        self.assertEqual(result["nominal_training_frequency_state_evaluations"], 30)
        self.assertFalse(runner.parse_optimization_trace(MMA_TRACE, {"stages": 2, "training_band": "single"})[
            "completed_requested_stages"])

    def test_malformed_or_contradictory_optimization_rows_fail_closed(self) -> None:
        invalid = [
            "Iter SolEst Damping Stepsize #Res #Jac #Sol LinErr LinRes\n1 1 1 1 2 2 2 0 0",
            GCMMA_TRACE.replace("     5      7     26      0.311     0.6111          -", "5 7 26 0.311"),
            GCMMA_TRACE.replace("     5      7     26", "     5      7     19"),
            GCMMA_TRACE.replace("     5      7     26", "     6      7     26"),
            GCMMA_TRACE.replace("0.6111", "NaN"),
            GCMMA_TRACE.replace("     0      -      1", "     0      -      2"),
            "Iter Inner nEval Error Objective MaxInfeas\n",
            "Iter Inner nEval Error Objective MaxInfeas\n0 - 1 - 0.4 -\n" + GCMMA_TRACE,
        ]
        for trace in invalid:
            with self.subTest(trace=trace[-100:]), self.assertRaises(ValueError):
                runner.parse_optimization_trace(trace, {"stages": 1, "training_band": "five"})

    def test_interruption_before_next_initial_row_preserves_completed_prefix(self) -> None:
        next_header = (
            "<---- Study 1/Solution 1 (sol1): Optimization Solver 1 ----\n"
            "Iter Inner nEval Error Objective MaxInfeas\n"
        )
        result = runner.parse_optimization_trace(MMA_TRACE + next_header, {"stages": 2, "training_band": "five"})
        self.assertFalse(result["completed_requested_stages"])
        self.assertEqual(result["observed_band_evaluations"], 11)
        self.assertEqual(result["nominal_training_frequency_state_evaluations"], 55)
        self.assertEqual(result["stages"][1]["rows"], [])
        self.assertEqual(result["stages"][1]["evaluations"], 0)
        self.assertFalse(result["stages"][1]["completed"])
        with self.assertRaisesRegex(ValueError, "Empty optimization trace stage"):
            runner.parse_optimization_trace(
                MMA_TRACE + next_header + "----- Study 1/Solution 1 (sol1): Optimization Solver 1 ---->\n",
                {"stages": 2, "training_band": "five"},
            )

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_completed_runner_receipt_keeps_actual_over_threshold_cost(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "bin/win64"
            native.mkdir(parents=True)
            for name in ("comsolcompile.exe", "comsolbatch.exe"):
                (native / name).touch()
            source = root / "HadamardNative.java"
            source.write_text("reviewed source placeholder", encoding="utf-8")
            config = root / "config.json"
            config.write_text(json.dumps({"mode": "optimize", "optimizer": "gcmma",
                                          "training_band": "five", "evaluation_limit": 20}), encoding="utf-8")
            output = root / "run"

            def process(command, cwd, log, timeout):
                log.write_text("compile\n", encoding="utf-8")
                if log.name == "compile.log":
                    (cwd / "HadamardNative.class").write_bytes(b"compiled")
                else:
                    (cwd / "batch.log").write_text(GCMMA_TRACE, encoding="utf-8")
                    for artifact in ("final.mph", "metrics.csv", "power.csv", "density.txt"):
                        (cwd / artifact).write_bytes(b"export")
                    log.write_text("HADAMARD_DIAGNOSTIC_EXPORT_COMPLETE\n", encoding="utf-8")
                return 0, 0.01

            args = ["run", "--solver-root", str(root), "--source", str(source), "--config", str(config),
                    "--output", str(output), "--execute"]
            with (patch("sys.argv", args), patch.object(runner, "process", side_effect=process),
                  redirect_stdout(io.StringIO())):
                self.assertEqual(runner.main(), 0)
            receipt = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
            self.assertTrue(receipt["completed"])
            self.assertEqual(receipt["optimization_cost"]["observed_band_evaluations"], 26)
            self.assertEqual(receipt["artifacts"]["batch.log"]["sha256"], runner.digest(output / "batch.log"))

    def test_optimizer_tuning_is_explicit_bounded_and_validated_before_execution(self) -> None:
        defaults = runner.configuration(None)
        self.assertEqual((defaults["optimizer"], defaults["move_limit"], defaults["evaluation_limit"]),
                         ("mma", 0.05, 1000))
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "input.json"
            for method in ("mma", "gcmma"):
                for move in (0.0001, 0.0274653, 0.2):
                    requested = {"mode": "optimize", "optimizer": method, "move_limit": move,
                                 "evaluation_limit": 20}
                    config.write_text(json.dumps(requested), encoding="utf-8")
                    with self.subTest(requested=requested):
                        result = runner.configuration(config)
                        self.assertTrue(all(result[key] == value for key, value in requested.items()))
            invalid = [{"optimizer": value} for value in ("ipopt", None, [], True)]
            invalid += [{"move_limit": value} for value in (0, 0.20001, True, "0.05", float("nan"))]
            invalid += [{"evaluation_limit": value} for value in (1, 5001, 2.5, True, float("inf"))]
            for requested in invalid:
                config.write_text(json.dumps(requested), encoding="utf-8")
                with self.subTest(requested=requested), self.assertRaises(ValueError):
                    runner.configuration(config)

    def test_new_controls_keep_defaults_and_accept_explicit_training(self) -> None:
        defaults = runner.configuration(None)
        self.assertEqual(defaults["training_band"], "single")
        self.assertEqual(defaults["objective_profile"], "coherent")
        self.assertIs(defaults["reconfigure_restart"], False)
        self.assertEqual(defaults["boundary_model"], "exterior_modal")
        self.assertEqual(defaults["pml_thickness_um"], 0.8)
        self.assertEqual(defaults["pml_scale"], 1.0)
        self.assertEqual(defaults["pml_curvature"], 3.0)
        self.assertEqual(defaults["projection_offset_um"], 0.2)
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "input.json"
            for profile in ("coherent", "state_floor"):
                requested = {"mode": "optimize", "training_band": "five", "objective_profile": profile,
                             "reconfigure_restart": True}
                config.write_text(json.dumps(requested), encoding="utf-8")
                with self.subTest(profile=profile):
                    result = runner.configuration(config)
                    for key, value in requested.items():
                        self.assertEqual(result[key], value)

    def test_boundary_controls_accept_endpoints_and_reject_unsafe_parameters(self) -> None:
        limits = {"pml_thickness_um": (0.4, 1.6), "pml_scale": (0.5, 3), "pml_curvature": (1, 5),
                  "projection_offset_um": (0.1, 0.5)}
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "input.json"
            for boundary in ("exterior_modal", "slit_pml"):
                for key, (low, high) in limits.items():
                    for value in (low, high):
                        config.write_text(json.dumps({"boundary_model": boundary, key: value}), encoding="utf-8")
                        with self.subTest(boundary=boundary, key=key, value=value):
                            result = runner.configuration(config)
                            self.assertEqual(result["boundary_model"], boundary)
                            self.assertEqual(result[key], value)
            invalid = [{"boundary_model": value} for value in ("unknown", None, [], True)]
            for key, (low, high) in limits.items():
                invalid.extend({key: value} for value in (low - 0.01, high + 0.01, True, "1", None,
                                                         float("nan"), float("inf")))
            for value in invalid:
                config.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(value=value), self.assertRaises(ValueError):
                    runner.configuration(config)

    def test_slit_projection_contour_requires_strict_port_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "input.json"
            for port_half, accepted in ((1.49, True), (1.5, False), (1.51, False)):
                requested = {"boundary_model": "slit_pml", "outer_half_um": 2.0,
                             "projection_offset_um": 0.5, "port_half_um": port_half}
                config.write_text(json.dumps(requested), encoding="utf-8")
                with self.subTest(port_half=port_half):
                    if accepted:
                        self.assertEqual(runner.configuration(config)["port_half_um"], port_half)
                    else:
                        with self.assertRaisesRegex(ValueError, "closed projection contour"):
                            runner.configuration(config)
            requested["boundary_model"] = "exterior_modal"
            config.write_text(json.dumps(requested), encoding="utf-8")
            self.assertEqual(runner.configuration(config)["port_half_um"], 1.51)

    def test_config_rejects_unbounded_or_ambiguous_runs(self) -> None:
        invalid = [{"iterations": True}, {"iterations": 1.5}, {"iterations": 1001},
                   {"mesh_um": 0.001}, {"beta": float("nan")}, {"unknown": 1},
                   {"eps_core": 4, "eps_clad": 4}, {"guided_modes": 1.5},
                   {"port_half_um": 2.5, "outer_half_um": 2.5},
                   {"training_band": "three", "wavelength_nm": 1536.61},
                   {"training_band": "three", "mode": "gradient"},
                   {"training_band": "five", "mode": "baseline"},
                   {"training_band": "five", "mode": "binary"},
                   {"training_band": "five", "mode": "gradient"},
                   {"training_band": "five", "mode": "optimize", "wavelength_nm": 1565},
                   {"objective_profile": "unknown"}, {"objective_profile": []},
                   {"reconfigure_restart": "true"}, {"reconfigure_restart": 1},
                   {"reconfigure_restart": None}, {"reconfigure_restart": True},
                   {"reconfigure_restart": True, "mode": "frozen"}, ["not an object"]]
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "input.json"
            for value in invalid:
                config.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(value=value), self.assertRaises(ValueError):
                    runner.configuration(config)

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_frozen_five_frequency_checkpoint_can_be_planned_without_reoptimization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "bin/win64"
            native.mkdir(parents=True)
            for name in ("comsolcompile.exe", "comsolbatch.exe"):
                (native / name).touch()
            source = root / "HadamardNative.java"
            source.write_text("reviewed source placeholder", encoding="utf-8")
            config = root / "input.json"
            requested = {"mode": "frozen", "training_band": "five", "beta": 16,
                         "mesh_um": 0.045, "objective_profile": "state_floor",
                         "fidelity_weight": 10, "boundary_model": "slit_pml"}
            config.write_text(json.dumps(requested), encoding="utf-8")
            restart = root / "stage1.mph"
            restart.write_bytes(b"completed optimization checkpoint")
            output = root / "recovered-export"
            args = ["run", "--solver-root", str(root), "--source", str(source),
                    "--config", str(config), "--output", str(output)]
            with (patch("sys.argv", [*args, "--execute"]), patch.object(runner, "process") as process,
                  redirect_stdout(io.StringIO()), patch("sys.stderr", new=io.StringIO()),
                  self.assertRaises(SystemExit) as error):
                runner.main()
            self.assertEqual(error.exception.code, 2)
            process.assert_not_called()
            with (patch("sys.argv", [*args, "--restart", str(restart)]),
                  patch.object(runner, "process") as process, redirect_stdout(io.StringIO()) as stdout):
                self.assertEqual(runner.main(), 0)
            plan = json.loads(stdout.getvalue())
            self.assertEqual(plan["restart_sha256"], runner.digest(restart))
            self.assertTrue(all(plan["config"][key] == value for key, value in requested.items()))
            self.assertIs(plan["execute"], False)
            process.assert_not_called()
            self.assertFalse(output.exists())

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_restart_reconfiguration_requires_valid_explicit_restart_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "bin/win64"
            native.mkdir(parents=True)
            for name in ("comsolcompile.exe", "comsolbatch.exe"):
                (native / name).touch()
            source = root / "HadamardNative.java"
            source.write_text("reviewed source placeholder", encoding="utf-8")
            config = root / "input.json"
            config.write_text(json.dumps({"mode": "optimize", "training_band": "five",
                                          "objective_profile": "state_floor", "reconfigure_restart": True,
                                          "boundary_model": "slit_pml", "pml_thickness_um": 1.2,
                                          "pml_scale": 2.0, "pml_curvature": 4.0}),
                              encoding="utf-8")
            output = root / "results"
            args = ["run", "--solver-root", str(root), "--source", str(source), "--config", str(config),
                    "--output", str(output)]
            invalid = root / "missing.mph"
            wrong_suffix = root / "restart.txt"
            wrong_suffix.touch()
            for restart in (None, invalid, wrong_suffix):
                invocation = args + (["--restart", str(restart)] if restart else []) + ["--execute"]
                with (self.subTest(restart=restart), patch("sys.argv", invocation),
                      patch.object(runner, "process") as process, redirect_stdout(io.StringIO()),
                      patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as error):
                    runner.main()
                self.assertEqual(error.exception.code, 2)
                process.assert_not_called()
                self.assertFalse(output.exists())
            restart = root / "restart.mph"
            restart.write_bytes(b"restart fixture")
            with (patch("sys.argv", [*args, "--restart", str(restart)]), patch.object(runner, "process") as process,
                  redirect_stdout(io.StringIO()) as stdout):
                self.assertEqual(runner.main(), 0)
            plan = json.loads(stdout.getvalue())
            self.assertIs(plan["config"]["reconfigure_restart"], True)
            self.assertEqual(plan["config"]["objective_profile"], "state_floor")
            self.assertEqual(plan["config"]["boundary_model"], "slit_pml")
            self.assertEqual(plan["config"]["pml_thickness_um"], 1.2)
            self.assertEqual(plan["config"]["pml_scale"], 2.0)
            self.assertEqual(plan["config"]["pml_curvature"], 4.0)
            self.assertEqual(plan["restart_sha256"], runner.digest(restart))
            process.assert_not_called()
            self.assertFalse(output.exists())

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_zero_compiler_exit_without_fresh_class_is_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "bin/win64"
            native.mkdir(parents=True)
            for name in ("comsolcompile.exe", "comsolbatch.exe"):
                (native / name).touch()
            source = root / "HadamardNative.java"
            source.write_text("reviewed source placeholder", encoding="utf-8")
            output = root / "results"
            args = ["run", "--solver-root", str(root), "--source", str(source),
                    "--output", str(output), "--execute"]
            with (patch("sys.argv", args), patch.object(runner, "process", return_value=(0, 0.01)) as run,
                  redirect_stdout(io.StringIO())):
                self.assertEqual(runner.main(), 1)
            self.assertEqual(run.call_count, 1, "batch must not start after missing compiler output")
            self.assertFalse(json.loads((output / "receipt.json").read_text())["completed"])

    @unittest.skipUnless(os.name == "nt", "Windows native runner")
    def test_plan_does_not_start_solver_or_create_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            native = root / "bin/win64"
            native.mkdir(parents=True)
            for name in ("comsolcompile.exe", "comsolbatch.exe"):
                (native / name).touch()
            source = root / "HadamardNative.java"
            source.write_text("reviewed source placeholder", encoding="utf-8")
            output = root / "results"
            args = ["run", "--solver-root", str(root), "--source", str(source), "--output", str(output)]
            with (patch("sys.argv", args), patch.object(runner, "process", side_effect=AssertionError("run")),
                  redirect_stdout(io.StringIO()) as stdout):
                self.assertEqual(runner.main(), 0)
            self.assertFalse(json.loads(stdout.getvalue())["execute"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
