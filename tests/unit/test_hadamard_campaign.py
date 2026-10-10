import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse/campaign.py"
SPEC = importlib.util.spec_from_file_location("hadamard_campaign_example", SCRIPT)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)

GCMMA_TRACE = """<---- Study 1/Solution 1 (sol1): Optimization Solver 1 ----
Iter Inner nEval Error Objective MaxInfeas
0 - 1 - 0.4001 -
1 2 3 0.252 0.5834 -
2 4 7 0.0893 0.5935 -
3 7 14 0.0155 0.5969 -
4 5 19 0.00778 0.5978 -
5 7 26 0.311 0.6111 -
----- Study 1/Solution 1 (sol1): Optimization Solver 1 ---->
"""


def report(passed=True, f=0):
    return {
        "acceptance_pass": passed,
        "both_input_split_ratios": [math.exp(f), math.exp(-f)],
        "target_throughput_per_input": [0.97, 0.97],
        "minimum_target_throughput_all_inputs": 0.97,
        "six_states": {
            state: {"target_throughput": 0.97} for state in ("zero", "one", "plus", "minus", "plus_i", "minus_i")
        },
        "min_six_state_conditional_fidelity": 0.999,
        "conditional_choi_overlap": 0.999,
    }


def training_fixture(config):
    bands = {"three": [1580, 1550, 1520], "five": list(reversed(campaign.TRAINING_WAVELENGTHS))}
    wavelengths = bands.get(config["training_band"], [config["wavelength_nm"]])
    observations = []
    for stage in range(1, config["stages"] + 1):
        observations.extend(f"TRAINING_POINT={stage},{wavelength},0.8" for wavelength in wavelengths)
        observations.append(f"TRAINING_MINIMUM={stage},{wavelengths[0]},0.8")
    aggregation = "auto" if config["training_band"] == "single" else "min"
    return {"training_observations": observations}, (
        f"OPTIMIZATION_OBJECTIVE_VERIFIED={aggregation},{campaign.expected_objective(config)}\n"
        + f"OPTIMIZER_CONTROLS_VERIFIED={config.get('optimizer', 'mma')},"
        f"{config.get('move_limit', 0.05)},{config.get('evaluation_limit', 1000)}\n"
        + "\n".join(observations)
    )


