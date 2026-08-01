from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from photonic_workflow.application import ProjectStatusService
from photonic_workflow.cli import main
from photonic_workflow.config import load_project_config, project_config_toml
from photonic_workflow.mcp.server import PhotonicMcpServer
from photonic_workflow.models import AcceptanceResult, ExecutionStatus, RunSpec
from photonic_workflow.project import create_project_scaffold
from photonic_workflow.runtime import RunStore


def _invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(arguments)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _accepted_run(project: Path) -> None:
    store = RunStore(project)
    store.create(
        RunSpec(
            stable_id="run-spec:status-parity",
            name="status parity fixture",
            source="integration test",
            operation="fixture",
            adapter="mock",
            inputs={},
            expected_artifacts=[],
        ),
        run_id="run-accepted",
    )
    store.transition_execution("run-accepted", ExecutionStatus.RUNNING)
    store.transition_execution("run-accepted", ExecutionStatus.SUCCEEDED)
    store.record_acceptance(
        "run-accepted",
        [
            AcceptanceResult(
                stable_id="acceptance:status-parity",
                name="status parity acceptance",
                source="integration test",
                criterion_id="criterion:status-parity",
                passed=True,
                reason="fixture passed",
                evidence=["fixture.json"],
            )
        ],
    )


class ProjectStatusParityTests(unittest.TestCase):
    def test_cli_and_mcp_return_the_same_bounded_business_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            create_project_scaffold(project)
            _accepted_run(project)
            _, config = load_project_config(project)
            config = config.model_copy(
                update={
                    "instrument_aliases": {
                        "credential": "api_key=status-parity-secret",
                    }
                }
            )
            (project / "photonic.toml").write_text(
                project_config_toml(config),
                encoding="utf-8",
            )

            expected = ProjectStatusService(
                project,
                read_roots=[project],
            ).inspect().to_payload()
            cli_exit, cli_output, cli_error = _invoke(
                ["status", "--project-root", str(project), "--json"]
            )
            server = PhotonicMcpServer(
                root / "skill",
                read_roots=[project],
                write_roots=[],
            )
            mcp = server.tool_call(
                "inspect_project",
                {"project_root": str(project)},
            )["structuredContent"]

            self.assertEqual((cli_exit, cli_error), (0, ""))
            cli = json.loads(cli_output)["data"]
            self.assertEqual(cli, expected)
            self.assertEqual(mcp, expected)
            self.assertNotIn("config", mcp)
            self.assertNotIn("status-parity-secret", json.dumps(mcp))


if __name__ == "__main__":
    unittest.main()
