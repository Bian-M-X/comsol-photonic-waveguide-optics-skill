from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from photonic_workflow.exceptions import SecurityViolationError
from photonic_workflow.mcp.server import McpError, PhotonicMcpServer
from photonic_workflow.models import ProjectConfig
from photonic_workflow.models.io import write_contract


def _write_one_port_fixture(
    manifest_path: Path,
    *,
    sparameter_path: str,
) -> None:
    payload = {
        "schema_version": "1.0",
        "conventions": {
            "wavelength_unit": "nm",
            "sparameter_normalization": "power-wave",
            "time_dependence": "exp(-iwt)",
        },
        "components": {
            "fixture": {
                "ports": ["p1"],
                "port_modes": {"p1": "TE0"},
                "model_level": "analytic",
                "reference_plane": "fixture",
                "sparameters": sparameter_path,
                "passive": True,
            }
        },
        "instances": {"dut": {"component": "fixture"}},
        "connections": [],
        "external_ports": {"in": "dut:p1"},
    }
    manifest_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_one_port_sparameters(path: Path) -> None:
    path.write_text(
        "wavelength_nm,out_port,in_port,s_real,s_imag\n"
        "1550,p1,p1,0.5,0\n",
        encoding="utf-8",
    )


class McpSecurityTests(unittest.TestCase):
    def test_indirect_circuit_inputs_must_stay_within_mcp_read_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            read_root = root / "readable"
            read_root.mkdir()
            (root / "photonic.toml").write_text(
                "# project-root discovery marker\n",
                encoding="utf-8",
            )
            outside = root / "outside.csv"
            _write_one_port_sparameters(outside)
            manifest = read_root / "assembly.json"
            _write_one_port_fixture(
                manifest,
                sparameter_path="../outside.csv",
            )
            server = PhotonicMcpServer(
                root / "skill",
                read_roots=[read_root],
                write_roots=[read_root],
            )

            with self.assertRaises(SecurityViolationError):
                server.tool_call(
                    "validate_circuit",
                    {
                        "manifest": str(manifest),
                        "structure_only": False,
                    },
                )
            composed = read_root / "composed.csv"
            with self.assertRaises(SecurityViolationError):
                server.tool_call(
                    "compose_circuit",
                    {
                        "manifest": str(manifest),
                        "output": str(composed),
                    },
                )
            self.assertFalse(composed.exists())

            inside = read_root / "inside.csv"
            _write_one_port_sparameters(inside)
            _write_one_port_fixture(
                manifest,
                sparameter_path="inside.csv",
            )
            result = server.tool_call(
                "validate_circuit",
                {
                    "manifest": str(manifest),
                    "structure_only": False,
                },
            )
            self.assertTrue(result["structuredContent"]["valid"])
            composed_result = server.tool_call(
                "compose_circuit",
                {
                    "manifest": str(manifest),
                    "output": str(composed),
                },
            )
            self.assertEqual(
                composed_result["structuredContent"]["output"],
                str(composed.resolve()),
            )
            self.assertTrue(composed.is_file())

    def test_tool_arguments_enforce_published_closed_json_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            read_root = root / "read"
            write_root = root / "write"
            read_root.mkdir()
            write_root.mkdir()
            server = PhotonicMcpServer(
                root / "skill",
                read_roots=[read_root],
                write_roots=[write_root],
            )

            project = write_root / "unexpected-write"
            with self.assertRaisesRegex(McpError, "unexpected argument"):
                server.tool_call(
                    "create_project_scaffold",
                    {
                        "project_root": str(project),
                        "dry_run": True,
                    },
                )
            self.assertFalse(project.exists())

            with self.assertRaisesRegex(McpError, "missing required argument"):
                server.tool_call("audit_project_artifacts", {})

            with self.assertRaisesRegex(McpError, "must have JSON type integer"):
                server.tool_call(
                    "audit_project_artifacts",
                    {
                        "project_root": str(read_root),
                        "large_file_mb": True,
                    },
                )

    def test_validate_contract_returns_only_a_bounded_redacted_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract_path = root / "project-config.json"
            credential_label = "api_" + "key"
            credential_value = "fixture-" + "secret"
            credential_assignment = f"{credential_label}={credential_value}"
            user_prefix = "C:" + "\\" + "Users" + "\\private-user"
            write_contract(
                contract_path,
                ProjectConfig(
                    stable_id="project:mcp-redaction",
                    name="MCP redaction fixture",
                    source="unit test",
                    status=credential_assignment,
                    allowed_roots=[user_prefix + "\\confidential"],
                    matlab_toolbox_path_aliases={
                        "private-toolbox": user_prefix + "\\matlab",
                    },
                    lumerical_api_alias=user_prefix + "\\lumapi",
                    instrument_aliases={
                        "osa": "GPIB0::20::INSTR",
                        "credential": credential_assignment,
                    },
                ),
            )
            server = PhotonicMcpServer(
                root / "skill",
                read_roots=[root],
                write_roots=[],
            )

            result = server.tool_call(
                "validate_contract",
                {
                    "contract_file": str(contract_path),
                    "expected_type": "ProjectConfig",
                },
            )["structuredContent"]

            self.assertEqual(result["projection"], "bounded-redacted")
            self.assertEqual(
                set(result["contract"]),
                {
                    "contract_type",
                    "schema_version",
                    "stable_id",
                    "status",
                    "validity",
                },
            )
            self.assertEqual(
                result["contract"]["status"],
                f"{credential_label}=<redacted>",
            )
            encoded = json.dumps(result)
            for sensitive in (
                user_prefix.replace("\\", "\\\\"),
                "GPIB0",
                credential_value,
                "private-toolbox",
                "lumapi",
            ):
                self.assertNotIn(sensitive, encoded)

    def test_inspect_project_rejects_indirect_gate_reads_outside_read_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            verification = project / "verification"
            verification.mkdir(parents=True)
            (project / "runs").mkdir()
            (project / "photonic.toml").write_text(
                "\n".join(
                    (
                        'schema_version = "1.0"',
                        'stable_id = "project:mcp-indirect-read"',
                        'name = "MCP indirect read fixture"',
                        'source = "unit test"',
                        'profile = "custom-device-first"',
                        "",
                    )
                ),
                encoding="utf-8",
            )
            outside = root / "outside-gates.json"
            outside.write_text("[]\n", encoding="utf-8")
            gate_path = verification / "gates.json"
            try:
                gate_path.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")
            server = PhotonicMcpServer(
                root / "skill",
                read_roots=[project],
                write_roots=[],
            )

            with self.assertRaises(SecurityViolationError):
                server.tool_call(
                    "inspect_project",
                    {"project_root": str(project)},
                )


if __name__ == "__main__":
    unittest.main()
