"""Reusable contract checks for third-party descriptor providers."""

from __future__ import annotations

import os
from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import ImplementationStatus

from .registry import (
    AdapterRegistration,
    AdapterRegistry,
    _provider_registrations,
    default_adapter_registry,
)

_DESCRIPTOR_ONLY_MODES = {
    "descriptor",
    "capability-probe-contract",
    "probe-contract",
}


def _canonical_registration(
    registration: AdapterRegistration,
) -> dict[str, Any]:
    payload = registration.descriptor.model_dump(mode="json")
    # Construction time is provenance, but it is not provider ABI structure.
    payload.pop("created_at", None)
    return {
        "descriptor": payload,
        "factory": registration.factory is not None,
        "spi_version": registration.spi_version,
    }


def validate_adapter_provider_contract(
    provider: object,
    *,
    provider_name: str,
) -> tuple[AdapterRegistration, ...]:
    """Validate the stable descriptor-only provider SPI 1.0 contract.

    This is a provider test helper, not a sandbox. Python import/call side
    effects may already have occurred when a failure is reported.
    """

    before_cwd = os.getcwd()
    before_environment = dict(os.environ)
    first = _provider_registrations(provider, provider_name=provider_name)
    second = _provider_registrations(provider, provider_name=provider_name)
    if os.getcwd() != before_cwd:
        raise InvalidInputError(
            f"adapter provider {provider_name!r} changed the working directory"
        )
    if dict(os.environ) != before_environment:
        raise InvalidInputError(
            f"adapter provider {provider_name!r} changed the process environment"
        )
    if tuple(map(_canonical_registration, first)) != tuple(
        map(_canonical_registration, second)
    ):
        raise InvalidInputError(
            f"adapter provider {provider_name!r} is not deterministic"
        )

    adapter_ids = [item.descriptor.adapter for item in first]
    if len(adapter_ids) != len(set(adapter_ids)):
        raise InvalidInputError(
            f"adapter provider {provider_name!r} returned duplicate adapter IDs"
        )
    built_in_ids = {
        descriptor.adapter
        for descriptor in default_adapter_registry().descriptors()
    }
    conflicts = sorted(set(adapter_ids) & built_in_ids)
    if conflicts:
        raise InvalidInputError(
            f"adapter provider {provider_name!r} conflicts with built-in IDs: "
            + ", ".join(conflicts)
        )

    for registration in first:
        descriptor = registration.descriptor
        if descriptor.implementation not in {
            ImplementationStatus.PLANNED,
            ImplementationStatus.UNVERIFIED,
        }:
            raise InvalidInputError(
                "descriptor-only third-party adapters must remain planned or "
                "unverified"
            )
        if "descriptor" not in descriptor.execution_modes:
            raise InvalidInputError(
                "descriptor-only third-party adapters must publish descriptor mode"
            )
        unsupported_modes = sorted(
            set(descriptor.execution_modes) - _DESCRIPTOR_ONLY_MODES
        )
        if unsupported_modes:
            raise InvalidInputError(
                "descriptor-only third-party adapter declares unsupported modes: "
                + ", ".join(unsupported_modes)
            )
        if not descriptor.default_dry_run or descriptor.default_concurrency != 1:
            raise InvalidInputError(
                "third-party descriptor defaults must remain dry-run and "
                "single-concurrency"
            )

    isolated_registry = AdapterRegistry()
    isolated_registry.register_many(first)
    return first


__all__ = ["validate_adapter_provider_contract"]
