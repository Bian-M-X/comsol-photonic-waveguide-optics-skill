"""Fail-closed records for adopting optional execution backends.

These gates are operational readiness records. They deliberately do not use
``GateName`` and cannot advance the G0-G8 design or M0-M4 measurement tracks.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import Field, model_validator

from .contracts import ContractBase, GateStatus, Validity

_UNRECORDED_CHECK_REASON = "required evidence has not been recorded"
_UNRECORDED_GATE_REASON = (
    "required backend adoption evidence has not been recorded"
)
_DEFAULT_GATE_NEXT_ACTION = "collect the next required backend check"


class BackendAdoptionPhase(StrEnum):
    PHASE_B = "phase-b"
    PHASE_C = "phase-c"


class BackendAdoptionTarget(StrEnum):
    MATLAB_RUNTIME = "matlab-runtime"
    MATLAB_COMSOL_LIVELINK = "matlab-comsol-livelink"
    MATLAB_LUMERICAL = "matlab-lumerical"
    MATLAB_INSTRUMENT = "matlab-instrument"
    MATLAB_SIMULINK = "matlab-simulink"
    LUMERICAL = "lumerical"
    REAL_PDK_DRC_LVS = "real-pdk-drc-lvs"


class BackendAdoptionCheck(StrEnum):
    CAPABILITY_PROBE = "capability-probe"
    INTERACTIVE_USER_CONTEXT = "interactive-user-context"
    DRY_RUN_PLAN = "dry-run-plan"
    AUTHORIZED_SMOKE = "authorized-smoke"
    MATLAB_BATCH_SMOKE = "matlab-batch-smoke"
    MATLAB_UNITTEST = "matlab-unittest"
    JSON_ROUND_TRIP = "json-round-trip"
    MAT_V73_HDF5_ROUND_TRIP = "mat-v7.3-hdf5-round-trip"
    COMPLEX_ARRAY_ROUND_TRIP = "complex-array-round-trip"
    LEGACY_GDS_KLAYOUT_FIXTURE = "legacy-gds-klayout-fixture"
    FDFD_FIXTURE = "fdfd-fixture"
    RF_TOUCHSTONE_FIXTURE = "rf-touchstone-fixture"
    TIMEOUT_FAILURE_CLEANUP = "timeout-failure-cleanup"
    TIMEOUT_CANCELLATION_ORPHAN_CLEANUP = (
        "timeout-cancellation-orphan-cleanup"
    )
    REDACTION_AUDIT = "redaction-audit"
    RESULT_INSPECTION = "result-inspection"
    ROLLBACK = "rollback"
    NATIVE_COMSOL_JAVA_PARITY = "native-comsol-java-parity"
    DIRECT_LUMERICAL_PARITY = "direct-lumerical-parity"
    INSTRUMENT_IDENTITY = "instrument-identity"
    PHYSICAL_SAFETY_LIMITS = "physical-safety-limits"
    IMMUTABLE_RAW_DATA = "immutable-raw-data"
    MODEL_IO_CONTRACT = "model-io-contract"
    REDUCED_MODEL_CLAIM_BOUNDARY = "reduced-model-claim-boundary"
    REFERENCE_MODEL_PARITY = "reference-model-parity"
    PRODUCT_SPECIFIC_ENTITLEMENT = "product-specific-entitlement"
    SOLVER_FIXTURE = "solver-fixture"
    REFERENCE_FIXTURE_PARITY = "reference-fixture-parity"
    PDK_FINGERPRINT = "pdk-fingerprint"
    CONTROLLED_DECK_IDENTITY = "controlled-deck-identity"
    DRC_EXECUTION = "drc-execution"
    LVS_EXECUTION = "lvs-execution"
    EXTRACTED_LOGICAL_PARITY = "extracted-logical-parity"
    SIGNOFF_SCOPE = "signoff-scope"


@dataclass(frozen=True, slots=True)
class BackendAdoptionDefinition:
    target: BackendAdoptionTarget
    phase: BackendAdoptionPhase
    required_checks: tuple[BackendAdoptionCheck, ...]


_COMMON_PHASE_C_CHECKS = (
    BackendAdoptionCheck.CAPABILITY_PROBE,
    BackendAdoptionCheck.DRY_RUN_PLAN,
    BackendAdoptionCheck.AUTHORIZED_SMOKE,
    BackendAdoptionCheck.TIMEOUT_FAILURE_CLEANUP,
    BackendAdoptionCheck.REDACTION_AUDIT,
    BackendAdoptionCheck.RESULT_INSPECTION,
    BackendAdoptionCheck.ROLLBACK,
)


def _definition(
    target: BackendAdoptionTarget,
    phase: BackendAdoptionPhase,
    required_checks: tuple[BackendAdoptionCheck, ...],
) -> BackendAdoptionDefinition:
    if len(required_checks) != len(set(required_checks)):
        raise RuntimeError(f"{target.value} adoption definition contains duplicates")
    return BackendAdoptionDefinition(
        target=target,
        phase=phase,
        required_checks=required_checks,
    )


BACKEND_ADOPTION_DEFINITIONS: Mapping[
    BackendAdoptionTarget,
    BackendAdoptionDefinition,
] = MappingProxyType(
    {
        BackendAdoptionTarget.MATLAB_RUNTIME: _definition(
            BackendAdoptionTarget.MATLAB_RUNTIME,
            BackendAdoptionPhase.PHASE_B,
            (
                BackendAdoptionCheck.CAPABILITY_PROBE,
                BackendAdoptionCheck.INTERACTIVE_USER_CONTEXT,
                BackendAdoptionCheck.DRY_RUN_PLAN,
                BackendAdoptionCheck.MATLAB_BATCH_SMOKE,
                BackendAdoptionCheck.MATLAB_UNITTEST,
                BackendAdoptionCheck.JSON_ROUND_TRIP,
                BackendAdoptionCheck.MAT_V73_HDF5_ROUND_TRIP,
                BackendAdoptionCheck.COMPLEX_ARRAY_ROUND_TRIP,
                BackendAdoptionCheck.LEGACY_GDS_KLAYOUT_FIXTURE,
                BackendAdoptionCheck.FDFD_FIXTURE,
                BackendAdoptionCheck.RF_TOUCHSTONE_FIXTURE,
                BackendAdoptionCheck.TIMEOUT_CANCELLATION_ORPHAN_CLEANUP,
                BackendAdoptionCheck.REDACTION_AUDIT,
                BackendAdoptionCheck.RESULT_INSPECTION,
                BackendAdoptionCheck.ROLLBACK,
            ),
        ),
        BackendAdoptionTarget.MATLAB_COMSOL_LIVELINK: _definition(
            BackendAdoptionTarget.MATLAB_COMSOL_LIVELINK,
            BackendAdoptionPhase.PHASE_C,
            (
                *_COMMON_PHASE_C_CHECKS,
                BackendAdoptionCheck.NATIVE_COMSOL_JAVA_PARITY,
            ),
        ),
        BackendAdoptionTarget.MATLAB_LUMERICAL: _definition(
            BackendAdoptionTarget.MATLAB_LUMERICAL,
            BackendAdoptionPhase.PHASE_C,
            (
                *_COMMON_PHASE_C_CHECKS,
                BackendAdoptionCheck.DIRECT_LUMERICAL_PARITY,
            ),
        ),
        BackendAdoptionTarget.MATLAB_INSTRUMENT: _definition(
            BackendAdoptionTarget.MATLAB_INSTRUMENT,
            BackendAdoptionPhase.PHASE_C,
            (
                *_COMMON_PHASE_C_CHECKS,
                BackendAdoptionCheck.INSTRUMENT_IDENTITY,
                BackendAdoptionCheck.PHYSICAL_SAFETY_LIMITS,
                BackendAdoptionCheck.IMMUTABLE_RAW_DATA,
            ),
        ),
        BackendAdoptionTarget.MATLAB_SIMULINK: _definition(
            BackendAdoptionTarget.MATLAB_SIMULINK,
            BackendAdoptionPhase.PHASE_C,
            (
                *_COMMON_PHASE_C_CHECKS,
                BackendAdoptionCheck.MODEL_IO_CONTRACT,
                BackendAdoptionCheck.REDUCED_MODEL_CLAIM_BOUNDARY,
                BackendAdoptionCheck.REFERENCE_MODEL_PARITY,
            ),
        ),
        BackendAdoptionTarget.LUMERICAL: _definition(
            BackendAdoptionTarget.LUMERICAL,
            BackendAdoptionPhase.PHASE_C,
            (
                *_COMMON_PHASE_C_CHECKS,
                BackendAdoptionCheck.PRODUCT_SPECIFIC_ENTITLEMENT,
                BackendAdoptionCheck.SOLVER_FIXTURE,
                BackendAdoptionCheck.REFERENCE_FIXTURE_PARITY,
            ),
        ),
        BackendAdoptionTarget.REAL_PDK_DRC_LVS: _definition(
            BackendAdoptionTarget.REAL_PDK_DRC_LVS,
            BackendAdoptionPhase.PHASE_C,
            (
                *_COMMON_PHASE_C_CHECKS,
                BackendAdoptionCheck.PDK_FINGERPRINT,
                BackendAdoptionCheck.CONTROLLED_DECK_IDENTITY,
                BackendAdoptionCheck.DRC_EXECUTION,
                BackendAdoptionCheck.LVS_EXECUTION,
                BackendAdoptionCheck.EXTRACTED_LOGICAL_PARITY,
                BackendAdoptionCheck.SIGNOFF_SCOPE,
            ),
        ),
    }
)


class BackendAdoptionCheckRecord(ContractBase):
    contract_type = "BackendAdoptionCheckRecord"
    target: BackendAdoptionTarget = BackendAdoptionTarget.MATLAB_RUNTIME
    check: BackendAdoptionCheck = BackendAdoptionCheck.CAPABILITY_PROBE
    status: GateStatus = GateStatus.BLOCKED
    evidence: list[str] = Field(default_factory=list)
    reason: str = _UNRECORDED_CHECK_REASON

    @model_validator(mode="before")
    @classmethod
    def _derive_validity(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if "status" in payload and "validity" not in payload:
            status = GateStatus(payload["status"])
            if status == GateStatus.PASS:
                payload["validity"] = Validity.VALID
            elif status == GateStatus.FAIL:
                payload["validity"] = Validity.INVALID
        return payload

    @model_validator(mode="after")
    def _validate_evidence_and_membership(self) -> BackendAdoptionCheckRecord:
        definition = BACKEND_ADOPTION_DEFINITIONS[self.target]
        if self.check not in definition.required_checks:
            raise ValueError(
                f"{self.check.value} must occur exactly once only in a target "
                f"that requires it; {self.target.value} does not"
            )
        expected_id = f"adoption-check:{self.target.value}:{self.check.value}"
        if self.stable_id != expected_id:
            raise ValueError(
                f"backend adoption check stable_id must be {expected_id!r}"
            )
        if self.status == GateStatus.NOT_APPLICABLE:
            raise ValueError(
                "required adoption checks cannot be not_applicable"
            )
        if any(not item.strip() for item in self.evidence):
            raise ValueError("adoption-check evidence entries must not be empty")
        if self.status in {GateStatus.PASS, GateStatus.FAIL} and not self.evidence:
            raise ValueError(
                f"a {self.status.value} adoption check requires explicit evidence"
            )
        if not self.reason.strip():
            raise ValueError("an adoption-check reason must not be empty")
        if (
            self.status in {GateStatus.PASS, GateStatus.FAIL}
            and self.reason == _UNRECORDED_CHECK_REASON
        ):
            raise ValueError(
                "a decided adoption check requires an explicit result reason"
            )
        expected_validity = {
            GateStatus.PASS: Validity.VALID,
            GateStatus.FAIL: Validity.INVALID,
            GateStatus.BLOCKED: Validity.UNKNOWN,
        }[self.status]
        if self.validity != expected_validity:
            raise ValueError(
                f"{self.status.value} adoption check requires validity "
                f"{expected_validity.value}"
            )
        return self


class BackendAdoptionGateRecord(ContractBase):
    contract_type = "BackendAdoptionGateRecord"
    target: BackendAdoptionTarget = BackendAdoptionTarget.MATLAB_RUNTIME
    phase: BackendAdoptionPhase = BackendAdoptionPhase.PHASE_B
    required_checks: tuple[BackendAdoptionCheck, ...] = Field(
        default_factory=lambda: BACKEND_ADOPTION_DEFINITIONS[
            BackendAdoptionTarget.MATLAB_RUNTIME
        ].required_checks
    )
    checks: list[BackendAdoptionCheckRecord] = Field(default_factory=list)
    status: GateStatus = GateStatus.BLOCKED
    reason: str = _UNRECORDED_GATE_REASON
    next_action: str = _DEFAULT_GATE_NEXT_ACTION

    @model_validator(mode="before")
    @classmethod
    def _fill_canonical_definition(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        target = BackendAdoptionTarget(
            payload.get("target", BackendAdoptionTarget.MATLAB_RUNTIME)
        )
        definition = BACKEND_ADOPTION_DEFINITIONS[target]
        payload.setdefault("phase", definition.phase)
        payload.setdefault("required_checks", definition.required_checks)
        if "checks" not in payload:
            source = str(payload.get("source", "backend adoption gate"))
            payload["checks"] = [
                {
                    "stable_id": f"adoption-check:{target.value}:{check.value}",
                    "name": f"{target.value} {check.value}",
                    "source": source,
                    "target": target,
                    "check": check,
                    "status": GateStatus.BLOCKED,
                    "reason": _UNRECORDED_CHECK_REASON,
                }
                for check in definition.required_checks
            ]
        if "status" in payload and "validity" not in payload:
            status = GateStatus(payload["status"])
            if status == GateStatus.PASS:
                payload["validity"] = Validity.VALID
            elif status == GateStatus.FAIL:
                payload["validity"] = Validity.INVALID
        return payload

    @model_validator(mode="after")
    def _validate_complete_gate(self) -> BackendAdoptionGateRecord:
        definition = BACKEND_ADOPTION_DEFINITIONS[self.target]
        expected_id = f"adoption:{self.target.value}"
        if self.stable_id != expected_id:
            raise ValueError(
                f"backend adoption gate stable_id must be {expected_id!r}"
            )
        if self.phase != definition.phase:
            raise ValueError(
                f"{self.target.value} belongs to {definition.phase.value}"
            )
        if self.required_checks != definition.required_checks:
            raise ValueError(
                "required_checks must exactly match the canonical backend "
                "adoption definition"
            )
        actual_checks = tuple(result.check for result in self.checks)
        if actual_checks != definition.required_checks:
            raise ValueError(
                "checks must contain every canonical required check exactly once "
                "in definition order"
            )
        if any(result.target != self.target for result in self.checks):
            raise ValueError("every check record must name the gate target")
        if not self.reason.strip():
            raise ValueError("a backend adoption gate reason must not be empty")
        if not self.next_action.strip():
            raise ValueError(
                "a backend adoption gate next_action must not be empty"
            )
        if self.status == GateStatus.NOT_APPLICABLE:
            raise ValueError("a named backend adoption gate cannot be not_applicable")
        if self.status in {GateStatus.PASS, GateStatus.FAIL} and (
            self.reason == _UNRECORDED_GATE_REASON
            or self.next_action == _DEFAULT_GATE_NEXT_ACTION
        ):
            raise ValueError(
                "a decided backend adoption gate requires an explicit rationale"
            )
        if self.status == GateStatus.PASS and not all(
            result.status == GateStatus.PASS and result.evidence
            for result in self.checks
        ):
            raise ValueError(
                "a passing backend adoption gate requires all required checks "
                "to pass with explicit evidence"
            )
        if self.status == GateStatus.FAIL and not any(
            result.status == GateStatus.FAIL for result in self.checks
        ):
            raise ValueError(
                "a failed backend adoption gate requires a failed evidence record"
            )
        expected_validity = {
            GateStatus.PASS: Validity.VALID,
            GateStatus.FAIL: Validity.INVALID,
            GateStatus.BLOCKED: Validity.UNKNOWN,
        }[self.status]
        if self.validity != expected_validity:
            raise ValueError(
                f"{self.status.value} backend adoption gate requires validity "
                f"{expected_validity.value}"
            )
        return self


__all__ = [
    "BACKEND_ADOPTION_DEFINITIONS",
    "BackendAdoptionCheck",
    "BackendAdoptionCheckRecord",
    "BackendAdoptionDefinition",
    "BackendAdoptionGateRecord",
    "BackendAdoptionPhase",
    "BackendAdoptionTarget",
]
