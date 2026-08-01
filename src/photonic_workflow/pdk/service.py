from __future__ import annotations

from typing import Any

from photonic_workflow.models import PdkManifest


def validate_pdk_manifest(manifest: PdkManifest) -> dict[str, Any]:
    errors: list[str] = []
    if not manifest.foundry_alias:
        errors.append("foundry/process alias is required")
    if not manifest.pdk_version:
        errors.append("PDK version is required")
    if manifest.access.lower() in {"nda", "proprietary", "restricted"}:
        if manifest.technology_stack_id or manifest.pcells or manifest.compact_models:
            errors.append(
                "restricted PDK manifests may record aliases, version, fingerprint and capabilities only"
            )
        if manifest.local_path_alias and ("/" in manifest.local_path_alias or "\\" in manifest.local_path_alias):
            errors.append("restricted PDK local_path_alias must not expose a filesystem path")
    return {
        "valid": not errors,
        "errors": errors,
        "access": manifest.access,
        "fingerprinted": bool(manifest.fingerprint),
        "claim_boundary": "manifest validation does not run foundry DRC/LVS or grant PDK access",
    }
