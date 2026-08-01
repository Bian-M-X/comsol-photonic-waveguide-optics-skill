"""Smoke-test an installed wheel without relying on a repository checkout."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import tempfile
from pathlib import Path

import photonic_workflow
from photonic_workflow import __version__
from photonic_workflow.circuits import validate_manifest
from photonic_workflow.mcp.server import (
    AGENT_RESOURCES,
    REFERENCE_RESOURCES,
    PhotonicMcpServer,
    default_skill_root,
)
from photonic_workflow.project import create_project_scaffold


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--forbid-root",
        type=Path,
        help="Repository root that packaged resources must not resolve through.",
    )
    args = parser.parse_args()

    distribution_version = importlib.metadata.version("photonic-workflow")
    if distribution_version != __version__:
        raise RuntimeError(
            f"distribution {distribution_version} != runtime {__version__}"
        )

    skill_root = default_skill_root().resolve()
    if args.forbid_root is not None:
        repository_root = args.forbid_root.resolve()
        source_root = repository_root / "src"
        package_module = Path(photonic_workflow.__file__).resolve()
        if (
            skill_root == repository_root
            or source_root == package_module
            or source_root in package_module.parents
        ):
            raise RuntimeError(
                "installed package or MCP resources resolved through source checkout: "
                f"{package_module}; {skill_root}"
            )

    server = PhotonicMcpServer(skill_root, read_roots=[], write_roots=[])
    resources = server.resource_list()
    tools = server.tool_list()
    expected_resource_uris = {
        "photonic://server/manifest",
        *(f"photonic://skill/reference/{name}" for name in REFERENCE_RESOURCES),
        *(f"photonic://skill/agent/{name}" for name in AGENT_RESOURCES),
    }
    actual_resource_uris = {resource["uri"] for resource in resources}
    if actual_resource_uris != expected_resource_uris or len(tools) != 10:
        raise RuntimeError(
            "unexpected MCP surface: "
            f"{len(resources)} resources, {len(tools)} tools; "
            f"missing={sorted(expected_resource_uris - actual_resource_uris)}, "
            f"extra={sorted(actual_resource_uris - expected_resource_uris)}"
        )
    for resource in resources:
        contents = server.resource_read(resource["uri"])
        if len(contents) != 1 or not contents[0]["text"]:
            raise RuntimeError(f"empty installed MCP resource: {resource['uri']}")

    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as temporary:
        outside = Path(temporary)
        os.chdir(outside)
        try:
            project = outside / "installed-wheel-project"
            create_project_scaffold(project, device_family="mzi")
            manifest, data = validate_manifest(project / "circuits" / "assembly.json")
            if len(manifest["instances"]) != 4 or len(data) != 2:
                raise RuntimeError("installed MZI template did not validate")
        finally:
            os.chdir(original_cwd)

    print(
        json.dumps(
            {
                "version": __version__,
                "mcp_resource_count": len(resources),
                "mcp_tool_count": len(tools),
                "packaged_skill_root": skill_root.name,
                "template_smoke": "passed",
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
