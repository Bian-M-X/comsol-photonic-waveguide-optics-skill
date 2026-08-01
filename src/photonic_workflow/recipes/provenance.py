"""Strict, package-owned provenance for behaviorally reimplemented recipes."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from importlib import resources
from pathlib import PurePosixPath
from typing import Any

from photonic_workflow.exceptions import InvalidInputError

from .catalog import recipe_definitions

PROVENANCE_SCHEMA_VERSION = "1.0"
PROVENANCE_RESOURCE = "data/recipes/provenance-v1.json"
_HASH_RE = re.compile(r"[0-9a-f]{64}\Z")
_VERSION_PART = r"(?:0|[1-9][0-9]*)"
_VERSION_RE = re.compile(rf"{_VERSION_PART}\.{_VERSION_PART}\.{_VERSION_PART}\Z")
_PROJECT_ALIASES = {
    "lt-amzi-portable-core-20260718",
    "lt-amzi-sfwm-robust",
}


def _reject_constant(value: str) -> None:
    raise InvalidInputError(f"non-finite JSON number is not allowed: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise InvalidInputError(f"duplicate provenance key: {key!r}")
        payload[key] = value
    return payload


def _exact_keys(payload: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(payload)
    if actual != expected:
        raise InvalidInputError(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _nonblank(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInputError(f"{label} must be a nonblank string")
    return value


def _relative_path(value: Any, label: str) -> str:
    path = _nonblank(value, label)
    parsed = PurePosixPath(path)
    if (
        parsed.is_absolute()
        or "\\" in path
        or ":" in path
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise InvalidInputError(f"{label} must be a normalized relative POSIX path")
    return path


def _sha256(value: Any, label: str) -> str:
    digest = _nonblank(value, label)
    if not _HASH_RE.fullmatch(digest):
        raise InvalidInputError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _claim_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise InvalidInputError(f"{label} must be a non-empty list")
    claims = [_nonblank(item, f"{label} item") for item in value]
    if len(set(claims)) != len(claims):
        raise InvalidInputError(f"{label} contains duplicates")
    return claims


def validate_recipe_provenance(payload: Any) -> dict[str, Any]:
    """Validate provenance without trusting it to select executable code."""

    if not isinstance(payload, dict):
        raise InvalidInputError("recipe provenance root must be an object")
    _exact_keys(payload, {"schema_version", "recipes"}, "provenance root")
    if payload["schema_version"] != PROVENANCE_SCHEMA_VERSION:
        raise InvalidInputError("unsupported recipe provenance schema_version")
    recipes = payload["recipes"]
    if not isinstance(recipes, list) or not recipes:
        raise InvalidInputError("recipe provenance must contain recipes")

    seen: set[tuple[str, str]] = set()
    for index, record in enumerate(recipes):
        label = f"recipe provenance {index}"
        if not isinstance(record, dict):
            raise InvalidInputError(f"{label} must be an object")
        _exact_keys(
            record,
            {
                "recipe_id",
                "recipe_version",
                "origins",
                "distillation",
                "supported_claims",
                "excluded_claims",
            },
            label,
        )
        recipe_id = _nonblank(record["recipe_id"], f"{label} recipe_id")
        version = _nonblank(record["recipe_version"], f"{label} recipe_version")
        if not _VERSION_RE.fullmatch(version):
            raise InvalidInputError(f"{label} recipe_version is not SemVer")
        identity = recipe_id, version
        if identity in seen:
            raise InvalidInputError(f"duplicate recipe provenance: {identity}")
        seen.add(identity)

        origins = record["origins"]
        if not isinstance(origins, list) or not origins:
            raise InvalidInputError(f"{label} origins must be non-empty")
        for origin_index, origin in enumerate(origins):
            origin_label = f"{label} origin {origin_index}"
            if not isinstance(origin, dict):
                raise InvalidInputError(f"{origin_label} must be an object")
            _exact_keys(
                origin,
                {"project_alias", "revision", "source_files", "evidence_files"},
                origin_label,
            )
            project_alias = _nonblank(
                origin["project_alias"],
                f"{origin_label} project_alias",
            )
            if project_alias not in _PROJECT_ALIASES:
                raise InvalidInputError(f"{origin_label} has an unknown project alias")
            revision = _nonblank(origin["revision"], f"{origin_label} revision")
            if "/" in revision or "\\" in revision:
                raise InvalidInputError(
                    f"{origin_label} revision must not contain a filesystem path"
                )
            for collection_name, expected_keys in (
                ("source_files", {"path", "sha256"}),
                ("evidence_files", {"path", "sha256", "kind"}),
            ):
                files = origin[collection_name]
                if not isinstance(files, list):
                    raise InvalidInputError(f"{origin_label} {collection_name} must be a list")
                if collection_name == "source_files" and not files:
                    raise InvalidInputError(f"{origin_label} source_files must be non-empty")
                for file_index, item in enumerate(files):
                    file_label = f"{origin_label} {collection_name} {file_index}"
                    if not isinstance(item, dict):
                        raise InvalidInputError(f"{file_label} must be an object")
                    _exact_keys(item, expected_keys, file_label)
                    _relative_path(item["path"], f"{file_label} path")
                    _sha256(item["sha256"], f"{file_label} sha256")
                    if "kind" in item:
                        _nonblank(item["kind"], f"{file_label} kind")

        distillation = record["distillation"]
        if not isinstance(distillation, dict):
            raise InvalidInputError(f"{label} distillation must be an object")
        _exact_keys(distillation, {"method", "copied_vendor_code"}, f"{label} distillation")
        _nonblank(distillation["method"], f"{label} distillation method")
        if distillation["copied_vendor_code"] is not False:
            raise InvalidInputError(f"{label} must not include copied vendor code")
        _claim_list(record["supported_claims"], f"{label} supported_claims")
        _claim_list(record["excluded_claims"], f"{label} excluded_claims")

    catalog_identities = {
        (item.descriptor.recipe_id, item.descriptor.recipe_version)
        for item in recipe_definitions()
    }
    if seen != catalog_identities:
        raise InvalidInputError(
            "recipe provenance and executable catalog identities differ: "
            f"missing={sorted(catalog_identities - seen)}, "
            f"unknown={sorted(seen - catalog_identities)}"
        )
    return deepcopy(payload)


def load_recipe_provenance() -> dict[str, Any]:
    text = (
        resources.files("photonic_workflow")
        .joinpath(*PROVENANCE_RESOURCE.split("/"))
        .read_text(encoding="utf-8")
    )
    try:
        payload = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except json.JSONDecodeError as exc:
        raise InvalidInputError(f"invalid packaged recipe provenance: {exc}") from exc
    return validate_recipe_provenance(payload)


def provenance_for(recipe_id: str) -> dict[str, Any]:
    payload = load_recipe_provenance()
    for record in payload["recipes"]:
        if record["recipe_id"] == recipe_id:
            return deepcopy(record)
    raise InvalidInputError(f"recipe provenance is missing: {recipe_id}")


__all__ = [
    "PROVENANCE_RESOURCE",
    "PROVENANCE_SCHEMA_VERSION",
    "load_recipe_provenance",
    "provenance_for",
    "validate_recipe_provenance",
]
