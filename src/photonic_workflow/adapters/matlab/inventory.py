from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models.contracts import (
    AvailabilityStatus,
    MatlabToolboxRecord,
)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _availability(value: Any, *, default: AvailabilityStatus) -> AvailabilityStatus:
    if value is None:
        return default
    if isinstance(value, bool):
        return AvailabilityStatus.AVAILABLE if value else AvailabilityStatus.UNAVAILABLE
    try:
        return AvailabilityStatus(str(value))
    except ValueError as exc:
        raise InvalidInputError(f"invalid MATLAB availability status: {value!r}") from exc


def _require_bool(value: Any, field_name: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise InvalidInputError(f"{field_name} must be a boolean")
    return value


def _stable_product_id(name: str) -> str:
    fragment = re.sub(r"[^A-Za-z0-9._:-]+", "-", name).strip("-").lower()
    if not fragment or len(fragment) > 96:
        fragment = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
    return f"matlab-product:{fragment}"


def _optional_text(payload: dict[str, Any], field_name: str) -> str | None:
    value = payload.get(field_name)
    if value is None or value == "":
        return None
    if not isinstance(value, (str, int, float)):
        raise InvalidInputError(f"{field_name} must be a scalar string or number")
    return str(value)


def _product_record(payload: Any, *, source: str, community: bool = False) -> MatlabToolboxRecord:
    if not isinstance(payload, dict):
        raise InvalidInputError("each MATLAB product record must be a JSON object")
    name = payload.get("product_name", payload.get("name"))
    if not isinstance(name, str) or not name.strip():
        raise InvalidInputError("MATLAB product_name must be a non-empty string")
    installed = _require_bool(payload.get("installed"), f"{name}.installed", default=True)
    license_verified = _require_bool(
        payload.get("license_verified"),
        f"{name} license_verified",
        default=False,
    )
    path_alias = payload.get("path_alias")
    if path_alias is not None and (not isinstance(path_alias, str) or not path_alias.strip()):
        raise InvalidInputError(f"{name}.path_alias must be a non-empty alias when supplied")
    fingerprint = payload.get("fingerprint")
    if fingerprint is not None and (
        not isinstance(fingerprint, str)
        or not re.fullmatch(r"[A-Fa-f0-9]{64}", fingerprint)
    ):
        raise InvalidInputError(f"{name}.fingerprint must be a SHA-256 hex digest")
    try:
        return MatlabToolboxRecord(
            stable_id=_stable_product_id(name),
            name=name,
            source=source,
            status="installed" if installed else "unavailable",
            product_name=name,
            release=_optional_text(payload, "release"),
            version=_optional_text(payload, "version"),
            installed=installed,
            license_verified=license_verified,
            path_alias=path_alias,
            fingerprint=fingerprint,
            provenance=["community-toolbox" if community else "matlab-product-inventory"],
        )
    except ValidationError as exc:
        raise InvalidInputError(f"invalid MATLAB product record for {name!r}: {exc}") from exc


def _derived_product_status(
    products: tuple[MatlabToolboxRecord, ...],
    product_name: str,
    *,
    complete_inventory: bool,
) -> AvailabilityStatus:
    wanted = product_name.casefold()
    for product in products:
        if product.product_name.casefold() == wanted:
            return (
                AvailabilityStatus.AVAILABLE
                if product.installed
                else AvailabilityStatus.UNAVAILABLE
            )
    return AvailabilityStatus.UNAVAILABLE if complete_inventory else AvailabilityStatus.UNVERIFIED


@dataclass(frozen=True)
class MatlabProductInventory:
    availability: AvailabilityStatus
    release: str | None
    version: str | None
    platform: str | None
    architecture: str | None
    batch_capable: bool
    products: tuple[MatlabToolboxRecord, ...]
    community_toolboxes: tuple[MatlabToolboxRecord, ...]
    comsol_livelink: AvailabilityStatus
    lumerical_api: AvailabilityStatus
    instrument_control: AvailabilityStatus
    simulink: AvailabilityStatus
    root_alias: str | None = None


def parse_product_inventory(payload: Any) -> MatlabProductInventory:
    if not isinstance(payload, dict):
        raise InvalidInputError("MATLAB inventory root must be a JSON object")

    source = payload.get("source", "MATLAB structured capability inventory")
    if not isinstance(source, str) or not source.strip():
        raise InvalidInputError("MATLAB inventory source must be a non-empty string")
    raw_products = payload.get("products", [])
    raw_community = payload.get("community_toolboxes", [])
    if not isinstance(raw_products, list) or not isinstance(raw_community, list):
        raise InvalidInputError("products and community_toolboxes must be arrays")

    products = tuple(_product_record(item, source=source) for item in raw_products)
    community = tuple(
        _product_record(item, source=source, community=True) for item in raw_community
    )
    names = [record.product_name.casefold() for record in (*products, *community)]
    if len(names) != len(set(names)):
        raise InvalidInputError("MATLAB product inventory contains duplicate product names")

    availability = _availability(
        payload.get("availability"),
        default=AvailabilityStatus.UNVERIFIED,
    )
    complete_inventory = _require_bool(
        payload.get("complete_product_inventory"),
        "complete_product_inventory",
        default=availability == AvailabilityStatus.AVAILABLE,
    )
    root_alias = "<matlab-root>" if payload.get("root") or payload.get("root_alias") else None

    return MatlabProductInventory(
        availability=availability,
        release=_optional_text(payload, "release"),
        version=_optional_text(payload, "version"),
        platform=_optional_text(payload, "platform"),
        architecture=_optional_text(payload, "architecture"),
        batch_capable=_require_bool(payload.get("batch_capable"), "batch_capable"),
        products=products,
        community_toolboxes=community,
        comsol_livelink=_availability(
            payload.get("comsol_livelink"),
            default=AvailabilityStatus.UNVERIFIED,
        ),
        lumerical_api=_availability(
            payload.get("lumerical_api"),
            default=AvailabilityStatus.UNVERIFIED,
        ),
        instrument_control=_availability(
            payload.get("instrument_control"),
            default=_derived_product_status(
                products,
                "Instrument Control Toolbox",
                complete_inventory=complete_inventory,
            ),
        ),
        simulink=_availability(
            payload.get("simulink"),
            default=_derived_product_status(
                products,
                "Simulink",
                complete_inventory=complete_inventory,
            ),
        ),
        root_alias=root_alias,
    )


def load_product_inventory(path: Path) -> MatlabProductInventory:
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except FileNotFoundError as exc:
        raise InvalidInputError(f"MATLAB inventory not found: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise InvalidInputError(f"invalid MATLAB inventory JSON in {path}: {exc}") from exc
    return parse_product_inventory(payload)
