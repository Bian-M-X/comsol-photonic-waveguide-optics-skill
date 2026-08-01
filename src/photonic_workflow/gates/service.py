from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import GateName, GateRecord, GateStatus, Validity
from photonic_workflow.models.io import (
    atomic_write_text,
    contract_payload,
    parse_contract,
    revalidate_internal,
)

GATE_DEFINITIONS: dict[GateName, dict[str, Any]] = {
    GateName.G0: {
        "name": "device-contract",
        "requires": ["topology", "ports", "band", "stack", "modes", "metrics", "tolerances", "claim"],
    },
    GateName.G1: {
        "name": "port-and-straight-waveguide-baseline",
        "requires": ["modes", "orientation", "normalization", "reference-planes", "mesh", "boundary", "power"],
    },
    GateName.G2: {
        "name": "component-qualification",
        "requires": ["complete-complex-s", "modes", "passivity", "reciprocity", "energy", "convergence"],
    },
    GateName.G3: {
        "name": "assembly-contract",
        "requires": ["instances", "connections", "port-occupancy", "mode-match", "shared-grid", "conventions"],
    },
    GateName.G4: {
        "name": "circuit-behavior",
        "requires": ["external-s", "singular-value", "reciprocity", "energy", "sampling", "sensitivity"],
    },
    GateName.G5: {
        "name": "layout-and-connectivity",
        "requires": ["port-aware-layout", "extracted-netlist", "drc", "pdk-version", "routing-rules"],
    },
    GateName.G6: {
        "name": "promoted-full-wave-subassembly",
        "requires": ["reference-plane-parity", "mode-parity", "complex-comparison", "tolerance", "root-cause"],
    },
    GateName.G7: {
        "name": "robustness-and-optimization",
        "requires": ["baseline", "objective", "constraints", "solver-noise", "corners", "high-fidelity-reevaluation"],
    },
    GateName.G8: {
        "name": "evidence-package",
        "requires": ["source", "manifests", "logs", "tables", "plots", "ledger", "limitations", "next-action"],
    },
    GateName.M0: {
        "name": "test-ready",
        "requires": ["test-plan", "packaging-interface", "instrument-aliases", "safety-limits"],
    },
    GateName.M1: {
        "name": "raw-data-integrity",
        "requires": ["immutable-raw-data", "hashes", "setup-metadata", "analysis-link"],
    },
    GateName.M2: {
        "name": "calibrated-measurement",
        "requires": ["calibration", "uncertainty", "processed-data-provenance"],
    },
    GateName.M3: {
        "name": "simulation-measurement-correlation",
        "requires": ["device-identity", "reference-plane-alignment", "common-metrics", "residuals"],
    },
    GateName.M4: {
        "name": "compact-model-recalibrated",
        "requires": ["fit-provenance", "fit-error", "validity-envelope", "release-record"],
    },
}


class GateLedger:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.path = self.project_root / "verification" / "gates.json"

    def default_records(self) -> list[GateRecord]:
        return [
            GateRecord(
                stable_id=f"gate:{gate.value}",
                name=definition["name"],
                source="photonic gate definitions",
                status=GateStatus.BLOCKED,
                validity="unknown",
                gate=gate,
                reason="required evidence has not been recorded",
                next_action=f"collect evidence for {gate.value}",
            )
            for gate, definition in GATE_DEFINITIONS.items()
        ]

    def load(self, *, create_if_missing: bool = False) -> list[GateRecord]:
        if not self.path.exists():
            records = self.default_records()
            if create_if_missing:
                self.save(records)
            return records
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise InvalidInputError(f"invalid gate ledger JSON: {self.path}: {exc}") from exc
        if not isinstance(payload, list):
            raise InvalidInputError("gate ledger must be a JSON array")
        records: list[GateRecord] = []
        for item in payload:
            model = parse_contract(item, "GateRecord")
            assert isinstance(model, GateRecord)
            records.append(model)
        actual = {record.gate for record in records}
        missing = set(GATE_DEFINITIONS) - actual
        duplicates = len(actual) != len(records)
        if missing or duplicates:
            raise InvalidInputError(
                "gate ledger must contain each G0-G8 and M0-M4 exactly once"
            )
        return records

    def save(self, records: list[GateRecord]) -> None:
        payload = [contract_payload(record) for record in records]
        atomic_write_text(
            self.path,
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        )

    def update(
        self,
        gate: GateName,
        status: GateStatus,
        *,
        evidence: list[str],
        metrics: dict[str, float | str] | None = None,
        reason: str,
        next_action: str,
        dry_run: bool = False,
    ) -> GateRecord:
        if status == GateStatus.PASS and not evidence:
            raise InvalidInputError("a passing gate requires explicit evidence")
        if status == GateStatus.NOT_APPLICABLE and not reason.strip():
            raise InvalidInputError("not_applicable requires a reason")
        records = self.load(create_if_missing=not dry_run)
        index = next((index for index, record in enumerate(records) if record.gate == gate), None)
        if index is None:
            raise InvalidInputError(f"unknown gate: {gate.value}")
        previous = records[index]
        payload = previous.model_dump()
        payload.update(
            {
                "revision": str(int(previous.revision) + 1) if previous.revision.isdigit() else previous.revision,
                "status": status,
                "validity": Validity.VALID if status == GateStatus.PASS else Validity.UNKNOWN,
                "evidence": evidence,
                "metrics": metrics or {},
                "reason": reason,
                "next_action": next_action,
            }
        )
        updated = revalidate_internal(GateRecord, payload)
        records[index] = updated
        if not dry_run:
            self.save(records)
        return updated

    def summary(self) -> dict[str, Any]:
        records = self.load()
        return {
            "gates": [
                {
                    "gate": record.gate.value,
                    "name": record.name,
                    "status": record.status.value,
                    "evidence_count": len(record.evidence),
                    "reason": record.reason,
                    "next_action": record.next_action,
                }
                for record in records
            ],
            "all_gates_passed": all(
                record.status in {GateStatus.PASS, GateStatus.NOT_APPLICABLE}
                for record in records
                if record.gate.value.startswith("G")
            ),
            "measurement_track_complete": all(
                record.status in {GateStatus.PASS, GateStatus.NOT_APPLICABLE}
                for record in records
                if record.gate.value.startswith("M")
            ),
        }
