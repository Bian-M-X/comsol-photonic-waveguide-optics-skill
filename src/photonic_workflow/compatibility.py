"""Named compatibility boundaries for persisted and public data surfaces."""

from __future__ import annotations

DEFAULT_CONTRACT_SCHEMA_VERSION = "1.0"
# Backward-compatible name. Contract types may advance independently; this is
# a construction default, not a claim that every model must share one version.
CURRENT_CONTRACT_SCHEMA_VERSION = DEFAULT_CONTRACT_SCHEMA_VERSION
CURRENT_API_ENVELOPE_SCHEMA_VERSION = "1.0"
CURRENT_RUN_EVENT_SCHEMA_VERSION = "1.0"
CURRENT_RUN_CHECKPOINT_SCHEMA_VERSION = "1.0"
CURRENT_ADAPTER_SPI_VERSION = "1.0"

ADAPTER_ENTRY_POINT_GROUP = "photonic_workflow.adapters"

__all__ = [
    "ADAPTER_ENTRY_POINT_GROUP",
    "CURRENT_ADAPTER_SPI_VERSION",
    "CURRENT_API_ENVELOPE_SCHEMA_VERSION",
    "CURRENT_CONTRACT_SCHEMA_VERSION",
    "CURRENT_RUN_CHECKPOINT_SCHEMA_VERSION",
    "CURRENT_RUN_EVENT_SCHEMA_VERSION",
    "DEFAULT_CONTRACT_SCHEMA_VERSION",
]
