"""Pure operations for independent backend adoption-gate records."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from photonic_workflow.exceptions import InvalidInputError, SecurityViolationError
from photonic_workflow.models import (
    BACKEND_ADOPTION_DEFINITIONS,
    BackendAdoptionCheck,
    BackendAdoptionGateRecord,
    BackendAdoptionTarget,
    GateStatus,
    Validity,
)
from photonic_workflow.models.io import (
    create_contract,
    load_contract,
    revalidate_internal,
    write_contract,
)
from photonic_workflow.security import ensure_within_allowed_roots


def _increment_revision(revision: str) -> str:
    return str(int(revision) + 1) if revision.isdigit() else revision


def new_backend_adoption_gate(
    target: BackendAdoptionTarget | str,
    *,
    source: str,
    name: str | None = None,
) -> BackendAdoptionGateRecord:
    """Create one canonical, fully populated, blocked backend gate."""

    resolved = BackendAdoptionTarget(target)
    return BackendAdoptionGateRecord(
        stable_id=f"adoption:{resolved.value}",
        name=name or f"{resolved.value} adoption gate",
        source=source,
        target=resolved,
    )


def new_backend_adoption_gates(
    *,
    source: str,
) -> tuple[BackendAdoptionGateRecord, ...]:
    """Create independent blocked records for every declared backend."""

    return tuple(
        new_backend_adoption_gate(target, source=source)
        for target in BACKEND_ADOPTION_DEFINITIONS
    )


def record_backend_adoption_check(
    gate: BackendAdoptionGateRecord,
    check: BackendAdoptionCheck | str,
    status: GateStatus | str,
    *,
    evidence: list[str],
    reason: str,
) -> BackendAdoptionGateRecord:
    """Return a revised gate with one explicit check result.

    Updating a check resets the gate decision to ``blocked``. Call
    :func:`evaluate_backend_adoption_gate` to make a new decision from the
    complete required-check set.
    """

    resolved_check = BackendAdoptionCheck(check)
    resolved_status = GateStatus(status)
    if resolved_check not in gate.required_checks:
        raise InvalidInputError(
            f"{resolved_check.value} is not required by {gate.target.value}"
        )
    if resolved_status == GateStatus.NOT_APPLICABLE:
        raise InvalidInputError(
            "required adoption checks cannot be not_applicable"
        )
    checks = [result.model_dump() for result in gate.checks]
    index = next(
        (
            index
            for index, result in enumerate(gate.checks)
            if result.check == resolved_check
        ),
        None,
    )
    if index is None:
        raise InvalidInputError(
            f"missing canonical adoption check: {resolved_check.value}"
        )
    previous = gate.checks[index]
    checks[index].update(
        {
            "revision": _increment_revision(previous.revision),
            "status": resolved_status,
            "validity": (
                Validity.VALID
                if resolved_status == GateStatus.PASS
                else (
                    Validity.INVALID
                    if resolved_status == GateStatus.FAIL
                    else Validity.UNKNOWN
                )
            ),
            "evidence": list(evidence),
            "reason": reason,
        }
    )
    payload = gate.model_dump()
    payload.update(
        {
            "revision": _increment_revision(gate.revision),
            "checks": checks,
            "status": GateStatus.BLOCKED,
            "validity": Validity.UNKNOWN,
            "reason": "backend adoption decision requires evaluation",
            "next_action": "evaluate the complete required-check set",
        }
    )
    return revalidate_internal(BackendAdoptionGateRecord, payload)


def evaluate_backend_adoption_gate(
    gate: BackendAdoptionGateRecord,
) -> BackendAdoptionGateRecord:
    """Derive a fail-closed decision from the complete canonical check set."""

    if all(result.status == GateStatus.PASS for result in gate.checks):
        status = GateStatus.PASS
        validity = Validity.VALID
        reason = "all required backend checks passed with explicit evidence"
        next_action = "preserve evidence and re-evaluate after backend changes"
    elif any(result.status == GateStatus.FAIL for result in gate.checks):
        status = GateStatus.FAIL
        validity = Validity.INVALID
        reason = "one or more required backend checks failed"
        next_action = "resolve failed checks, record new evidence, and re-evaluate"
    else:
        status = GateStatus.BLOCKED
        validity = Validity.UNKNOWN
        reason = "one or more required backend checks remain blocked"
        next_action = "collect evidence for every blocked required check"
    payload = gate.model_dump()
    payload.update(
        {
            "revision": _increment_revision(gate.revision),
            "status": status,
            "validity": validity,
            "reason": reason,
            "next_action": next_action,
        }
    )
    return revalidate_internal(BackendAdoptionGateRecord, payload)


class BackendAdoptionStore:
    """Confined, atomic persistence for independent backend adoption gates."""

    def __init__(
        self,
        project_root: Path,
        allowed_roots: Sequence[Path] | None = None,
    ) -> None:
        candidate = project_root.resolve()
        configured_roots = (candidate,) if allowed_roots is None else allowed_roots
        roots = tuple(root.resolve() for root in configured_roots)
        if not roots:
            raise InvalidInputError("backend adoption store requires an allowed root")
        self.allowed_roots = roots
        self.project_root = ensure_within_allowed_roots(candidate, roots)
        canonical_root = self.project_root / "verification" / "adoption"
        resolved_root = canonical_root.resolve()
        if os.path.normcase(str(resolved_root)) != os.path.normcase(
            str(canonical_root)
        ):
            raise SecurityViolationError(
                "backend adoption directory cannot be a symlink or junction"
            )
        self.root = ensure_within_allowed_roots(
            resolved_root,
            roots,
        )

    def path_for(self, target: BackendAdoptionTarget | str) -> Path:
        resolved = BackendAdoptionTarget(target)
        return ensure_within_allowed_roots(
            self.root / f"{resolved.value}.json",
            (self.root,),
        )

    def exists(self, target: BackendAdoptionTarget | str) -> bool:
        return self.path_for(target).is_file()

    def _validated_evidence(self, evidence: list[str]) -> list[str]:
        normalized: list[str] = []
        for reference in evidence:
            if not reference.strip():
                raise InvalidInputError(
                    "backend adoption evidence entries must not be empty"
                )
            relative = Path(reference)
            if relative.is_absolute():
                raise InvalidInputError(
                    "backend adoption evidence must use project-relative paths"
                )
            checked = ensure_within_allowed_roots(
                self.project_root / relative,
                (self.project_root,),
            )
            if not checked.is_file():
                raise InvalidInputError(
                    f"backend adoption evidence is missing or unreadable: {reference}"
                )
            try:
                with checked.open("rb") as stream:
                    stream.read(1)
            except OSError as exc:
                raise InvalidInputError(
                    f"backend adoption evidence is missing or unreadable: {reference}"
                ) from exc
            normalized.append(checked.relative_to(self.project_root).as_posix())
        return normalized

    def initialize(
        self,
        target: BackendAdoptionTarget | str,
        *,
        source: str,
        dry_run: bool = False,
    ) -> BackendAdoptionGateRecord:
        resolved = BackendAdoptionTarget(target)
        path = self.path_for(resolved)
        if path.exists():
            raise InvalidInputError(
                f"backend adoption gate already exists: {resolved.value}"
            )
        gate = new_backend_adoption_gate(resolved, source=source)
        if not dry_run:
            try:
                create_contract(path, gate)
            except FileExistsError as exc:
                raise InvalidInputError(
                    f"backend adoption gate already exists: {resolved.value}"
                ) from exc
        return gate

    def load(
        self,
        target: BackendAdoptionTarget | str,
    ) -> BackendAdoptionGateRecord:
        resolved = BackendAdoptionTarget(target)
        model = load_contract(
            self.path_for(resolved),
            "BackendAdoptionGateRecord",
        )
        if not isinstance(model, BackendAdoptionGateRecord):
            raise InvalidInputError(
                f"expected BackendAdoptionGateRecord for {resolved.value}"
            )
        if model.target != resolved:
            raise InvalidInputError(
                "backend adoption gate target does not match its filename"
            )
        for result in model.checks:
            if result.status in {GateStatus.PASS, GateStatus.FAIL}:
                normalized = self._validated_evidence(result.evidence)
                if normalized != result.evidence:
                    raise InvalidInputError(
                        "backend adoption evidence paths are not canonical"
                    )
        return model

    def record(
        self,
        target: BackendAdoptionTarget | str,
        check: BackendAdoptionCheck | str,
        status: GateStatus | str,
        *,
        evidence: list[str],
        reason: str,
        dry_run: bool = False,
    ) -> BackendAdoptionGateRecord:
        if not reason.strip():
            raise InvalidInputError("backend adoption check requires a reason")
        resolved_status = GateStatus(status)
        if resolved_status in {GateStatus.PASS, GateStatus.FAIL} and not evidence:
            raise InvalidInputError(
                f"a {resolved_status.value} adoption check requires explicit evidence"
            )
        checked_evidence = self._validated_evidence(evidence)
        gate = self.load(target)
        updated = record_backend_adoption_check(
            gate,
            check,
            resolved_status,
            evidence=checked_evidence,
            reason=reason,
        )
        if not dry_run:
            write_contract(self.path_for(gate.target), updated)
        return updated

    def evaluate(
        self,
        target: BackendAdoptionTarget | str,
        *,
        dry_run: bool = False,
    ) -> BackendAdoptionGateRecord:
        gate = self.load(target)
        evaluated = evaluate_backend_adoption_gate(gate)
        if not dry_run:
            write_contract(self.path_for(gate.target), evaluated)
        return evaluated


__all__ = [
    "BACKEND_ADOPTION_DEFINITIONS",
    "BackendAdoptionStore",
    "evaluate_backend_adoption_gate",
    "new_backend_adoption_gate",
    "new_backend_adoption_gates",
    "record_backend_adoption_check",
]