class CampaignTests(unittest.TestCase):
    def test_raw_training_amplitudes_rescore_both_objective_profiles(self):
        for profile in ("coherent", "state_floor"):
            with self.subTest(profile=profile):
                config = dict(campaign.plan()["startup"])["coarse"] | {"stages": 1, "objective_profile": profile}
                receipt, console = training_fixture(config)
                value = 0.56 if profile == "coherent" else 0.56 - math.sqrt(0.0196 + 1e-8)
                receipt["training_observations"] = [line.replace(",0.8", f",{value}")
                                                    for line in receipt["training_observations"]]
                console = console.replace(",0.8", f",{value}")
                modes = [f"TRAINING_MODAL=1,{wavelength},0.6,0.1,-0.2,0.5"
                         for wavelength in campaign.TRAINING_WAVELENGTHS]
                receipt["training_modal_observations"] = modes
                console += "\n" + "\n".join(modes)
                result = campaign.optimization_prechecks(receipt, console, config)["objective_components"]
                self.assertTrue(result["available"])
                points = result["training_stages"][1]["points"]
                self.assertEqual(len(points), 5)
                self.assertAlmostEqual(points[0]["target_throughput_input1"], 0.66)
                self.assertAlmostEqual(points[0]["wrong_superposition_power"], 0.01)
                self.assertAlmostEqual(points[0]["real_cross_overlap"], -0.07)
                self.assertAlmostEqual(points[0]["coherent_objective"], 0.56)
                self.assertAlmostEqual(points[0]["state_floor_objective"], 0.56 - math.sqrt(0.0196 + 1e-8))
                self.assertAlmostEqual(points[0]["mirror_all_input_throughput_surrogate"], 0.52)
                self.assertAlmostEqual(result["training_stages"][1]["minima"]["target_throughput_input1"], 0.66)

    def test_raw_training_readout_rejects_corruption_missing_points_and_objective_changes(self):
        config = dict(campaign.plan()["startup"])["coarse"] | {"stages": 1, "objective_profile": "coherent"}
        receipt, console = training_fixture(config)
        receipt["training_observations"] = [line.replace(",0.8", ",0.56") for line in receipt["training_observations"]]
        console = console.replace(",0.8", ",0.56")
        modes = [f"TRAINING_MODAL=1,{wavelength},0.6,0.1,-0.2,0.5" for wavelength in campaign.TRAINING_WAVELENGTHS]
        cases = [
            modes[:-1], modes + modes[:1],
            [modes[0].replace("MODAL=1,", "MODAL=2,"), *modes[1:]],
            [modes[0].replace("1520.0", "1543.3"), *modes[1:]],
            [modes[0].replace("0.6", "nan"), *modes[1:]],
            [modes[0].replace("0.6", "1e308"), *modes[1:]],
            [modes[0].replace("0.6", "0.7"), *modes[1:]],
            [modes[0] + ",0.0", *modes[1:]],
        ]
        for raw in cases:
            with self.subTest(raw=raw[0]), self.assertRaises(RuntimeError):
                campaign.optimization_prechecks(receipt | {"training_modal_observations": raw},
                                                console + "\n" + "\n".join(raw), config)
        with self.assertRaisesRegex(RuntimeError, "modal receipt"):
            campaign.optimization_prechecks(receipt, console + "\n" + "\n".join(modes), config)
        with self.assertRaisesRegex(RuntimeError, "modal receipt"):
            campaign.optimization_prechecks(receipt | {"training_modal_observations": modes}, console, config)

    def test_legacy_training_log_does_not_infer_unrecorded_components(self):
        config = dict(campaign.plan()["startup"])["coarse"]
        receipt, console = training_fixture(config)
        result = campaign.optimization_prechecks(receipt, console, config)["objective_components"]
        self.assertFalse(result["available"])
        self.assertNotIn("training_stages", result)

    def test_cost_prechecks_reject_inconsistent_missing_or_incomplete_trace(self):
        config = dict(campaign.plan()["startup"])["coarse"] | {"stages": 1, "evaluation_limit": 20}
        receipt, console = training_fixture(config)
        receipt["training_observations"] = [line.replace(",0.8", ",0.6111310356826978")
                                            for line in receipt["training_observations"]]
        console = console.replace(",0.8", ",0.6111310356826978")
        training = campaign.optimization_prechecks(receipt, console, config)
        receipt["optimization_cost"] = campaign._RUNNER.parse_optimization_trace(GCMMA_TRACE, config)
        self.assertEqual(campaign.optimization_cost_prechecks(receipt, GCMMA_TRACE, config, training)[
            "observed_band_evaluations"], 26)
        altered = GCMMA_TRACE.replace("0.6111", "0.5111")
        incomplete = GCMMA_TRACE.split("----- Study", 1)[0]
        for trace, requested, faulty in (
            (GCMMA_TRACE, config, {"optimization_cost": {}}),
            (altered, config, receipt),
            (altered, config, {"optimization_cost": campaign._RUNNER.parse_optimization_trace(altered, config)}),
            (incomplete, config, {"optimization_cost": campaign._RUNNER.parse_optimization_trace(incomplete, config)}),
            (GCMMA_TRACE, config | {"stages": 2}, receipt),
            (GCMMA_TRACE, config | {"iterations": 4}, receipt),
        ):
            with self.subTest(trace=trace[-80:], config=requested), self.assertRaises(RuntimeError):
                campaign.optimization_cost_prechecks(faulty, trace, requested, training)

    def test_actual_cost_overrun_retains_physical_evidence_and_stops_next_native_job(self):
        for limit, physical_pass in ((20, True), (20, False), (26, True)):
            with self.subTest(limit=limit, physical_pass=physical_pass), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                runner = campaign.Campaign(output, Path("solver"), 8, 7200)
                config = dict(campaign.plan()["startup"])["coarse"] | {
                    "stages": 1, "evaluation_limit": limit, "optimizer": "gcmma"
                }
                folder = output / "gcmma"
                folder.mkdir()
                receipt, console = training_fixture(config)
                console = console.replace(",0.8", ",0.6111310356826978")
                receipt["training_observations"] = [line.replace(",0.8", ",0.6111310356826978")
                                                    for line in receipt["training_observations"]]
                (folder / "plan.json").write_text(json.dumps({"config": config}), encoding="utf-8")
                (folder / "console.log").write_text(console, encoding="utf-8")
                (folder / "batch.log").write_text(GCMMA_TRACE, encoding="utf-8")
                receipt.update(
                    completed=True,
                    optimization_cost=campaign._RUNNER.parse_optimization_trace(GCMMA_TRACE, config),
                    artifacts={name: {"sha256": campaign.digest(folder / name)}
                               for name in ("plan.json", "console.log", "batch.log")},
                )
                (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

                def process(command, log, folder=folder, physical_pass=physical_pass):
                    if "analyze.py" in command[1]:
                        (folder / "verification.json").write_text(json.dumps(report(physical_pass)), encoding="utf-8")
                        return 0 if physical_pass else 2
                    return 0

                with patch.object(runner, "subprocess", side_effect=process) as calls:
                    if limit == 20:
                        with self.assertRaises(campaign.CostOverrun):
                            runner.native("gcmma", config)
                        self.assertEqual(runner.document["status"], "cost_overrun")
                        with self.assertRaises(campaign.CostOverrun):
                            runner.native("next", {"mode": "gradient"})
                        self.assertFalse((output / "next-config.json").exists())
                    else:
                        self.assertTrue(runner.native("gcmma", config)["acceptance_pass"])
                    self.assertEqual(calls.call_count, 2, "Analyze completed result; no next solver")
                row = runner.document["runs"][0]
                self.assertIs(row["receipt"]["completed"], True)
                self.assertEqual(row["status"], "scientific_pass" if physical_pass else "scientific_failure")
                self.assertEqual(row["report"]["acceptance_pass"], physical_pass)
                self.assertEqual(row["cost_status"], "overrun" if limit == 20 else "within_requested_threshold")
                self.assertEqual(runner.document["cost"]["observed_band_evaluations"], 26)
                self.assertEqual(runner.document["cost"]["nominal_training_frequency_state_evaluations"], 130)
                self.assertEqual(len(runner.document["runs"]), 1)

    def test_batch_hash_mismatch_prevents_cost_acceptance_and_analysis(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            runner = campaign.Campaign(output, Path("solver"), 8, 7200)
            config = dict(campaign.plan()["startup"])["coarse"]
            folder = output / "coarse"
            folder.mkdir()
            receipt, console = training_fixture(config)
            (folder / "plan.json").write_text(json.dumps({"config": config}), encoding="utf-8")
            (folder / "console.log").write_text(console, encoding="utf-8")
            (folder / "batch.log").write_text(GCMMA_TRACE, encoding="utf-8")
            receipt.update(completed=True, artifacts={name: {"sha256": campaign.digest(folder / name)}
                                                     for name in ("plan.json", "console.log", "batch.log")})
            (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            (folder / "batch.log").write_text(GCMMA_TRACE.replace("26", "27"), encoding="utf-8")
            with (patch.object(runner, "subprocess", return_value=0) as calls,
                  self.assertRaisesRegex(RuntimeError, "artifact mismatch.*batch.log")):
                runner.native("coarse", config)
            self.assertEqual(calls.call_count, 1)
            self.assertEqual(runner.document["runs"][0]["cost_status"], "unknown")
            self.assertEqual(runner.document["cost"]["unknown_optimization_jobs"], 1)
            self.assertNotIn("observed_band_evaluations", runner.document["cost"])

    def test_failed_native_keeps_verified_partial_counts_and_never_analyzes(self):
        partial_trace = GCMMA_TRACE.split("----- Study", 1)[0]
        for limit in (20, 30):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                runner = campaign.Campaign(output, Path("solver"), 8, 600)
                config = dict(campaign.plan()["startup"])["coarse"] | {
                    "stages": 1, "evaluation_limit": limit, "optimizer": "gcmma"
                }
                folder = output / "interrupted"
                folder.mkdir()
                (folder / "plan.json").write_text(json.dumps({"config": config}), encoding="utf-8")
                (folder / "batch.log").write_text(partial_trace, encoding="utf-8")
                receipt = {
                    "completed": False,
                    "optimization_cost": campaign._RUNNER.parse_optimization_trace(partial_trace, config),
                    "artifacts": {name: {"sha256": campaign.digest(folder / name)}
                                  for name in ("plan.json", "batch.log")},
                }
                (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
                with (patch.object(runner, "subprocess", return_value=1) as calls,
                      self.assertRaisesRegex(RuntimeError, "Native execution failed")):
                    runner.native("interrupted", config)
                self.assertEqual(calls.call_count, 1)
                saved = json.loads((output / "campaign.json").read_text(encoding="utf-8"))
                self.assertEqual(saved["runs"][0]["status"], "execution_failure")
                self.assertEqual(saved["cost"]["observed_band_evaluations"], 26)
                self.assertEqual(saved["cost"]["nominal_training_frequency_state_evaluations"], 130)
                self.assertEqual(saved["cost"]["incomplete_optimization_jobs"], 1)
                self.assertTrue(saved["cost"]["optimization_counts_are_lower_bounds"])
                self.assertEqual(saved["runs"][0]["cost_status"],
                                 "overrun" if limit == 20 else "partial_lower_bound")
                if limit == 20:
                    with self.assertRaises(campaign.CostOverrun):
                        runner.native("next", config)
                    self.assertFalse((output / "next-config.json").exists())

    def test_failed_native_without_verifiable_trace_marks_unknown_cost(self):
        for state in ("missing_receipt", "bad_hash", "bad_plan", "bad_trace_receipt"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                runner = campaign.Campaign(output, Path("solver"), 8, 600)
                config = dict(campaign.plan()["startup"])["coarse"] | {"stages": 1}
                folder = output / "failed"
                folder.mkdir()
                actual_config = config | ({"training_band": "single"} if state == "bad_plan" else {})
                (folder / "plan.json").write_text(json.dumps({"config": actual_config}), encoding="utf-8")
                (folder / "batch.log").write_text(GCMMA_TRACE, encoding="utf-8")
                receipt = {
                    "completed": False,
                    "optimization_cost": campaign._RUNNER.parse_optimization_trace(GCMMA_TRACE, config),
                    "artifacts": {name: {"sha256": campaign.digest(folder / name)}
                                  for name in ("plan.json", "batch.log")},
                }
                if state == "bad_hash":
                    receipt["artifacts"]["batch.log"]["sha256"] = "wrong"
                if state == "bad_trace_receipt":
                    receipt["optimization_cost"]["observed_band_evaluations"] = 0
                if state != "missing_receipt":
                    (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
                with (patch.object(runner, "subprocess", return_value=1) as calls,
                      self.assertRaisesRegex(RuntimeError, "Native execution failed")):
                    runner.native("failed", config)
                self.assertEqual(calls.call_count, 1)
                self.assertEqual(runner.document["cost"]["unknown_optimization_jobs"], 1)
                self.assertTrue(runner.document["cost"]["optimization_counts_are_lower_bounds"])
                self.assertNotIn("observed_band_evaluations", runner.document["cost"])
                self.assertEqual(runner.document["runs"][0]["cost_status"], "unknown")

    def test_cli_records_cost_stop_separately_from_execution_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "campaign"
            args = ["campaign", "--output", str(output), "--solver-root", "solver", "--execute"]
            with (patch("sys.argv", args),
                  patch.object(campaign.Campaign, "run", side_effect=campaign.CostOverrun("cost")),
                  patch("sys.stdout"), patch("sys.stderr")):
                self.assertEqual(campaign.main(), 3)
            document = json.loads((output / "campaign.json").read_text(encoding="utf-8"))
            self.assertEqual(document["status"], "cost_overrun")

    def test_analysis_error_after_cost_overrun_keeps_cost_stop(self):
        def failed_analysis(runner):
            runner.document["cost"]["observed_band_evaluations"] = 26
            runner.document["cost"]["stop_further_native_jobs"] = True
            raise RuntimeError("Evidence analysis failed after completed solver")

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "campaign"
            args = ["campaign", "--output", str(output), "--solver-root", "solver", "--execute"]
            with (patch("sys.argv", args), patch.object(campaign.Campaign, "run", failed_analysis),
                  patch("sys.stdout"), patch("sys.stderr")):
                self.assertEqual(campaign.main(), 3)
            document = json.loads((output / "campaign.json").read_text(encoding="utf-8"))
            self.assertEqual(document["status"], "cost_overrun")
            self.assertEqual(document["cost"]["observed_band_evaluations"], 26)
            self.assertIn("analysis failed", document["summary"]["error"])

    def test_observed_secant_and_step_bound(self):
        self.assertEqual(campaign.propose_threshold([]), 0.5)
        history = [{"threshold": 0.5, "f": 0.1}]
        self.assertEqual(campaign.propose_threshold(history), 0.495)
        history.append({"threshold": 0.495, "f": 0.05})
        self.assertEqual(campaign.propose_threshold(history), 0.505)
        history.append({"threshold": 0.505, "f": 0.15})
        self.assertAlmostEqual(campaign.propose_threshold(history), 0.49)
        history[-1]["f"] = 0.099
        proposed = campaign.propose_threshold(history)
        self.assertLessEqual(abs(proposed - 0.495), campaign.MAX_STEP + 1e-12)
        self.assertGreaterEqual(proposed, campaign.LOW)

    def test_fallback_no_repeated_threshold(self):
        history = [{"threshold": 0.5, "f": 0}, {"threshold": 0.495, "f": 0}]
        proposed = campaign.propose_threshold(history)
        self.assertNotIn(proposed, [item["threshold"] for item in history])
        self.assertEqual(proposed, campaign.propose_threshold(history))
        history.append({"threshold": 0.5, "f": 0})
        with self.assertRaises(ValueError):
            campaign.propose_threshold(history)

    def test_real_observed_threshold_replay_preserves_precision(self):
        history = []
        observations = (
            (0.5, 0.27814755717120165),
            (0.495, 0.2519684160500575),
            (0.505, 0.3037528058700366),
            (0.475, 0.1001663112555601),
            (0.4618030405255367, -0.09896589918271531),
        )
        for threshold, measured in observations:
            self.assertEqual(campaign.propose_threshold(history), threshold)
            history.append({"threshold": threshold, "f": measured})
        self.assertEqual(campaign.propose_threshold(history), 0.4683617431984674)
        self.assertEqual(history, [{"threshold": threshold, "f": measured} for threshold, measured in observations])

    def test_threshold_budget_is_strict_even_when_observations_are_missing(self):
        history = []
        for _ in range(6):
            proposed = campaign.propose_threshold(history)
            anchor = history[0]["threshold"] if history else 0.5
            self.assertTrue(campaign.LOW <= proposed <= campaign.HIGH)
            self.assertLessEqual(abs(proposed - anchor), campaign.MAX_STEP + 1e-12)
            self.assertTrue(all(abs(proposed - row["threshold"]) > campaign.REPEAT_TOLERANCE for row in history))
            history.append({"threshold": proposed, "f": None})
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            campaign.propose_threshold(history)

    def test_threshold_uses_narrowest_bracket_and_nearest_usable_observation(self):
        bracketed = [{"threshold": threshold, "f": value}
                     for threshold, value in ((0.46, -2), (0.48, -1), (0.5, 1), (0.52, 3))]
        self.assertEqual(campaign.propose_threshold(bracketed), 0.49)
        unbracketed = [{"threshold": threshold, "f": value}
                       for threshold, value in ((0.5, 0.3), (0.495, 0.1), (0.505, 0.4))]
        self.assertEqual(campaign.propose_threshold(unbracketed), 0.4925)

    def test_bracket_midpoint_fallback_is_fresh_interior_and_step_bounded(self):
        for history in (
            [{"threshold": 0.48, "f": -1e-9}, {"threshold": 0.5, "f": 1e-9},
             {"threshold": 0.505, "f": 0.1}],
            [{"threshold": 0.48, "f": -1}, {"threshold": 0.52, "f": 1},
             {"threshold": 0.5, "f": None}],
            [{"threshold": 0.48, "f": -1e308}, {"threshold": 0.52, "f": 1e308},
             {"threshold": 0.5, "f": None}],
        ):
            with self.subTest(history=history):
                self.assertEqual(campaign.propose_threshold(history), 0.49)
        blocked = [{"threshold": 0.48, "f": -1}, {"threshold": 0.52, "f": 1},
                   {"threshold": 0.5, "f": None}, {"threshold": 0.49, "f": None}]
        with self.assertRaisesRegex(ValueError, "No fresh threshold inside"):
            campaign.propose_threshold(blocked)

    def test_degenerate_secant_fallback_only_uses_observed_anchor(self):
        history = [{"threshold": threshold, "f": 0.1} for threshold in (0.5, 0.495, 0.505)]
        before = json.dumps(history)
        self.assertEqual(campaign.propose_threshold(history), 0.49)
        self.assertEqual(json.dumps(history), before)
        history = [{"threshold": threshold, "f": value}
                   for threshold, value in ((0.44, 0.1), (0.45, 0.2), (0.46, 0.3))]
        self.assertEqual(campaign.propose_threshold(history), 0.445)

    def test_nonfinite_rejected(self):
        rows = (
            {"threshold": float("nan"), "f": 0}, {"threshold": float("inf"), "f": 0},
            {"threshold": True, "f": 0}, {"threshold": "0.5", "f": 0},
            {"threshold": 0.43, "f": 0}, {"threshold": 0.54, "f": 0},
            {"threshold": 0.5, "f": float("inf")}, {"threshold": 0.5, "f": float("nan")},
            {"threshold": 0.5, "f": True}, {"threshold": 0.5, "f": "0.1"},
        )
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                campaign.propose_threshold([row])
        for repeated in (0.5, 0.5000005):
            with self.subTest(repeated=repeated), self.assertRaisesRegex(ValueError, "Repeated"):
                campaign.propose_threshold([{"threshold": 0.5, "f": 0.1}, {"threshold": repeated, "f": 0.2}])
        with self.assertRaises(ValueError):
            campaign.imbalance({"both_input_split_ratios": [float("nan"), 1]})
        self.assertIsNone(campaign.imbalance({"both_input_split_ratios": [0, 1]}))

    def test_no_failed_candidate_selection(self):
        rows = [{"acceptance_pass": False, "f": 0}, {"acceptance_pass": False, "f": 0.01}]
        self.assertIsNone(campaign.select_candidate(rows))
        rows.extend([{"acceptance_pass": True, "f": 0.04}, {"acceptance_pass": True, "f": 0.03}])
        self.assertEqual(campaign.select_candidate(rows)["f"], 0.03)

    def test_convergence_failure_not_relaxed(self):
        reference = report()
        changed = report()
        changed["six_states"]["plus_i"]["target_throughput"] += 0.006
        result = campaign.convergence(reference, changed)
        self.assertFalse(result["pass"])
        self.assertEqual(result["eta"]["tolerance"], 0.005)
        self.assertTrue(result["fidelity"]["pass"])

    def test_convergence_includes_every_state_and_all_input_floor(self):
        for state in campaign.STATES:
            changed = report()
            changed["six_states"][state]["target_throughput"] -= 0.006
            with self.subTest(state=state):
                self.assertFalse(campaign.convergence(report(), changed)["pass"])
        changed = report()
        changed["minimum_target_throughput_all_inputs"] -= 0.006
        self.assertFalse(campaign.convergence(report(), changed)["all_input_eta"]["pass"])
        for value in (None, True, float("nan"), float("inf")):
            changed["minimum_target_throughput_all_inputs"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                campaign.convergence(report(), changed)
        del changed["minimum_target_throughput_all_inputs"]
        with self.assertRaises(KeyError):
            campaign.convergence(report(), changed)

    def test_plan_only_no_directories_or_solver(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "untouched"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(output.exists())
            recipe = json.loads(proc.stdout)
            self.assertEqual(recipe["schema_version"], 3)
            self.assertEqual(recipe["native_job_budget_max"], 36)
            self.assertEqual(len(recipe["startup"]), 11)
            self.assertEqual(len(recipe["validation"]), 19)
            self.assertFalse(recipe["gpu_used"])

    def test_profile_is_explicit_multimode_and_five_frequency(self):
        recipe = campaign.plan()
        startup = dict(recipe["startup"])
        nominal = recipe["binary_nominal"]
        configurations = [*startup.values(), nominal]
        configurations.extend(nominal | changes for _, changes in recipe["validation"])
        for config in configurations:
            self.assertEqual(config["guided_modes"], 2)
            self.assertEqual(config["eps_core"], 12.1)
            self.assertEqual(config["eps_clad"], 2.1)
            self.assertEqual(config["fidelity_weight"], 10)
            self.assertEqual(config["objective_profile"], "coherent" if config["mode"] != "binary" else "state_floor")
            self.assertEqual(config["optimizer"], "mma")
            self.assertEqual(config["move_limit"], 0.05)
            self.assertEqual(config["boundary_model"], "slit_pml")
            self.assertEqual(config["pml_curvature"], 3)
            v = 2 * math.pi / (config["wavelength_nm"] * 1e-9) * 0.2e-6 * math.sqrt(12.1 - 2.1)
            self.assertEqual(math.ceil(math.nextafter(2 * v / math.pi, -math.inf)), config["guided_modes"])
        self.assertEqual(startup["gradient0"]["training_band"], "single")
        self.assertEqual(startup["gradient1"]["training_band"], "single")
        self.assertEqual(startup["coarse"]["training_band"], "five")
        self.assertEqual(startup["fine"]["training_band"], "five")
        expected = {
            "warmup": (8, 1, 2, 9),
            "coarse": (32, 1, 2, 33),
            "projection": (40, 2, 4, 41),
            "sharpen": (40, 1, 16, 41),
            "fine": (40, 1, 32, 41),
        }
        for name, controls in expected.items():
            self.assertEqual(
                tuple(startup[name][key] for key in ("iterations", "stages", "beta", "evaluation_limit")), controls
            )
            self.assertEqual(startup[name]["training_band"], "five")
        self.assertEqual((startup["fine"]["mesh_um"], startup["fine"]["cladding_mesh_um"]), (0.025, 0.10))
        self.assertEqual(recipe["contour_symmetry"], "mirror_xy")
        changes = dict(recipe["validation"])
        self.assertEqual(changes["mesh020"]["cladding_mesh_um"], 0.08)
        self.assertEqual(changes["mesh015"]["cladding_mesh_um"], 0.06)
        self.assertGreater(changes["boundary"]["outer_half_um"], nominal["outer_half_um"])
        self.assertGreater(changes["boundary"]["port_half_um"], nominal["port_half_um"])
        self.assertIn("training wavelength", recipe["validation_roles"]["wave1520"])
        self.assertIn("training wavelength", recipe["validation_roles"]["wave1536"])
        self.assertIn("Held-out", recipe["validation_roles"]["holdout1543_3"])

    def test_locked_budget_and_seven_discrete_wavelengths(self):
        recipe = campaign.plan()
        self.assertEqual(
            recipe["budget_breakdown"],
            {
                "gradient_and_optimization": 11,
                "binary_candidates": 6,
                "locked_validation": 19,
            },
        )
        self.assertEqual(recipe["native_job_budget_max"], sum(recipe["budget_breakdown"].values()))
        gradients = [config for _, config in recipe["startup"] if config["mode"] == "gradient"]
        self.assertEqual(
            {(config["direction"], config["wavelength_nm"]) for config in gradients},
            {(0, wavelength) for wavelength in campaign.TRAINING_WAVELENGTHS} | {(1, 1550)},
        )
        nominal = recipe["binary_nominal"]
        self.assertEqual((nominal["mesh_um"], nominal["cladding_mesh_um"]), (0.025, 0.10))
        self.assertEqual(
            (nominal["pml_thickness_um"], nominal["pml_scale"], nominal["projection_offset_um"]), (0.8, 1, 0.2)
        )
        configurations = {name: nominal | changes for name, changes in recipe["validation"]}
        self.assertEqual(len(configurations), 19)
        self.assertEqual(len(recipe["convergence_pairs"]), 13)
        self.assertEqual(recipe["convergence_tolerances"], {
            "eta": 0.005, "all_input_eta": 0.005, "fidelity": 0.002, "ratio": 0.02
        })
        self.assertEqual([name for name, _ in recipe["validation"][-2:]], ["holdout1543_3", "holdout1572_3"])
        self.assertEqual(
            {config["wavelength_nm"] for config in configurations.values()},
            set(campaign.TRAINING_WAVELENGTHS + campaign.HOLDOUT_WAVELENGTHS),
        )
        for _, (reference, comparison) in recipe["convergence_pairs"].items():
            baseline = nominal if reference == "selected_binary" else configurations[reference]
            self.assertEqual(baseline["wavelength_nm"], configurations[comparison]["wavelength_nm"])
        self.assertEqual(configurations["pml"]["pml_thickness_um"], 1.2)
        self.assertEqual(configurations["wave1536_pml"]["pml_scale"], 2)
        self.assertEqual(configurations["projection"]["projection_offset_um"], 0.4)
        self.assertEqual(configurations["wave1536_projection"]["projection_offset_um"], 0.4)

    def test_endpoint_convergence_configuration_matches_wavelength_and_mesh(self):
        changes = dict(campaign.plan()["validation"])
        for name in ("wave1520", "wave1536", "wave1580"):
            reference = changes[name]
            fine = changes[f"{name}_mesh015"]
            boundary = changes[f"{name}_boundary"]
            self.assertEqual(reference["wavelength_nm"], fine["wavelength_nm"])
            self.assertEqual(reference["wavelength_nm"], boundary["wavelength_nm"])
            self.assertEqual((fine["mesh_um"], fine["cladding_mesh_um"]), (0.015, 0.06))
            self.assertEqual(
                (boundary["mesh_um"], boundary["cladding_mesh_um"]),
                (reference["mesh_um"], reference["cladding_mesh_um"]),
            )
            self.assertGreater(boundary["outer_half_um"], campaign.plan()["binary_nominal"]["outer_half_um"])

    def test_training_prechecks_require_actual_receipt_and_console_records(self):
        config = dict(campaign.plan()["startup"])["coarse"] | {"stages": 4}
        receipt, console = training_fixture(config)
        evidence = campaign.optimization_prechecks(receipt, console, config)
        self.assertEqual(len(evidence["training_stages"]), 4)
        self.assertTrue(all(len(stage["points"]) == 5 for stage in evidence["training_stages"].values()))
        for faulty_receipt, faulty_console in (
            ({}, console),
            (receipt, console.replace("VERIFIED=min", "VERIFIED=auto")),
            (receipt, console + "\nTRAINING_POINT=1,1550,0.8"),
        ):
            with self.assertRaises(RuntimeError):
                campaign.optimization_prechecks(faulty_receipt, faulty_console, config)
        invalid = {"training_observations": [line.replace(",0.8", ",NaN") for line in receipt["training_observations"]]}
        invalid_console = "\n".join([*console.splitlines()[:2], *invalid["training_observations"]])
        with self.assertRaises(RuntimeError):
            campaign.optimization_prechecks(invalid, invalid_console, config)

    def test_training_missing_wavelength_and_wrong_exact_objective_fail_closed(self):
        config = dict(campaign.plan()["startup"])["coarse"] | {"stages": 4, "objective_profile": "state_floor"}
        receipt, console = training_fixture(config)
        marker = console.splitlines()[0]
        controls = console.splitlines()[1]
        observations = receipt["training_observations"]
        for defective in (
            [line for line in observations if line != "TRAINING_POINT=2,1536.61,0.8"],
            [line.replace("TRAINING_POINT=2,1536.61,", "TRAINING_POINT=2,1550.0,") for line in observations],
            [line.replace("TRAINING_MINIMUM=2,1580.0,0.8", "TRAINING_MINIMUM=2,1580.0,0.7") for line in observations],
        ):
            with self.assertRaises(RuntimeError):
                campaign.optimization_prechecks(
                    {"training_observations": defective}, "\n".join([marker, controls, *defective]), config
                )
        for wrong in (
            marker + "unreviewed_suffix",
            marker.replace("comp1.modal_a3", "comp1.ewfd.S31"),
            marker.replace("-sqrt(4*realdot(comp1.modal_a3,comp1.modal_a4)^2+1e-8)", ""),
            marker + "\n" + marker,
        ):
            with self.assertRaises(RuntimeError):
                campaign.optimization_prechecks(receipt, "\n".join([wrong, controls, *observations]), config)

    def test_optimizer_readback_binds_method_move_and_evaluation_budget(self):
        config = dict(campaign.plan()["startup"])["coarse"] | {
            "optimizer": "gcmma", "move_limit": 0.0274653, "evaluation_limit": 20
        }
        receipt, console = training_fixture(config)
        controls = console.splitlines()[1]
        evidence = campaign.optimization_prechecks(receipt, console, config)
        self.assertEqual(evidence["optimizer_controls"], {
            "method": "gcmma", "move_limit": 0.0274653, "evaluation_limit_per_stage": 20
        })
        for replacement in ("", controls + "\n" + controls, controls.replace("gcmma", "mma"),
                            controls.replace("0.0274653", "0.05"), controls.replace("0.0274653", "NaN"),
                            controls.replace(",20", ",21"), controls.replace(",20", ",20.5")):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(RuntimeError, "control"):
                campaign.optimization_prechecks(receipt, console.replace(controls, replacement), config)

    def test_legacy_single_and_three_training_prechecks(self):
        for band in ("single", "three"):
            config = {"training_band": band, "wavelength_nm": 1550, "stages": 1}
            receipt, console = training_fixture(config)
            evidence = campaign.optimization_prechecks(receipt, console, config)
            self.assertEqual(len(evidence["training_stages"][1]["points"]), 1 if band == "single" else 3)

    def test_execution_failure_stops_and_records(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = campaign.Campaign(Path(temp), Path("solver"), 8, 7200)
            with patch.object(runner, "subprocess", return_value=1), self.assertRaises(RuntimeError):
                runner.native("failed", {"mode": "gradient"})
            self.assertEqual(len(runner.document["runs"]), 1)
            self.assertEqual(runner.document["runs"][0]["status"], "execution_failure")
            self.assertIsNone(runner.document["runs"][0]["receipt"])

    def test_receipt_console_hash_binds_optimization_markers(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            runner = campaign.Campaign(output, Path("solver"), 8, 7200)
            config = dict(campaign.plan()["startup"])["coarse"]
            folder = output / "coarse"
            folder.mkdir()
            (folder / "plan.json").write_text(json.dumps({"config": config}), encoding="utf-8")
            receipt, console = training_fixture(config)
            (folder / "console.log").write_text(console, encoding="utf-8")
            receipt.update(
                completed=True,
                artifacts={
                    "plan.json": {"sha256": campaign.digest(folder / "plan.json")},
                    "console.log": {"sha256": "0" * 64},
                },
            )
            (folder / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            with (
                patch.object(runner, "subprocess", return_value=0) as process,
                self.assertRaisesRegex(RuntimeError, "artifact mismatch"),
            ):
                runner.native("coarse", config)
            self.assertEqual(process.call_count, 1)

    def test_job_budget_exhaustion_precedes_execution_or_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = campaign.Campaign(Path(temp), Path("solver"), 8, 7200)
            runner.document["cost"]["native_jobs"] = 36
            with (
                patch.object(runner, "subprocess") as process,
                self.assertRaisesRegex(RuntimeError, "budget exhausted"),
            ):
                runner.native("over_budget", {"mode": "gradient"})
            process.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_startup_dispatches_each_restart_after_its_source(self):
        recipe = campaign.plan()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            runner = campaign.Campaign(output, Path("solver"), 8, 7200)
            observed = []

            def native(name, config, restart=None, mask=None):
                if name in recipe["restart_sources"]:
                    source = recipe["restart_sources"][name]
                    self.assertIn(source, observed)
                    self.assertEqual(restart, output / source / "final.mph")
                    self.assertEqual(restart.read_bytes(), source.encode())
                else:
                    self.assertIsNone(restart)
                observed.append(name)
                if config["mode"] == "optimize":
                    (output / name).mkdir()
                    (output / name / "final.mph").write_bytes(name.encode())

            with (patch.object(runner, "native", side_effect=native),
                  patch.object(runner, "qualify_binary", return_value=0) as qualify):
                self.assertEqual(runner.run(), 0)
            self.assertEqual(observed, [name for name, _ in recipe["startup"]])
            self.assertEqual(recipe["restart_sources"], {
                "coarse": "warmup", "projection": "coarse", "sharpen": "projection", "fine": "sharpen"
            })
            qualify.assert_called_once_with(output / "fine/density.txt")

    def test_coarse_restart_regenerates_solver_as_in_exercised_lineage(self):
        recipe = campaign.plan()
        startup = dict(recipe["startup"])
        self.assertIs(startup["coarse"]["reconfigure_restart"], True)
        self.assertEqual(recipe["restart_sources"]["coarse"], "warmup")
        for name, config in recipe["startup"]:
            if name != "coarse":
                with self.subTest(name=name):
                    self.assertIs(config.get("reconfigure_restart", False), False)

    def test_restart_requires_observed_source_and_existing_checkpoint(self):
        recipe = campaign.plan()
        for defect in ("missing_checkpoint", "unobserved_source"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                runner = campaign.Campaign(output, Path("solver"), 8, 7200)
                broken = recipe.copy()
                if defect == "unobserved_source":
                    (output / "warmup").mkdir()
                    (output / "warmup/final.mph").write_bytes(b"stale checkpoint")
                    broken["startup"] = [("coarse", dict(recipe["startup"])["coarse"])]
                expected = "Restart source is missing" if defect == "missing_checkpoint" else "must be observed"
                with (patch.object(campaign, "plan", return_value=broken),
                      patch.object(runner, "native") as native,
                      patch.object(runner, "qualify_binary") as qualify,
                      self.assertRaisesRegex(RuntimeError, expected)):
                    runner.run()
                self.assertEqual(native.call_count, 7 if defect == "missing_checkpoint" else 0)
                self.assertFalse(any(call.args[0] == "coarse" for call in native.call_args_list))
                qualify.assert_not_called()

    def test_locked_pipeline_with_fake_results_only(self):
        class Fake(campaign.Campaign):
            def native(self, name, config, restart=None, mask=None):
                self.document["cost"]["native_jobs"] += 1
                row = {"name": name, "config": config}
                if config["mode"] == "optimize":
                    row["receipt"], console = training_fixture(config)
                    row["optimization_prechecks"] = campaign.optimization_prechecks(row["receipt"], console, config)
                    folder = self.output / name
                    folder.mkdir()
                    (folder / "final.mph").write_bytes(b"mock checkpoint")
                self.document["runs"].append(row)
                if name.startswith("gradient"):
                    return None
                if name.startswith("binary"):
                    index = int(name[-1])
                    return report(passed=index == 3, f=(3 - index) * 0.05)
                return report()

            def subprocess(self, command, log):
                self.assertion = command
                folder = Path(command[command.index("--output") + 1])
                folder.mkdir()
                (folder / "mask.json").write_text('{"polygons":[]}')
                return 0

        with tempfile.TemporaryDirectory() as temp:
            runner = Fake(Path(temp), Path("solver"), 8, 7200)
            self.assertEqual(runner.run(), 0)
            self.assertEqual(runner.document["status"], "pass")
            self.assertEqual(runner.document["cost"]["native_jobs"], 33)
            self.assertEqual(runner.document["selection"]["name"], "binary3")
            validations = runner.document["runs"][-19:]
            self.assertEqual([row["name"] for row in validations], [name for name, _ in campaign.plan()["validation"]])
            self.assertTrue(runner.document["summary"]["mask_locked_before_validation"])
            self.assertTrue(runner.document["summary"]["locked_validation_complete"])
            self.assertEqual(runner.document["summary"]["unspent_locked_checks"], [])
            self.assertEqual(runner.assertion[runner.assertion.index("--symmetry") + 1], "mirror_xy")
            self.assertEqual(
                set(runner.document["summary"]["convergence"]),
                set(campaign.plan()["convergence_pairs"]),
            )

    def test_six_failed_candidates_never_validate_or_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = campaign.Campaign(Path(temp), Path("solver"), 8, 7200)

            def extraction(command, log):
                folder = Path(command[command.index("--output") + 1])
                folder.mkdir()
                (folder / "mask.json").write_text('{"polygons":[]}')
                return 0

            with (
                patch.object(runner, "native", return_value=report(False, 0.1)) as native,
                patch.object(runner, "subprocess", side_effect=extraction),
            ):
                self.assertEqual(runner.qualify_binary(Path(temp) / "density.txt"), 2)
            self.assertEqual(native.call_count, 6)
            self.assertEqual(len(runner.document["candidates"]), 6)
            self.assertEqual(runner.document["status"], "scientific_failure")
            self.assertIsNone(runner.document["selection"])
            self.assertEqual(len({row["threshold"] for row in runner.document["candidates"]}), 6)

    def test_any_locked_acceptance_or_convergence_failure_prevents_pass(self):
        for failure in ("acceptance", "all_input_eta"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                runner = campaign.Campaign(Path(temp), Path("solver"), 8, 7200)

                def extraction(command, log):
                    folder = Path(command[command.index("--output") + 1])
                    folder.mkdir()
                    (folder / "mask.json").write_text('{"polygons":[]}')
                    return 0

                def native(name, config, restart=None, mask=None, failure=failure):
                    result = report()
                    # Gray optimizer acceptance is diagnostic; it never selects the binary mask.
                    if name in ("coarse", "fine"):
                        result["acceptance_pass"] = False
                    if name == "wave1536_projection":
                        if failure == "acceptance":
                            result["acceptance_pass"] = False
                        else:
                            result["minimum_target_throughput_all_inputs"] -= 0.006
                    return result

                with (
                    patch.object(runner, "native", side_effect=native) as native_calls,
                    patch.object(runner, "subprocess", side_effect=extraction),
                ):
                    self.assertEqual(runner.qualify_binary(Path(temp) / "density.txt"), 2)
                self.assertEqual(runner.document["status"], "scientific_failure")
                self.assertEqual(runner.document["selection"]["name"], "binary1")
                summary = runner.document["summary"]
                self.assertFalse(summary["locked_validation_complete"])
                self.assertFalse(summary["all_locked_validation_full_pass"])
                self.assertEqual(summary["first_failed_locked_check"], "wave1536_projection")
                self.assertEqual(native_calls.call_args.args[0], "wave1536_projection")
                self.assertFalse(any(call.args[0].startswith("holdout") for call in native_calls.call_args_list))
                self.assertIn("holdout1543_3", summary["unspent_locked_checks"])
                self.assertIn("holdout1572_3", summary["unspent_locked_checks"])
                if failure == "acceptance":
                    self.assertFalse(summary["observed_locked_runs_pass"])
                else:
                    self.assertTrue(summary["observed_locked_runs_pass"])
                    self.assertFalse(summary["convergence"]["wave1536_projection"]["all_input_eta"]["pass"])

    def test_failed_first_holdout_preserves_second_and_never_reports_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            runner = campaign.Campaign(Path(temp), Path("solver"), 8, 7200)

            def extraction(command, log):
                folder = Path(command[command.index("--output") + 1])
                folder.mkdir()
                (folder / "mask.json").write_text('{"polygons":[]}')
                return 0

            def native(name, config, restart=None, mask=None):
                return report(name != "holdout1543_3")

            with (
                patch.object(runner, "native", side_effect=native) as calls,
                patch.object(runner, "subprocess", side_effect=extraction),
            ):
                self.assertEqual(runner.qualify_binary(Path(temp) / "density.txt"), 2)
            summary = runner.document["summary"]
            self.assertFalse(summary["locked_validation_complete"])
            self.assertFalse(summary["all_locked_validation_full_pass"])
            self.assertEqual(summary["unspent_locked_checks"], ["holdout1572_3"])
            self.assertEqual(calls.call_args.args[0], "holdout1543_3")


if __name__ == "__main__":
    unittest.main()
