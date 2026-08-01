from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from photonic_workflow.models import (
    AcceptanceResult,
    AcceptanceStatus,
    ExecutionStatus,
    RunManifest,
    RunSpec,
    RunStatus,
)
from photonic_workflow.runtime import (
    CHECKPOINT_HASHED_FILES,
    REQUIRED_RUN_FILES,
    RunStore,
)


def run_spec(name: str = "fixture run") -> RunSpec:
    return RunSpec(
        stable_id="run-spec:fixture",
        name=name,
        source="unit test",
        operation="fixture",
        adapter="mock",
        inputs={"geometry": "mock"},
        expected_artifacts=[],
    )


class RunStoreTests(unittest.TestCase):
    def test_run_files_state_transitions_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RunStore(root)
            manifest = store.create(run_spec(), run_id="run-fixture")
            directory = root / "runs" / "run-fixture"
            self.assertTrue(all((directory / name).exists() for name in REQUIRED_RUN_FILES))
            self.assertEqual(manifest.execution_status, ExecutionStatus.PLANNED)

            store.transition_execution("run-fixture", ExecutionStatus.RUNNING)
            succeeded = store.transition_execution("run-fixture", ExecutionStatus.SUCCEEDED)
            self.assertEqual(succeeded.status, RunStatus.SUCCEEDED)
            self.assertEqual(succeeded.acceptance_status, AcceptanceStatus.PENDING)
            self.assertIsNotNone(succeeded.finished_at)
            self.assertTrue(store.recover("run-fixture")["recoverable"])

    def test_successful_tool_run_can_be_physically_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RunStore(Path(temporary))
            store.create(run_spec(), run_id="rejected-run")
            store.transition_execution("rejected-run", ExecutionStatus.RUNNING)
            store.transition_execution("rejected-run", ExecutionStatus.SUCCEEDED)
            criterion = AcceptanceResult(
                stable_id="acceptance:fixture",
                name="fixture criterion result",
                source="unit test",
                criterion_id="criterion:fixture",
                passed=False,
                reason="physics threshold not met",
            )
            manifest = store.record_acceptance("rejected-run", [criterion])
            self.assertEqual(manifest.execution_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(manifest.acceptance_status, AcceptanceStatus.REJECTED)
            self.assertEqual(manifest.status, RunStatus.REJECTED)
            self.assertIsNone(store.latest_trusted_run())

    def test_latest_trusted_run_requires_success_acceptance_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RunStore(Path(temporary))
            store.create(run_spec(), run_id="accepted-run")
            store.transition_execution("accepted-run", ExecutionStatus.RUNNING)
            store.transition_execution("accepted-run", ExecutionStatus.SUCCEEDED)
            result = AcceptanceResult(
                stable_id="acceptance:pass",
                name="passing result",
                source="unit test",
                criterion_id="criterion:pass",
                passed=True,
                reason="fixture passed",
                evidence=["fixture.json"],
            )
            store.record_acceptance("accepted-run", [result])
            trusted = store.latest_trusted_run()
            self.assertIsNotNone(trusted)
            self.assertEqual(trusted.stable_id, "accepted-run")

    def test_loads_legacy_status_only_manifest_into_authoritative_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RunStore(root)
            store.create(run_spec(), run_id="legacy-run")
            path = root / "runs" / "legacy-run" / "run.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.pop("execution_status")
            payload.pop("acceptance_status")
            payload["status"] = "accepted"
            path.write_text(json.dumps(payload), encoding="utf-8")

            manifest = store.load("legacy-run")

            self.assertEqual(manifest.execution_status, ExecutionStatus.SUCCEEDED)
            self.assertEqual(manifest.acceptance_status, AcceptanceStatus.ACCEPTED)
            self.assertEqual(manifest.status, RunStatus.ACCEPTED)

    def test_manifest_rejects_conflicting_legacy_and_authoritative_status(self) -> None:
        with self.assertRaisesRegex(ValidationError, "legacy status conflicts"):
            RunManifest(
                stable_id="run:conflict",
                name="conflicting run",
                source="unit test",
                status=RunStatus.FAILED,
                execution_status=ExecutionStatus.SUCCEEDED,
                acceptance_status=AcceptanceStatus.PENDING,
            )

    def test_recovery_rejects_incomplete_or_wrong_checkpoint_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RunStore(root)
            store.create(run_spec(), run_id="checkpoint-run")
            checkpoint_path = root / "runs" / "checkpoint-run" / "checkpoint.json"
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            checkpoint["hashes"].pop(CHECKPOINT_HASHED_FILES[-1])
            checkpoint["run_id"] = "another-run"
            checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

            recovery = store.recover("checkpoint-run")

            self.assertFalse(recovery["recoverable"])
            self.assertIn(
                "checkpoint.json run_id does not match its directory",
                recovery["mismatches"],
            )
            self.assertIn(
                f"checkpoint hash is missing: {CHECKPOINT_HASHED_FILES[-1]}",
                recovery["mismatches"],
            )

    def test_recovery_parses_hashed_state_not_only_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RunStore(root)
            store.create(run_spec(), run_id="semantic-run")
            directory = root / "runs" / "semantic-run"
            (directory / "events.jsonl").write_text(
                '{"schema_version":"1.0","timestamp":"bad","event":"x","data":{}}\n',
                encoding="utf-8",
            )
            store._checkpoint("semantic-run")

            recovery = store.recover("semantic-run")

            self.assertFalse(recovery["recoverable"])
            self.assertIn(
                "events.jsonl line 1 timestamp is invalid",
                recovery["mismatches"],
            )

    def test_invalid_manifest_recovery_is_structured_and_not_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RunStore(root)
            store.create(run_spec(), run_id="broken-run")
            directory = root / "runs" / "broken-run"
            (directory / "run.json").write_text("{broken", encoding="utf-8")
            store._checkpoint("broken-run")

            recovery = store.recover("broken-run")

            self.assertFalse(recovery["recoverable"])
            self.assertIsNone(recovery["manifest"])
            self.assertTrue(
                any(item.startswith("run.json is invalid:") for item in recovery["mismatches"])
            )
            self.assertIsNone(store.latest_trusted_run())

    def test_failed_create_does_not_leave_a_partial_named_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = RunStore(root)
            with patch(
                "photonic_workflow.runtime.store.atomic_write_text",
                side_effect=OSError("injected write failure"),
            ), self.assertRaisesRegex(OSError, "injected write failure"):
                store.create(run_spec(), run_id="atomic-create")
            self.assertFalse((root / "runs" / "atomic-create").exists())
            leftovers = list((root / "runs").glob(".atomic-create.*.tmp"))
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
