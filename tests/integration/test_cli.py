from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from photonic_workflow import __version__
from photonic_workflow.cli import main

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(arguments)
    return exit_code, stdout.getvalue(), stderr.getvalue()


class CliIntegrationTests(unittest.TestCase):
    def test_version_init_check_status_and_mock_pdk_json(self) -> None:
        version_exit, version_output, _ = invoke(["--version"])
        self.assertEqual(version_exit, 0)
        self.assertIn(__version__, version_output)

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "cli-project"
            init_exit, init_output, init_error = invoke(
                ["init", str(project), "--device-family", "mzi", "--json"]
            )
            self.assertEqual((init_exit, init_error), (0, ""))
            init_payload = json.loads(init_output)
            self.assertEqual(init_payload["data"]["template_kind"], "mzi-4port")
            self.assertTrue((project / "requirements.txt").is_file())

            for command in ("check", "status"):
                exit_code, output, error = invoke(
                    [command, "--project-root", str(project), "--json"]
                )
                self.assertEqual((exit_code, error), (0, ""))
                payload = json.loads(output)
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["exit_code"], 0)

            doctor_exit, doctor_output, doctor_error = invoke(
                ["doctor", "--project-root", str(project), "--json"]
            )
            self.assertEqual((doctor_exit, doctor_error), (0, ""))
            doctor = json.loads(doctor_output)["data"]
            self.assertEqual(len(doctor["optional"]), 10)
            self.assertGreaterEqual(len(doctor["adapters"]), 17)
            optional_by_capability = {
                report["capability"]: report for report in doctor["optional"]
            }
            for capability in (
                "gdsfactory-layout",
                "sax-circuit-simulation",
                "meep-full-wave",
                "femwell-finite-element",
                "tidy3d-simulation",
            ):
                self.assertEqual(
                    optional_by_capability[capability]["implementation"],
                    "planned",
                )

        pdk_exit, pdk_output, pdk_error = invoke(
            ["pdk", "validate", str(FIXTURE_ROOT / "mock_pdk.json"), "--json"]
        )
        self.assertEqual((pdk_exit, pdk_error), (0, ""))
        self.assertTrue(json.loads(pdk_output)["data"]["valid"])

    def test_missing_matlab_is_structured_unavailable(self) -> None:
        exit_code, output, error = invoke(
            [
                "matlab",
                "check",
                "--executable",
                "matlab_photonic_fixture_missing.exe",
                "--json",
            ]
        )
        self.assertEqual(error, "")
        self.assertEqual(exit_code, 3)
        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "unavailable_capability")
        self.assertEqual(payload["data"]["availability"], "unavailable")

    def test_incompatible_contract_schema_has_distinct_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "future-pdk.json"
            payload = json.loads(
                (FIXTURE_ROOT / "mock_pdk.json").read_text(encoding="utf-8")
            )
            payload["schema_version"] = "2.0"
            path.write_text(json.dumps(payload), encoding="utf-8")

            exit_code, output, error = invoke(
                ["pdk", "validate", str(path), "--json"]
            )

        self.assertEqual(error, "")
        self.assertEqual(exit_code, 4)
        response = json.loads(output)
        self.assertFalse(response["ok"])
        self.assertEqual(response["exit_code"], 4)
        self.assertEqual(response["status"], "incompatible_version")

    def test_backend_adoption_cli_is_fail_closed_and_dry_run_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "adoption-project"
            init_exit, _, init_error = invoke(
                ["init", str(project), "--json"]
            )
            self.assertEqual((init_exit, init_error), (0, ""))
            gate_path = (
                project
                / "verification"
                / "adoption"
                / "matlab-runtime.json"
            )

            empty_list_exit, empty_list_output, empty_list_error = invoke(
                [
                    "gate",
                    "adoption",
                    "list",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((empty_list_exit, empty_list_error), (0, ""))
            empty_inventory = json.loads(empty_list_output)["data"]["targets"]
            self.assertEqual(len(empty_inventory), 7)
            self.assertTrue(all(not item["initialized"] for item in empty_inventory))
            self.assertTrue(all(item["status"] == "blocked" for item in empty_inventory))

            preview_exit, preview_output, preview_error = invoke(
                [
                    "gate",
                    "adoption",
                    "init",
                    "matlab-runtime",
                    "--project-root",
                    str(project),
                    "--dry-run",
                    "--json",
                ]
            )
            self.assertEqual((preview_exit, preview_error), (0, ""))
            preview = json.loads(preview_output)["data"]
            self.assertTrue(preview["dry_run"])
            self.assertEqual(preview["record"]["status"], "blocked")
            self.assertFalse(gate_path.exists())

            create_exit, create_output, create_error = invoke(
                [
                    "gate",
                    "adoption",
                    "init",
                    "matlab-runtime",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((create_exit, create_error), (0, ""))
            created = json.loads(create_output)["data"]
            self.assertFalse(created["dry_run"])
            self.assertTrue(gate_path.is_file())
            evidence_path = project / "verification" / "matlab-capability.json"
            evidence_path.write_text("{}\n", encoding="utf-8")

            overwrite_exit, overwrite_output, overwrite_error = invoke(
                [
                    "gate",
                    "adoption",
                    "init",
                    "matlab-runtime",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual(overwrite_error, "")
            self.assertEqual(overwrite_exit, 2)
            self.assertIn("already exists", json.loads(overwrite_output)["errors"][0])

            list_exit, list_output, list_error = invoke(
                [
                    "gate",
                    "adoption",
                    "list",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((list_exit, list_error), (0, ""))
            inventory = json.loads(list_output)["data"]["targets"]
            matlab = next(
                item for item in inventory
                if item["target"] == "matlab-runtime"
            )
            self.assertTrue(matlab["initialized"])
            self.assertEqual(matlab["status"], "blocked")

            record_preview_exit, record_preview_output, record_preview_error = invoke(
                [
                    "gate",
                    "adoption",
                    "record",
                    "matlab-runtime",
                    "capability-probe",
                    "pass",
                    "--evidence",
                    "verification/matlab-capability.json",
                    "--reason",
                    "fixed local probe passed",
                    "--project-root",
                    str(project),
                    "--dry-run",
                    "--json",
                ]
            )
            self.assertEqual(
                (record_preview_exit, record_preview_error),
                (0, ""),
            )
            preview_record = json.loads(record_preview_output)["data"]["record"]
            self.assertEqual(preview_record["checks"][0]["status"], "pass")
            on_disk = json.loads(gate_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["checks"][0]["status"], "blocked")

            record_exit, record_output, record_error = invoke(
                [
                    "gate",
                    "adoption",
                    "record",
                    "matlab-runtime",
                    "capability-probe",
                    "pass",
                    "--evidence",
                    "verification/matlab-capability.json",
                    "--reason",
                    "fixed local probe passed",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((record_exit, record_error), (0, ""))
            recorded = json.loads(record_output)["data"]["record"]
            self.assertEqual(recorded["status"], "blocked")
            self.assertEqual(recorded["checks"][0]["status"], "pass")

            evaluate_exit, evaluate_output, evaluate_error = invoke(
                [
                    "gate",
                    "adoption",
                    "evaluate",
                    "matlab-runtime",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((evaluate_exit, evaluate_error), (0, ""))
            evaluated = json.loads(evaluate_output)["data"]["record"]
            self.assertEqual(evaluated["status"], "blocked")
            self.assertIn("remain blocked", evaluated["reason"])

            inspect_exit, inspect_output, inspect_error = invoke(
                [
                    "gate",
                    "adoption",
                    "inspect",
                    "matlab-runtime",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((inspect_exit, inspect_error), (0, ""))
            inspected = json.loads(inspect_output)["data"]["record"]
            self.assertEqual(inspected, evaluated)


if __name__ == "__main__":
    unittest.main()
