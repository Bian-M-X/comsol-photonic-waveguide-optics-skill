from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from photonic_workflow.application import (
    MAX_PROJECT_STATUS_RUNS,
    ProjectStatusService,
)
from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import (
    AcceptanceResult,
    ExecutionStatus,
    RunSpec,
)
from photonic_workflow.project import create_project_scaffold
from photonic_workflow.runtime import RunStore


def _run_spec() -> RunSpec:
    return RunSpec(
        stable_id="run-spec:application-status",
        name="application status fixture",
        source="unit test",
        operation="fixture",
        adapter="mock",
        inputs={"geometry": "mock"},
        expected_artifacts=[],
    )


def _create_project(root: Path) -> Path:
    project = root / "project"
    create_project_scaffold(project)
    return project


class ProjectStatusServiceTests(unittest.TestCase):
    def test_run_window_has_a_strict_twenty_run_upper_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _create_project(Path(temporary))
            for index in range(MAX_PROJECT_STATUS_RUNS + 5):
                (project / "runs" / f"run-{index:02d}").mkdir()
            recovery = {
                "run_id": "fixture",
                "recoverable": False,
                "missing": ["run.json"],
                "mismatches": [],
                "manifest": None,
            }

            with patch(
                "photonic_workflow.application.RunStore.recover",
                return_value=recovery,
            ) as recover:
                payload = ProjectStatusService(
                    project,
                    read_roots=[project],
                ).inspect().to_payload()

            self.assertEqual(len(payload["runs"]), MAX_PROJECT_STATUS_RUNS)
            self.assertEqual(recover.call_count, MAX_PROJECT_STATUS_RUNS)
            self.assertEqual(
                [call.args[0] for call in recover.call_args_list],
                [f"run-{index:02d}" for index in range(24, 4, -1)],
            )

            service = ProjectStatusService(project, read_roots=[project])
            for invalid_limit in (0, -1, MAX_PROJECT_STATUS_RUNS + 1, True):
                with self.subTest(limit=invalid_limit), self.assertRaises(InvalidInputError):
                    service.inspect(run_limit=invalid_limit)

    def test_corrupt_run_has_structured_recovery_and_is_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _create_project(Path(temporary))
            store = RunStore(project)
            store.create(_run_spec(), run_id="run-corrupt")
            (project / "runs" / "run-corrupt" / "run.json").write_text(
                "{broken",
                encoding="utf-8",
            )

            payload = ProjectStatusService(
                project,
                read_roots=[project],
            ).inspect().to_payload()

            self.assertIsNone(payload["latest_trusted_run"])
            self.assertEqual(len(payload["runs"]), 1)
            corrupt = payload["runs"][0]
            self.assertEqual(corrupt["run_id"], "run-corrupt")
            self.assertEqual(corrupt["status"], "corrupt")
            self.assertEqual(
                set(corrupt["recovery"]),
                {"recoverable", "missing", "mismatches"},
            )
            self.assertFalse(corrupt["recovery"]["recoverable"])
            self.assertTrue(corrupt["recovery"]["mismatches"])

    def test_latest_trusted_run_and_gate_summary_share_the_bounded_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = _create_project(Path(temporary))
            store = RunStore(project)
            store.create(_run_spec(), run_id="run-accepted")
            store.transition_execution("run-accepted", ExecutionStatus.RUNNING)
            store.transition_execution("run-accepted", ExecutionStatus.SUCCEEDED)
            store.record_acceptance(
                "run-accepted",
                [
                    AcceptanceResult(
                        stable_id="acceptance:application-status",
                        name="application status acceptance",
                        source="unit test",
                        criterion_id="criterion:application-status",
                        passed=True,
                        reason="fixture passed",
                        evidence=["fixture.json"],
                    )
                ],
            )

            payload = ProjectStatusService(
                project,
                read_roots=[project],
            ).inspect().to_payload()

            self.assertEqual(
                payload["latest_trusted_run"]["stable_id"],
                "run-accepted",
            )
            self.assertEqual(payload["runs"][0]["status"], "accepted")
            self.assertEqual(len(payload["gates"]["gates"]), 14)
            self.assertFalse(payload["gates"]["all_gates_passed"])


if __name__ == "__main__":
    unittest.main()
