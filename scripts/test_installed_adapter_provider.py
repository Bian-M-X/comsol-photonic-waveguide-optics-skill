"""Verify real installed entry-point discovery without provider execution."""

from __future__ import annotations

import json
from importlib.metadata import entry_points

from photonic_workflow.adapters import (
    default_adapter_registry,
    validate_adapter_provider_contract,
)
from photonic_workflow.compatibility import ADAPTER_ENTRY_POINT_GROUP


def main() -> int:
    matching = [
        entry_point
        for entry_point in entry_points(group=ADAPTER_ENTRY_POINT_GROUP)
        if entry_point.name == "reviewed-example"
    ]
    if len(matching) != 1:
        raise RuntimeError(
            f"expected one installed reviewed-example entry point, found {len(matching)}"
        )
    registrations = validate_adapter_provider_contract(
        matching[0].load(),
        provider_name=matching[0].name,
    )
    registry = default_adapter_registry()
    loaded = registry.load_entrypoint_adapters(["reviewed-example"])
    if loaded != ("reviewed-example",):
        raise RuntimeError(f"unexpected loaded provider names: {loaded!r}")
    if registry.has_factory("reviewed-example"):
        raise RuntimeError("descriptor-only provider exposed a runtime factory")
    print(
        json.dumps(
            {
                "provider": registry.loaded_providers()[0].as_dict(),
                "adapters": [
                    registration.descriptor.adapter
                    for registration in registrations
                ],
                "factory": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
