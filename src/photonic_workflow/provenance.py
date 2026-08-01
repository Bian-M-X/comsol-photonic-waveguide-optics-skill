from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import ArtifactRecord, ProvenanceRecord
from .security import ensure_within_allowed_roots


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(
    path: Path,
    *,
    project_root: Path,
    allowed_roots: Iterable[Path],
    media_type: str = "application/octet-stream",
    immutable: bool = False,
    parent_artifacts: list[str] | None = None,
) -> ArtifactRecord:
    checked = ensure_within_allowed_roots(path, allowed_roots)
    relative = checked.relative_to(project_root.resolve())
    stat = checked.stat()
    stable_id = "artifact:" + sha256_file(checked)[:24]
    return ArtifactRecord(
        stable_id=stable_id,
        name=checked.name,
        source="local artifact inspection",
        status="recorded",
        validity="valid",
        relative_path=relative.as_posix(),
        media_type=media_type,
        byte_count=stat.st_size,
        sha256=sha256_file(checked),
        immutable=immutable,
        parent_artifacts=parent_artifacts or [],
    )


def transformation_record(
    *,
    stable_id: str,
    name: str,
    activity: str,
    tool: str,
    tool_version: str | None,
    inputs: list[str],
    outputs: list[str],
    transformations: list[dict[str, Any]],
    command_shape: list[str] | None = None,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        stable_id=stable_id,
        name=name,
        source="photonic workflow runtime",
        status="recorded",
        validity="valid",
        activity=activity,
        tool=tool,
        tool_version=tool_version,
        input_artifacts=inputs,
        output_artifacts=outputs,
        transformations=transformations,
        command_shape=command_shape or [],
    )
