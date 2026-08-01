from __future__ import annotations

import shutil
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any

from ._version import compatible_minor_requirement
from .config import make_project_config, project_config_toml
from .exceptions import InvalidInputError
from .models import WorkflowProfile
from .models.io import atomic_write_text
from .security import validate_safe_label

PROJECT_FOLDERS = (
    "requirements",
    "pdk",
    "components/contracts",
    "components/sparameters",
    "circuits",
    "layout",
    "models/cards",
    "models/java",
    "models/mph",
    "optimization",
    "multiphysics",
    "packaging",
    "testplans",
    "measurement/raw",
    "measurement/processed",
    "runs",
    "scripts",
    "data/raw",
    "data/processed",
    "verification",
    "reports",
    "handoff",
)


def scaffold_plan(
    root: Path,
    *,
    profile: WorkflowProfile,
    device_family: str,
    project_name: str | None = None,
) -> dict[str, Any]:
    normalized_family = device_family.strip().lower()
    template_kind = (
        "mzi-4port"
        if normalized_family in {"mzi", "balanced-mzi", "interferometer"}
        else "waveguide-cascade"
    )
    config = make_project_config(root, profile=profile, name=project_name)
    template_files = (
        [
            "circuits/assembly.json",
            "components/sparameters/directional_coupler.csv",
            "components/sparameters/arm.csv",
        ]
        if template_kind == "mzi-4port"
        else ["circuits/assembly.json", "components/sparameters/waveguide.csv"]
    )
    return {
        "project_root": str(root.resolve()),
        "profile": profile.value,
        "device_family": device_family,
        "template_kind": template_kind,
        "directories": list(PROJECT_FOLDERS),
        "files": [
            "photonic.toml",
            "PROJECT.md",
            "handoff/latest.md",
            "requirements.txt",
            ".gitignore",
            *template_files,
        ],
        "config_preview": project_config_toml(config),
    }


def _copy_template(relative_source: str, destination: Path) -> None:
    resource = files("photonic_workflow").joinpath("data", "templates", *relative_source.split("/"))
    with as_file(resource) as source:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def create_project_scaffold(
    root: Path,
    *,
    profile: WorkflowProfile = WorkflowProfile.CUSTOM_DEVICE_FIRST,
    device_family: str = "waveguide",
    project_name: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    validate_safe_label(root.name)
    plan = scaffold_plan(root, profile=profile, device_family=device_family, project_name=project_name)
    if dry_run:
        return {**plan, "dry_run": True, "written": []}
    if (root / "photonic.toml").exists():
        raise InvalidInputError(f"project already initialized: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for folder in PROJECT_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)

    atomic_write_text(root / "photonic.toml", plan["config_preview"])
    atomic_write_text(
        root / "PROJECT.md",
        "\n".join(
            [
                "# Photonic Design-Closure Project",
                "",
                f"Profile: `{profile.value}`",
                f"Device family: `{device_family}`",
                "",
                "## Design intent",
                "",
                "## Physical inputs",
                "",
                "## Acceptance criteria",
                "",
                "## Current evidence boundary",
                "",
            ]
        ),
    )
    atomic_write_text(
        root / "handoff" / "latest.md",
        "# Latest Handoff\n\nStatus: initialized\n\nNext safe action: freeze the G0 device contract.\n",
    )
    atomic_write_text(
        root / "requirements.txt",
        compatible_minor_requirement() + "\n",
    )
    atomic_write_text(
        root / ".gitignore",
        "\n".join(
            [
                "*.mph",
                "*.class",
                "*.log",
                "*.mphbin",
                "*.mphstatus",
                "models/mph/",
                "runs/**/runtime/",
                "data/raw/",
                "measurement/raw/",
                "__pycache__/",
                "*.pyc",
                "",
            ]
        ),
    )

    if plan["template_kind"] == "mzi-4port":
        _copy_template("mzi-4port/assembly.json", root / "circuits" / "assembly.json")
        _copy_template(
            "mzi-4port/directional_coupler.csv",
            root / "components" / "sparameters" / "directional_coupler.csv",
        )
        _copy_template("mzi-4port/arm.csv", root / "components" / "sparameters" / "arm.csv")
    else:
        _copy_template("waveguide/assembly.json", root / "circuits" / "assembly.json")
        _copy_template("waveguide/waveguide.csv", root / "components" / "sparameters" / "waveguide.csv")
    return {**plan, "dry_run": False, "written": plan["files"]}
