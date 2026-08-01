from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from photonic_workflow.adoption import (
    BACKEND_ADOPTION_DEFINITIONS,
    BackendAdoptionStore,
    evaluate_backend_adoption_gate,
    new_backend_adoption_gate,
    new_backend_adoption_gates,
    record_backend_adoption_check,
)
from photonic_workflow.exceptions import InvalidInputError, SecurityViolationError
from photonic_workflow.models import (
    BackendAdoptionCheck,
    BackendAdoptionCheckRecord,
    BackendAdoptionGateRecord,
    BackendAdoptionPhase,
    BackendAdoptionTarget,
    GateStatus,
    Validity,
)
from photonic_workflow.models.io import load_contract, write_contract


class BackendAdoptionGateTests(unittest.TestCase):
    def test_named_backends_have_independent_fail_closed_definitions(self) -> None:
        expected = {
            BackendAdoptionTarget.MATLAB_RUNTIME,
            BackendAdoptionTarget.MATLAB_COMSOL_LIVELINK,
            BackendAdoptionTarget.MATLAB_LUMERICAL,
            BackendAdoptionTarget.MATLAB_INSTRUMENT,
            BackendAdoptionTarget.MATLAB_SIMULINK,
            BackendAdoptionTarget.LUMERICAL,
            BackendAdoptionTarget.REAL_PDK_DRC_LVS,
        }
        self.assertEqual(set(BACKEND_ADOPTION_DEFINITIONS), expected)
        phase_c_targets = expected - {BackendAdoptionTarget.MATLAB_RUNTIME}
        common_phase_c_checks = {
            BackendAdoptionCheck.CAPABILITY_PROBE,
            BackendAdoptionCheck.DRY_RUN_PLAN,
            BackendAdoptionCheck.AUTHORIZED_SMOKE,
            BackendAdoptionCheck.TIMEOUT_FAILURE_CLEANUP,
            BackendAdoptionCheck.REDACTION_AUDIT,
            BackendAdoptionCheck.RESULT_INSPECTION,
            BackendAdoptionCheck.ROLLBACK,
        }
        for target in phase_c_targets:
            definition = BACKEND_ADOPTION_DEFINITIONS[target]
            self.assertEqual(definition.phase, BackendAdoptionPhase.PHASE_C)
            self.assertTrue(
                common_phase_c_checks.issubset(definition.required_checks)
            )
        records = new_backend_adoption_gates(source="unit test")
        self.assertEqual({record.target for record in records}, expected)
        self.assertEqual(len({record.stable_id for record in records}), len(expected))
        for record in records:
            with self.subTest(target=record.target.value):
                definition = BACKEND_ADOPTION_DEFINITIONS[record.target]
                self.assertEqual(record.phase, definition.phase)
                self.assertEqual(record.required_checks, definition.required_checks)
                self.assertEqual(record.status, GateStatus.BLOCKED)
                self.assertEqual(record.validity, Validity.UNKNOWN)
                self.assertEqual(
                    tuple(result.check for result in record.checks),
                    definition.required_checks,
                )
                self.assertTrue(
                    all(result.status == GateStatus.BLOCKED for result in record.checks)
                )
                self.assertTrue(all(not result.evidence for result in record.checks))
                self.assertTrue(
                    all(
                        not result.check.value.startswith(("G", "M"))
                        for result in record.checks
                    )
                )

    def test_matlab_runtime_phase_b_covers_required_fixture_evidence(self) -> None:
        definition = BACKEND_ADOPTION_DEFINITIONS[
            BackendAdoptionTarget.MATLAB_RUNTIME
        ]
        self.assertEqual(definition.phase, BackendAdoptionPhase.PHASE_B)
        self.assertEqual(
            set(definition.required_checks),
            {
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
            },
        )

    def test_passing_or_failing_check_requires_explicit_evidence(self) -> None:
        for status in (GateStatus.PASS, GateStatus.FAIL):
            with self.subTest(status=status.value), self.assertRaisesRegex(
                ValidationError,
                "requires explicit evidence",
            ):
                BackendAdoptionCheckRecord(
                    stable_id="adoption-check:matlab-runtime:capability-probe",
                    name="missing evidence",
                    source="unit test",
                    target=BackendAdoptionTarget.MATLAB_RUNTIME,
                    check=BackendAdoptionCheck.CAPABILITY_PROBE,
                    status=status,
                )

        with self.assertRaisesRegex(ValidationError, "must not be empty"):
            BackendAdoptionCheckRecord(
                stable_id="adoption-check:matlab-runtime:capability-probe",
                name="blank evidence",
                source="unit test",
                target=BackendAdoptionTarget.MATLAB_RUNTIME,
                check=BackendAdoptionCheck.CAPABILITY_PROBE,
                status=GateStatus.PASS,
                evidence=["   "],
                reason="probe passed",
            )
        with self.assertRaisesRegex(ValidationError, "reason must not be empty"):
            BackendAdoptionCheckRecord(
                stable_id="adoption-check:matlab-runtime:capability-probe",
                name="blank reason",
                source="unit test",
                target=BackendAdoptionTarget.MATLAB_RUNTIME,
                check=BackendAdoptionCheck.CAPABILITY_PROBE,
                status=GateStatus.PASS,
                evidence=["verification/probe.json"],
                reason="   ",
            )

    def test_not_applicable_cannot_bypass_a_required_check(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "required adoption checks cannot be not_applicable",
        ):
            BackendAdoptionCheckRecord(
                stable_id="adoption-check:matlab-runtime:capability-probe",
                name="not applicable",
                source="unit test",
                target=BackendAdoptionTarget.MATLAB_RUNTIME,
                check=BackendAdoptionCheck.CAPABILITY_PROBE,
                status=GateStatus.NOT_APPLICABLE,
                reason="attempted bypass",
            )

    def test_gate_rejects_missing_duplicate_or_cross_backend_checks(self) -> None:
        gate = new_backend_adoption_gate(
            BackendAdoptionTarget.MATLAB_RUNTIME,
            source="unit test",
        )
        base = gate.model_dump()
        invalid_checks = {
            "missing": base["checks"][:-1],
            "duplicate": [*base["checks"], base["checks"][0]],
            "cross-backend": [
                *base["checks"][:-1],
                {
                    **base["checks"][-1],
                    "check": BackendAdoptionCheck.NATIVE_COMSOL_JAVA_PARITY,
                },
            ],
        }
        for label, checks in invalid_checks.items():
            with self.subTest(label=label), self.assertRaisesRegex(
                ValidationError,
                "exactly once",
            ):
                    BackendAdoptionGateRecord(**{**base, "checks": checks})

    def test_canonical_ids_and_decision_rationale_cannot_be_tampered(self) -> None:
        gate = new_backend_adoption_gate(
            BackendAdoptionTarget.MATLAB_COMSOL_LIVELINK,
            source="unit test",
        )
        with self.assertRaisesRegex(ValidationError, "gate stable_id"):
            BackendAdoptionGateRecord(
                **{**gate.model_dump(), "stable_id": "adoption:matlab-runtime"}
            )
        check = gate.checks[0]
        with self.assertRaisesRegex(ValidationError, "check stable_id"):
            BackendAdoptionCheckRecord(
                **{
                    **check.model_dump(),
                    "stable_id": "adoption-check:matlab-runtime:capability-probe",
                }
            )
        with self.assertRaisesRegex(ValidationError, "explicit result reason"):
            BackendAdoptionCheckRecord(
                **{
                    **check.model_dump(),
                    "status": GateStatus.PASS,
                    "validity": Validity.VALID,
                    "evidence": ["verification/probe.json"],
                }
            )

        for required in gate.required_checks:
            gate = record_backend_adoption_check(
                gate,
                required,
                GateStatus.PASS,
                evidence=["verification/probe.json"],
                reason="bounded fixture passed",
            )
        gate = evaluate_backend_adoption_gate(gate)
        for field, value, message in (
            ("reason", "   ", "reason must not be empty"),
            ("next_action", "", "next_action must not be empty"),
            (
                "reason",
                "required backend adoption evidence has not been recorded",
                "explicit rationale",
            ),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                ValidationError,
                message,
            ):
                BackendAdoptionGateRecord(
                    **{**gate.model_dump(), field: value}
                )

    def test_partial_evidence_never_infers_pass(self) -> None:
        gate = new_backend_adoption_gate(
            BackendAdoptionTarget.MATLAB_RUNTIME,
            source="unit test",
        )
        updated = record_backend_adoption_check(
            gate,
            BackendAdoptionCheck.CAPABILITY_PROBE,
            GateStatus.PASS,
            evidence=["reports/matlab-capability.json"],
            reason="fixed local probe passed",
        )
        evaluated = evaluate_backend_adoption_gate(updated)
        self.assertEqual(evaluated.status, GateStatus.BLOCKED)
        self.assertEqual(evaluated.validity, Validity.UNKNOWN)
        self.assertTrue(
            any(result.status == GateStatus.BLOCKED for result in evaluated.checks)
        )

        with self.assertRaisesRegex(
            ValidationError,
            "all required checks",
        ):
            BackendAdoptionGateRecord(
                **{**updated.model_dump(), "status": GateStatus.PASS}
            )

    def test_gate_passes_only_after_every_required_check_has_pass_evidence(self) -> None:
        gate = new_backend_adoption_gate(
            BackendAdoptionTarget.MATLAB_COMSOL_LIVELINK,
            source="unit test",
        )
        for check in gate.required_checks:
            gate = record_backend_adoption_check(
                gate,
                check,
                GateStatus.PASS,
                evidence=[f"evidence/{check.value}.json"],
                reason="bounded fixture passed",
            )
        self.assertEqual(gate.status, GateStatus.BLOCKED)
        evaluated = evaluate_backend_adoption_gate(gate)
        self.assertEqual(evaluated.status, GateStatus.PASS)
        self.assertEqual(evaluated.validity, Validity.VALID)
        self.assertTrue(
            all(result.status == GateStatus.PASS for result in evaluated.checks)
        )

    def test_failed_required_check_produces_failed_gate(self) -> None:
        gate = new_backend_adoption_gate(
            BackendAdoptionTarget.LUMERICAL,
            source="unit test",
        )
        gate = record_backend_adoption_check(
            gate,
            BackendAdoptionCheck.CAPABILITY_PROBE,
            GateStatus.FAIL,
            evidence=["reports/lumerical-probe-failure.json"],
            reason="required product entitlement unavailable",
        )
        evaluated = evaluate_backend_adoption_gate(gate)
        self.assertEqual(evaluated.status, GateStatus.FAIL)
        self.assertEqual(evaluated.validity, Validity.INVALID)

    def test_contract_round_trip_preserves_check_evidence(self) -> None:
        gate = new_backend_adoption_gate(
            BackendAdoptionTarget.REAL_PDK_DRC_LVS,
            source="unit test",
        )
        gate = record_backend_adoption_check(
            gate,
            BackendAdoptionCheck.PDK_FINGERPRINT,
            GateStatus.PASS,
            evidence=["verification/pdk-fingerprint.json"],
            reason="approved fingerprint matched",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "adoption-gate.json"
            write_contract(path, gate)
            restored = load_contract(path, "BackendAdoptionGateRecord")
        self.assertEqual(restored, gate)

    def test_gate_updates_do_not_mutate_other_backend_records(self) -> None:
        gates = {
            gate.target: gate
            for gate in new_backend_adoption_gates(source="unit test")
        }
        matlab = gates[BackendAdoptionTarget.MATLAB_RUNTIME]
        updated = record_backend_adoption_check(
            matlab,
            BackendAdoptionCheck.CAPABILITY_PROBE,
            GateStatus.PASS,
            evidence=["reports/matlab-capability.json"],
            reason="probe passed",
        )
        self.assertNotEqual(updated, matlab)
        self.assertTrue(all(not result.evidence for result in matlab.checks))
        for target, record in gates.items():
            if target != BackendAdoptionTarget.MATLAB_RUNTIME:
                self.assertTrue(all(not result.evidence for result in record.checks))

    def test_store_initialization_is_dry_run_safe_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            store = BackendAdoptionStore(project, allowed_roots=[project])
            target = BackendAdoptionTarget.MATLAB_RUNTIME
            path = project / "verification" / "adoption" / "matlab-runtime.json"

            preview = store.initialize(
                target,
                source="unit test",
                dry_run=True,
            )
            self.assertEqual(preview.target, target)
            self.assertFalse(path.exists())

            created = store.initialize(target, source="unit test")
            self.assertTrue(path.is_file())
            self.assertEqual(store.load(target), created)
            original_bytes = path.read_bytes()
            with self.assertRaisesRegex(
                InvalidInputError,
                "already exists",
            ):
                store.initialize(target, source="replacement attempt")
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_store_record_requires_explicit_evidence_and_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            store = BackendAdoptionStore(project, allowed_roots=[project])
            target = BackendAdoptionTarget.MATLAB_RUNTIME
            store.initialize(target, source="unit test")
            evidence_path = project / "verification" / "probe.json"
            evidence_path.write_text("{}\n", encoding="utf-8")

            for evidence, reason, message in (
                ([], "probe passed", "evidence"),
                (["verification/probe.json"], "", "reason"),
                (["verification/probe.json"], "   ", "reason"),
            ):
                with self.subTest(
                    evidence=evidence,
                    reason=reason,
                ), self.assertRaisesRegex(InvalidInputError, message):
                    store.record(
                        target,
                        BackendAdoptionCheck.CAPABILITY_PROBE,
                        GateStatus.PASS,
                        evidence=evidence,
                        reason=reason,
                    )

    def test_store_dry_run_record_and_evaluate_do_not_change_disk(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            store = BackendAdoptionStore(project, allowed_roots=[project])
            target = BackendAdoptionTarget.MATLAB_RUNTIME
            original = store.initialize(target, source="unit test")
            evidence_path = project / "verification" / "matlab-capability.json"
            evidence_path.write_text("{}\n", encoding="utf-8")

            preview = store.record(
                target,
                BackendAdoptionCheck.CAPABILITY_PROBE,
                GateStatus.PASS,
                evidence=["verification/matlab-capability.json"],
                reason="fixed local probe passed",
                dry_run=True,
            )
            self.assertNotEqual(preview, original)
            self.assertEqual(store.load(target), original)

            recorded = store.record(
                target,
                BackendAdoptionCheck.CAPABILITY_PROBE,
                GateStatus.PASS,
                evidence=["verification/matlab-capability.json"],
                reason="fixed local probe passed",
            )
            evaluated_preview = store.evaluate(target, dry_run=True)
            self.assertEqual(evaluated_preview.status, GateStatus.BLOCKED)
            self.assertEqual(store.load(target), recorded)

            evaluated = store.evaluate(target)
            self.assertEqual(evaluated.status, GateStatus.BLOCKED)
            self.assertEqual(store.load(target), evaluated)

    def test_store_rejects_missing_absolute_or_escaping_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve() / "project"
            project.mkdir()
            store = BackendAdoptionStore(project, allowed_roots=[project])
            target = BackendAdoptionTarget.MATLAB_RUNTIME
            store.initialize(target, source="unit test")
            outside = project.parent / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")

            for evidence, error_type, message in (
                (["verification/missing.json"], InvalidInputError, "missing or unreadable"),
                ([str(outside)], InvalidInputError, "project-relative"),
                (["../outside.json"], SecurityViolationError, "outside configured allowed roots"),
                (["   "], InvalidInputError, "must not be empty"),
            ):
                with self.subTest(evidence=evidence), self.assertRaisesRegex(error_type, message):
                    store.record(
                        target,
                        BackendAdoptionCheck.CAPABILITY_PROBE,
                        GateStatus.PASS,
                        evidence=evidence,
                        reason="bounded probe evidence",
                    )

    def test_store_rejects_filename_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            store = BackendAdoptionStore(project, allowed_roots=[project])
            matlab = store.initialize(
                BackendAdoptionTarget.MATLAB_RUNTIME,
                source="unit test",
            )
            wrong_path = store.path_for(BackendAdoptionTarget.LUMERICAL)
            write_contract(wrong_path, matlab)
            with self.assertRaisesRegex(InvalidInputError, "filename"):
                store.load(BackendAdoptionTarget.LUMERICAL)

    def test_store_paths_are_confined_to_project_allowed_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            project = base / "project"
            allowed = base / "allowed"
            project.mkdir()
            allowed.mkdir()
            with self.assertRaisesRegex(
                SecurityViolationError,
                "outside configured allowed roots",
            ):
                BackendAdoptionStore(project, allowed_roots=[allowed])

    def test_store_rejects_an_explicit_empty_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            with self.assertRaisesRegex(InvalidInputError, "allowed root"):
                BackendAdoptionStore(project, allowed_roots=[])

    def test_store_rejects_relocated_adoption_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            verification = project / "verification"
            relocated = project / "relocated-adoption"
            verification.mkdir()
            relocated.mkdir()
            link = verification / "adoption"
            try:
                link.symlink_to(relocated, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")
            with self.assertRaisesRegex(
                SecurityViolationError,
                "symlink or junction",
            ):
                BackendAdoptionStore(project, allowed_roots=[project])

    def test_store_revalidates_evidence_before_loading_or_evaluating_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            store = BackendAdoptionStore(project, allowed_roots=[project])
            target = BackendAdoptionTarget.MATLAB_COMSOL_LIVELINK
            gate = store.initialize(target, source="unit test")
            evidence = project / "verification" / "backend-probe.json"
            evidence.write_text("{}\n", encoding="utf-8")
            for check in gate.required_checks:
                gate = store.record(
                    target,
                    check,
                    GateStatus.PASS,
                    evidence=["verification/backend-probe.json"],
                    reason="bounded fixture passed",
                )
            evaluated = store.evaluate(target)
            self.assertEqual(evaluated.status, GateStatus.PASS)

            evidence.unlink()
            for operation in (store.load, store.evaluate):
                with self.subTest(operation=operation.__name__), self.assertRaisesRegex(
                    InvalidInputError,
                    "missing or unreadable",
                ):
                    operation(target)


if __name__ == "__main__":
    unittest.main()
