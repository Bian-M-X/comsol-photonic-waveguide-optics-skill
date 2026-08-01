"""Validate wheel runtime resources and sdist maintenance sources."""

from __future__ import annotations

import argparse
import json
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

WHEEL_REQUIRED_SUFFIXES = (
    "photonic_workflow/adapters/testing.py",
    "photonic_workflow/models/migration_catalog.py",
    "photonic_workflow/data/templates/mzi-4port/assembly.json",
    "photonic_workflow/data/matlab/tests/TestPhotonicRuntime.m",
    "photonic_workflow/data/recipes/provenance-v1.json",
)

SDIST_REQUIRED_RELATIVE_PATHS = (
    "SKILL.md",
    "CHANGELOG.md",
    "photonic.toml.example",
    "docs/maintenance.md",
    "docs/providers/authoring-third-party-adapter.md",
    "examples/minimal-adapter-provider/pyproject.toml",
    "examples/minimal-adapter-provider/src/photonic_example_adapter/__init__.py",
    "examples/recipes/circular-route.json",
    "matlab/tests/TestPhotonicRuntime.m",
    "scripts/sync-packaged-matlab-resources.ps1",
    "scripts/test_installed_adapter_provider.py",
    "tests/fixtures/contract_surface_v1.json",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path)
    args = parser.parse_args()
    wheels = sorted(args.dist_dir.glob("*.whl"))
    sdists = sorted(args.dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(
            f"expected one wheel and one sdist, found {len(wheels)} and {len(sdists)}"
        )

    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_names = set(archive.namelist())
    for suffix in WHEEL_REQUIRED_SUFFIXES:
        if not any(name.endswith(suffix) for name in wheel_names):
            raise RuntimeError(f"wheel is missing {suffix}")
    reference_count = sum(
        "/data/skill/references/" in name for name in wheel_names
    )
    agent_count = sum("/data/skill/agents/" in name for name in wheel_names)
    matlab_count = sum("/data/matlab/" in name for name in wheel_names)
    expected_counts = (
        len(tuple((REPOSITORY_ROOT / "references").glob("*.md"))),
        len(tuple((REPOSITORY_ROOT / "agents").glob("*-agent.md"))),
        len(tuple((REPOSITORY_ROOT / "matlab").rglob("*.m"))),
    )
    if (reference_count, agent_count, matlab_count) != expected_counts:
        raise RuntimeError(
            "wheel resource counts are "
            f"{reference_count}/{agent_count}/{matlab_count}, expected "
            f"{expected_counts[0]}/{expected_counts[1]}/{expected_counts[2]} "
            "from repository sources"
        )

    with tarfile.open(sdists[0], mode="r:gz") as archive:
        sdist_names = {
            PurePosixPath(name).parts[1:]
            for name in archive.getnames()
            if len(PurePosixPath(name).parts) > 1
        }
    forbidden_sdist_prefixes = (
        PurePosixPath("examples/minimal-adapter-provider/build").parts,
        PurePosixPath(
            "examples/minimal-adapter-provider/src/"
            "photonic_example_adapter.egg-info"
        ).parts,
    )
    for name in sdist_names:
        for prefix in forbidden_sdist_prefixes:
            if name[: len(prefix)] == prefix:
                raise RuntimeError(
                    "sdist contains generated example build metadata: "
                    + PurePosixPath(*name).as_posix()
                )
    for relative in SDIST_REQUIRED_RELATIVE_PATHS:
        parts = PurePosixPath(relative).parts
        if parts not in sdist_names:
            raise RuntimeError(f"sdist is missing {relative}")

    print(
        json.dumps(
            {
                "wheel": wheels[0].name,
                "wheel_file_count": len(wheel_names),
                "skill_references": reference_count,
                "skill_agents": agent_count,
                "matlab_files": matlab_count,
                "sdist": sdists[0].name,
                "sdist_file_count": len(sdist_names),
                "maintenance_sources": "present",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
