from __future__ import annotations

from photonic_workflow.models import TapeoutManifest
from photonic_workflow.security import enforce_tapeout_mutable


def assert_tapeout_editable(manifest: TapeoutManifest) -> None:
    enforce_tapeout_mutable(manifest.frozen)
