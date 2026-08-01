#!/usr/bin/env python3
"""Validate the public skill and Codex UI metadata contracts."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "SKILL.md"
OPENAI_PATH = ROOT / "agents" / "openai.yaml"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_SKILL_KEYS = {"name", "description", "license", "allowed-tools", "metadata"}
ALLOWED_OPENAI_KEYS = {"interface", "dependencies", "policy"}
ALLOWED_INTERFACE_KEYS = {
    "brand_color",
    "default_prompt",
    "display_name",
    "icon_large",
    "icon_small",
    "short_description",
}
ALLOWED_DEPENDENCY_KEYS = {"tools"}
ALLOWED_TOOL_KEYS = {"description", "transport", "type", "url", "value"}
ALLOWED_POLICY_KEYS = {"allow_implicit_invocation"}


class MetadataError(ValueError):
    """Raised when checked-in skill metadata violates its public schema."""


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: UniqueKeyLoader, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key, value in loader.construct_pairs(node, deep=deep):
        try:
            duplicate = key in result
        except TypeError as exc:
            raise MetadataError("YAML mapping keys must be hashable") from exc
        if duplicate:
            raise MetadataError(f"duplicate YAML mapping key: {key!r}")
        result[key] = value
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _load_yaml(content: str) -> Any:
    return yaml.load(content, Loader=UniqueKeyLoader)


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MetadataError(f"{label} must be a string-keyed YAML mapping")
    return value


def _require_nonempty_string(value: Any, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MetadataError(f"{label} must be a non-empty string")
    cleaned = value.strip()
    if len(cleaned) > maximum:
        raise MetadataError(f"{label} exceeds {maximum} characters")
    if "\n" in cleaned or "\r" in cleaned:
        raise MetadataError(f"{label} must be one line")
    return cleaned


def validate_skill(path: Path = SKILL_PATH) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.DOTALL)
    if match is None:
        raise MetadataError("SKILL.md must begin with delimited YAML frontmatter")
    data = _require_mapping(_load_yaml(match.group(1)), "SKILL.md frontmatter")
    unexpected = sorted(set(data) - ALLOWED_SKILL_KEYS)
    if unexpected:
        raise MetadataError(f"SKILL.md contains unsupported frontmatter keys: {unexpected}")

    name = _require_nonempty_string(data.get("name"), "SKILL.md name", maximum=64)
    if SKILL_NAME_PATTERN.fullmatch(name) is None:
        raise MetadataError("SKILL.md name must use lower-case hyphen-case")
    description = _require_nonempty_string(data.get("description"), "SKILL.md description", maximum=1024)
    if "<" in description or ">" in description:
        raise MetadataError("SKILL.md description cannot contain angle brackets")
    return name


def _require_yaml_string_style(node: Node, *, path: str = "") -> None:
    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode) or key_node.tag != "tag:yaml.org,2002:str":
                raise MetadataError(f"{path or 'openai.yaml'} contains a non-string mapping key")
            if key_node.style is not None:
                raise MetadataError(f"{path or 'openai.yaml'} keys must remain unquoted")
            child_path = f"{path}.{key_node.value}" if path else key_node.value
            _require_yaml_string_style(value_node, path=child_path)
        return
    if isinstance(node, SequenceNode):
        for index, child in enumerate(node.value):
            _require_yaml_string_style(child, path=f"{path}[{index}]")
        return
    if isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:str" and node.style != '"':
        raise MetadataError(f"{path} string values must use double quotes")


def validate_openai_yaml(skill_name: str, path: Path = OPENAI_PATH) -> None:
    content = path.read_text(encoding="utf-8")
    node = yaml.compose(content)
    if node is None:
        raise MetadataError("agents/openai.yaml cannot be empty")
    _require_yaml_string_style(node)

    data = _require_mapping(_load_yaml(content), "agents/openai.yaml")
    unexpected = sorted(set(data) - ALLOWED_OPENAI_KEYS)
    if unexpected:
        raise MetadataError(f"agents/openai.yaml contains unsupported top-level keys: {unexpected}")
    interface = _require_mapping(data.get("interface"), "agents/openai.yaml interface")
    unexpected_interface = sorted(set(interface) - ALLOWED_INTERFACE_KEYS)
    if unexpected_interface:
        raise MetadataError(f"agents/openai.yaml contains unsupported interface keys: {unexpected_interface}")

    _require_nonempty_string(interface.get("display_name"), "interface.display_name", maximum=64)
    short_description = _require_nonempty_string(
        interface.get("short_description"),
        "interface.short_description",
        maximum=64,
    )
    if len(short_description) < 25:
        raise MetadataError("interface.short_description must contain at least 25 characters")
    default_prompt = _require_nonempty_string(
        interface.get("default_prompt"),
        "interface.default_prompt",
        maximum=512,
    )
    if f"${skill_name}" not in default_prompt:
        raise MetadataError(f"interface.default_prompt must mention ${skill_name}")

    for icon_key in ("icon_small", "icon_large"):
        icon = interface.get(icon_key)
        if icon is not None:
            relative = _require_nonempty_string(icon, f"interface.{icon_key}", maximum=256)
            if not relative.startswith("./assets/") or not (ROOT / relative).is_file():
                raise MetadataError(f"interface.{icon_key} must name an existing ./assets/ file")

    brand_color = interface.get("brand_color")
    if brand_color is not None:
        color = _require_nonempty_string(brand_color, "interface.brand_color", maximum=7)
        if re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None:
            raise MetadataError("interface.brand_color must use #RRGGBB")

    dependencies = data.get("dependencies")
    if dependencies is not None:
        dependency_map = _require_mapping(dependencies, "dependencies")
        unexpected_dependencies = sorted(set(dependency_map) - ALLOWED_DEPENDENCY_KEYS)
        if unexpected_dependencies:
            raise MetadataError(f"dependencies contains unsupported keys: {unexpected_dependencies}")
        tools = dependency_map.get("tools")
        if not isinstance(tools, list) or not tools:
            raise MetadataError("dependencies.tools must be a non-empty list")
        for index, tool in enumerate(tools):
            tool_map = _require_mapping(tool, f"dependencies.tools[{index}]")
            unexpected_tool_keys = sorted(set(tool_map) - ALLOWED_TOOL_KEYS)
            if unexpected_tool_keys:
                raise MetadataError(f"dependencies.tools[{index}] contains unsupported keys: {unexpected_tool_keys}")
            tool_type = _require_nonempty_string(tool_map.get("type"), f"dependencies.tools[{index}].type", maximum=32)
            if tool_type != "mcp":
                raise MetadataError(f"dependencies.tools[{index}].type must be mcp")
            for key in ("value", "description", "transport", "url"):
                _require_nonempty_string(tool_map.get(key), f"dependencies.tools[{index}].{key}", maximum=512)

    policy = data.get("policy")
    if policy is not None:
        policy_map = _require_mapping(policy, "policy")
        unexpected_policy = sorted(set(policy_map) - ALLOWED_POLICY_KEYS)
        if unexpected_policy:
            raise MetadataError(f"policy contains unsupported keys: {unexpected_policy}")
        if not isinstance(policy_map.get("allow_implicit_invocation"), bool):
            raise MetadataError("policy.allow_implicit_invocation must be a boolean")


def main() -> int:
    try:
        skill_name = validate_skill()
        validate_openai_yaml(skill_name)
    except (MetadataError, OSError, UnicodeError, yaml.YAMLError) as exc:
        print(f"Skill metadata validation failed: {exc}", file=sys.stderr)
        return 1
    print("Skill and UI metadata schemas verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
