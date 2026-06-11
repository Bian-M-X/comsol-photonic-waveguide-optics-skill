from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def send(proc: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        stderr = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"server closed unexpectedly; stderr={stderr}")
    response = json.loads(line)
    if "error" in response:
        raise RuntimeError(f"MCP error for {request.get('method')}: {response['error']}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Protocol-level smoke test for mcp_photonic_server.py.")
    parser.add_argument("--server", type=Path, default=Path(__file__).with_name("mcp_photonic_server.py"))
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--table", type=Path, required=True)
    parser.add_argument("--allow-root", action="append", default=[])
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="photonic-mcp-smoke-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        cmd = [
            sys.executable,
            str(args.server),
            "--skill-root",
            str(args.skill_root),
            "--allow-root",
            str(args.skill_root),
            "--allow-root",
            str(args.table.resolve().parent),
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
            init = send(
                proc,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke-test"}},
                },
            )
            resources = send(proc, {"jsonrpc": "2.0", "id": 2, "method": "resources/list"})
            tools = send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
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
                        "arguments": {"table_file": str(args.table), "output_dir": str(temp_dir), "label": "mcp_smoke"},
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
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    summary = parsed["result"]["structuredContent"]["summary"]
    output = {
        "initialize_server": init["result"]["serverInfo"],
        "resource_count": len(resources["result"]["resources"]),
        "tool_names": [tool["name"] for tool in tools["result"]["tools"]],
        "manifest_bytes": len(manifest["result"]["contents"][0]["text"]),
        "parse_summary": summary,
        "scaffold_root_created": bool(scaffold["result"]["structuredContent"]["created_folders"]),
        "audit_finding_count": audit["result"]["structuredContent"]["finding_count"],
    }
    print(json.dumps(output, indent=2))

    expected_t21 = 0.325503969965
    if abs(float(summary["max_T21"]) - expected_t21) > 1e-9:
        raise SystemExit(f"unexpected max_T21: {summary['max_T21']}")
    if "parse_sweep_table" not in output["tool_names"]:
        raise SystemExit("parse_sweep_table tool missing")
    if output["audit_finding_count"] != 0:
        raise SystemExit("fresh scaffold should have no artifact audit findings")


if __name__ == "__main__":
    main()
