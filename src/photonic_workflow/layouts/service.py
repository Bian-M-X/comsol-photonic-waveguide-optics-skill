from __future__ import annotations

from typing import Any

from photonic_workflow.models import LayoutManifest
from photonic_workflow.models.io import revalidate_internal


def compare_layout_manifests(left: LayoutManifest, right: LayoutManifest) -> dict[str, Any]:
    fields = {
        "top_cell": (left.top_cell, right.top_cell),
        "layer_map": (left.layer_map, right.layer_map),
        "bounding_box_um": (left.bounding_box_um, right.bounding_box_um),
        "cell_hierarchy": (left.cell_hierarchy, right.cell_hierarchy),
        "polygon_count": (left.polygon_count, right.polygon_count),
        "extracted_netlist_id": (left.extracted_netlist_id, right.extracted_netlist_id),
    }
    differences = {
        name: {"left": values[0], "right": values[1]}
        for name, values in fields.items()
        if values[0] != values[1]
    }
    return {
        "equivalent_at_manifest_level": not differences,
        "differences": differences,
        "claim_boundary": (
            "manifest equality checks declared geometry metadata only; it does not prove optical equivalence, "
            "XOR equality, DRC, LVS, or foundry readiness"
        ),
    }


def normalize_layout_manifest(manifest: LayoutManifest) -> LayoutManifest:
    payload = manifest.model_dump()
    payload["layer_map"] = dict(sorted(manifest.layer_map.items()))
    payload["cell_hierarchy"] = list(dict.fromkeys(manifest.cell_hierarchy))
    payload["status"] = "normalized"
    payload["provenance"] = [*manifest.provenance, "layout-manifest-normalization"]
    return revalidate_internal(LayoutManifest, payload)
