from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-strict JSON constant in server response: {value}")


def roundtrip(proc: subprocess.Popen[str], request: Any) -> tuple[dict[str, Any], str]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(request, allow_nan=False) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"server closed unexpectedly; stderr={stderr}")
    response = json.loads(line, parse_constant=reject_json_constant)
    return response, line


def send(proc: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    response, _ = roundtrip(proc, request)
    if "error" in response:
        raise RuntimeError(f"MCP error for {request.get('method')}: {response['error']}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Protocol-level smoke test for mcp_photonic_server.py.")
    parser.add_argument("--server", type=Path, default=Path(__file__).with_name("mcp_photonic_server.py"))
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--table",
        type=Path,
        help=(
            "optional COMSOL-style table; a deterministic fixture is generated "
            "by default"
        ),
    )
    parser.add_argument("--expected-t21", type=float, default=0.325503969965)
    parser.add_argument("--allow-root", action="append", default=[])
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="photonic-mcp-smoke-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        table = args.table.resolve() if args.table else temp_dir / "sweep_fixture.txt"
        if not args.table:
            table.write_text(
                "% freq_GHz lambda_um S11 T21 T21_dB\n"
                "195.0 1.537 0.20 0.10 -10.0\n"
                "193.4 1.550 0.25 0.325503969965 -4.87\n"
                "191.8 1.563 0.22 0.12 -9.21\n",
                encoding="utf-8",
            )
        zero_table = temp_dir / "zero_fixture.txt"
        zero_table.write_text(
            "% freq_GHz lambda_um S11 T21\n"
            "195.0 1.540 0.0 0.0\n"
            "193.0 1.550 0.0 0.0\n"
            "191.0 1.560 0.0 0.0\n",
            encoding="utf-8",
        )
        descending_flat_table = temp_dir / "descending_flat_fixture.txt"
        descending_flat_table.write_text(
            "% descending wavelength with a two-sample flat-top peak\n"
            "190.0 1.560 0.02 0.10\n"
            "191.0 1.555 0.02 0.80\n"
            "192.0 1.550 0.02 0.80\n"
            "193.0 1.545 0.02 0.10\n"
            "194.0 1.540 0.02 0.60\n"
            "195.0 1.535 0.02 0.10\n",
            encoding="utf-8",
        )
        cmd = [
            sys.executable,
            str(args.server),
            "--skill-root",
            str(args.skill_root),
            "--allow-root",
            str(args.skill_root),
            "--allow-root",
            str(table.parent),
            "--allow-root",
            str(temp_dir),
        ]
        for root in args.allow_root:
            cmd.extend(["--allow-root", root])

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            invalid_array, _ = roundtrip(proc, [])
            init = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "smoke-test"},
                    },
                },
            )
            resources = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
            tools = send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
            source_sweep_reference = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 30,
                    "method": "resources/read",
                    "params": {
                        "uri": "photonic://skill/reference/frequency-domain-source-sweeps"
                    },
                },
            )
            modeling_recipe_reference = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 31,
                    "method": "resources/read",
                    "params": {
                        "uri": "photonic://skill/reference/modeling-recipes"
                    },
                },
            )
            manifest = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "resources/read",
                    "params": {"uri": "photonic://server/manifest"},
                },
            )
            parsed = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "parse_sweep_table",
                        "arguments": {"table_file": str(table), "output_dir": str(temp_dir), "label": "mcp_smoke"},
                    },
                },
            )
            unsafe_label_responses = []
            for index, unsafe_label in enumerate(
                ["../escape", "..\\escape", str(temp_dir / "absolute"), "", ".", "CON.report"], start=20
            ):
                response, _ = roundtrip(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": index,
                        "method": "tools/call",
                        "params": {
                            "name": "parse_sweep_table",
                            "arguments": {
                                "table_file": str(table),
                                "output_dir": str(temp_dir / "unsafe-output"),
                                "label": unsafe_label,
                            },
                        },
                    },
                )
                unsafe_label_responses.append(response)
            zero_parsed = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 30,
                    "method": "tools/call",
                    "params": {
                        "name": "parse_sweep_table",
                        "arguments": {
                            "table_file": str(zero_table),
                            "output_dir": str(temp_dir / "zero-output"),
                            "label": "zero_spectrum",
                        },
                    },
                },
            )
            descending_flat_parsed = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 31,
                    "method": "tools/call",
                    "params": {
                        "name": "parse_sweep_table",
                        "arguments": {
                            "table_file": str(descending_flat_table),
                            "output_dir": str(temp_dir / "descending-output"),
                            "label": "descending_flat",
                        },
                    },
                },
            )
            scaffold_dir = temp_dir / "project-scaffold"
            scaffold = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "create_project_scaffold",
                        "arguments": {"project_root": str(scaffold_dir), "device_family": "mzi"},
                    },
                },
            )
            audit = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {"name": "audit_project_artifacts", "arguments": {"project_root": str(scaffold_dir)}},
                },
            )
            credential_name = ".env"
            credential_file = scaffold_dir / credential_name
            credential_file.write_text("TO" + "KEN=fixture-value\n", encoding="utf-8")
            binary_file = scaffold_dir / "binaryblob"
            binary_file.write_bytes(bytes([0, 84, 79, 75, 69, 78, 61, 120]))
            credential_audit = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 32,
                    "method": "tools/call",
                    "params": {
                        "name": "audit_project_artifacts",
                        "arguments": {"project_root": str(scaffold_dir)},
                    },
                },
            )
            tail_secret_file = scaffold_dir / "tail-secret.txt"
            tail_secret_file.write_text(
                ("safe-prefix\n" * 100000) + ("API_" + "KEY=tail-fixture-value\n"),
                encoding="utf-8",
            )
            tail_secret_audit = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 33,
                    "method": "tools/call",
                    "params": {
                        "name": "audit_project_artifacts",
                        "arguments": {"project_root": str(scaffold_dir)},
                    },
                },
            )
            java_file = temp_dir / "SmokeModel.java"
            java_file.write_text(
                "\n".join(
                    [
                        "public class SmokeModel {",
                        "  public static void main(String[] args) {",
                        "    System.out.println(\"MCP dry-run placeholder\");",
                        "  }",
                        "}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            batch_plan = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {
                        "name": "run_java_batch",
                        "arguments": {
                            "java_file": str(java_file),
                            "output_mph": str(temp_dir / "SmokeModel.mph"),
                            "batch_log": str(temp_dir / "SmokeModel.log"),
                            "runtime_dir": str(temp_dir / "runtime"),
                            "solver_root": "PHOTONIC_SOLVER_ROOT_PLACEHOLDER",
                            "timeout_s": 60,
                            "dry_run": True,
                        },
                    },
                },
            )
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    summary = parsed["result"]["structuredContent"]["summary"]
    zero_summary = zero_parsed["result"]["structuredContent"]["summary"]
    descending_flat_summary = descending_flat_parsed["result"]["structuredContent"]["summary"]
    batch_structured = batch_plan["result"]["structuredContent"]
    credential_findings = credential_audit["result"]["structuredContent"]["findings"]
    tail_secret_findings = tail_secret_audit["result"]["structuredContent"]["findings"]
    source_sweep_text = source_sweep_reference["result"]["contents"][0]["text"]
    if "source_solution_index == column" not in source_sweep_text:
        raise RuntimeError("source-sweep reference was not exposed through MCP")
    modeling_recipe_text = modeling_recipe_reference["result"]["contents"][0]["text"]
    if "geometry.symmetric-euler-bend" not in modeling_recipe_text:
        raise RuntimeError("modeling-recipe reference was not exposed through MCP")
    manifest_payload = json.loads(
        manifest["result"]["contents"][0]["text"],
        parse_constant=reject_json_constant,
    )
    output = {
        "initialize_server": init["result"]["serverInfo"],
        "resource_count": len(resources["result"]["resources"]),
        "manifest_resource_count": len(manifest_payload["resources"]),
        "source_sweep_reference_verified": True,
        "modeling_recipe_reference_verified": True,
        "tool_names": [tool["name"] for tool in tools["result"]["tools"]],
        "manifest_bytes": len(manifest["result"]["contents"][0]["text"]),
        "parse_summary": summary,
        "regressions": {
            "array_request_error": invalid_array.get("error"),
            "unsafe_label_error_codes": [item.get("error", {}).get("code") for item in unsafe_label_responses],
            "zero_spectrum_weak_strong_ratio": zero_summary["weak_strong_ratio"],
            "descending_flat_peak_lambdas_nm": descending_flat_summary["peak_lambdas_nm"],
            "descending_flat_peak_spacings_nm": descending_flat_summary["peak_spacings_nm"],
            "credential_audit_kinds": [item["kind"] for item in credential_findings],
            "tail_secret_paths": [item["path"] for item in tail_secret_findings],
        },
        "scaffold_root_created": bool(scaffold["result"]["structuredContent"]["created_folders"]),
        "scaffold_requirements_created": "requirements.txt"
        in scaffold["result"]["structuredContent"].get("created_files", []),
        "scaffold_template_kind": scaffold["result"]["structuredContent"].get("template_kind"),
        "audit_finding_count": audit["result"]["structuredContent"]["finding_count"],
        "batch_dry_run": {
            "dry_run": batch_structured["dry_run"],
            "will_execute": batch_structured["will_execute"],
            "timeout_s": batch_structured["timeout_s"],
            "solver_root_source": batch_structured["solver_root_source"],
            "solver_root_redacted_as": batch_structured["solver_root_redacted_as"],
            "raw_solver_root_returned": "PHOTONIC_SOLVER_ROOT_PLACEHOLDER" in json.dumps(batch_structured),
        },
    }
    print(json.dumps(output, indent=2))

    expected_t21 = args.expected_t21
    if abs(float(summary["max_T21"]) - expected_t21) > 1e-9:
        raise SystemExit(f"unexpected max_T21: {summary['max_T21']}")
    if invalid_array.get("error", {}).get("code") != -32600 or invalid_array.get("id") is not None:
        raise SystemExit(f"array request should return JSON-RPC invalid request: {invalid_array}")
    if any(item.get("error", {}).get("code") != -32602 for item in unsafe_label_responses):
        raise SystemExit(f"unsafe labels were not uniformly rejected: {unsafe_label_responses}")
    if zero_summary["peak_lambdas_nm"] or zero_summary["weak_strong_ratio"] is not None:
        raise SystemExit(f"zero/no-peak spectrum must use an empty peak list and null ratio: {zero_summary}")
    peak_lambdas = descending_flat_summary["peak_lambdas_nm"]
    peak_spacings = descending_flat_summary["peak_spacings_nm"]
    if peak_lambdas != [1540.0, 1552.5]:
        raise SystemExit(f"descending flat-top peaks were not consolidated/sorted: {peak_lambdas}")
    if peak_spacings != [12.5] or any(spacing <= 0 for spacing in peak_spacings):
        raise SystemExit(f"descending spectrum produced invalid peak spacing: {peak_spacings}")
    credential_kinds = {item["kind"] for item in credential_findings}
    if (
        "sensitive_file_name" not in credential_kinds
        or "possible_sensitive_content:credential_token" not in credential_kinds
    ):
        raise SystemExit(f"MCP artifact audit missed hidden credential evidence: {credential_findings}")
    if any(item["path"] == "binaryblob" for item in credential_findings):
        raise SystemExit(f"MCP artifact audit treated a NUL-containing binary as text: {credential_findings}")
    if not any(item["path"] == "tail-secret.txt" for item in tail_secret_findings):
        raise SystemExit(f"MCP artifact audit missed sensitive content after the first MiB: {tail_secret_findings}")
    if "parse_sweep_table" not in output["tool_names"]:
        raise SystemExit("parse_sweep_table tool missing")
    if "run_java_batch" not in output["tool_names"]:
        raise SystemExit("run_java_batch tool missing")
    if not output["scaffold_requirements_created"]:
        raise SystemExit("project scaffold did not include requirements.txt")
    if output["scaffold_template_kind"] != "mzi-4port":
        raise SystemExit(f"MZI project did not select the four-port template: {output['scaffold_template_kind']}")
    if output["audit_finding_count"] != 0:
        raise SystemExit("fresh scaffold should have no artifact audit findings")
    if output["batch_dry_run"] != {
        "dry_run": True,
        "will_execute": False,
        "timeout_s": 60,
        "solver_root_source": "argument",
        "solver_root_redacted_as": "<PHOTONIC_SOLVER_ROOT>",
        "raw_solver_root_returned": False,
    }:
        raise SystemExit(f"unexpected batch dry-run payload: {output['batch_dry_run']}")


if __name__ == "__main__":
    main()
