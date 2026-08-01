from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

import photonic_workflow.models as public_models
from photonic_workflow.exceptions import IncompatibleVersionError, InvalidInputError
from photonic_workflow.models import (
    CONTRACT_MIGRATIONS,
    MODEL_CLASSES,
    MODEL_REGISTRY,
    AcceptanceStatus,
    DesignIntent,
    ExecutionStatus,
    GateName,
    GateRecord,
    GateStatus,
    MatlabRunSpec,
    ProjectConfig,
    ProjectIdentity,
    RunManifest,
    RunStatus,
    validate_contract_model_versions,
)
from photonic_workflow.models.io import (
    contract_json,
    load_contract,
    parse_contract,
    write_contract,
)
from photonic_workflow.models.versioning import (
    ContractMigration,
    ContractMigrationRegistry,
)


class ContractRoundTripTests(unittest.TestCase):
    def test_every_registered_contract_round_trips_with_common_metadata(self) -> None:
        self.assertGreaterEqual(len(MODEL_REGISTRY), 45)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for model_class in MODEL_CLASSES:
                with self.subTest(contract_type=model_class.contract_type):
                    stable_id = {
                        "BackendAdoptionCheckRecord": (
                            "adoption-check:matlab-runtime:capability-probe"
                        ),
                        "BackendAdoptionGateRecord": "adoption:matlab-runtime",
                    }.get(
                        model_class.contract_type,
                        f"fixture:{model_class.contract_type}",
                    )
                    model = model_class(
                        stable_id=stable_id,
                        name=f"{model_class.contract_type} fixture",
                        source="contract unit test",
                    )
                    path = root / f"{model_class.contract_type}.json"
                    write_contract(path, model)
                    restored = load_contract(path, model_class.contract_type)
                    self.assertEqual(type(restored), model_class)
                    self.assertEqual(restored.stable_id, model.stable_id)
                    self.assertEqual(
                        restored.schema_version,
                        model_class.current_schema_version,
                    )
                    self.assertEqual(
                        model_class.model_fields["schema_version"].default,
                        model_class.current_schema_version,
                    )

    def test_contract_types_can_advance_versions_independently(self) -> None:
        class ProjectIdentityV11(ProjectIdentity):
            contract_type = "ProjectIdentityV11"
            current_schema_version = "1.1"
            schema_version: str = "1.1"

        validate_contract_model_versions((ProjectIdentityV11,))
        self.assertEqual(
            ProjectIdentityV11(
                stable_id="project",
                name="project",
                source="test",
            ).schema_version,
            "1.1",
        )

        class BrokenProjectIdentityV11(ProjectIdentity):
            contract_type = "BrokenProjectIdentityV11"
            current_schema_version = "1.1"

        with self.assertRaisesRegex(RuntimeError, "override both"):
            validate_contract_model_versions((BrokenProjectIdentityV11,))

    def test_extra_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectIdentity(
                stable_id="project",
                name="project",
                source="test",
                unexpected=True,
            )

        with self.assertRaisesRegex(ValidationError, "contains duplicates"):
            ProjectConfig(
                stable_id="project",
                name="project",
                source="test",
                adapter_entrypoint_allowlist=["same", "same"],
            )
        with self.assertRaisesRegex(ValidationError, "invalid adapter entry-point"):
            ProjectConfig(
                stable_id="project",
                name="project",
                source="test",
                adapter_entrypoint_allowlist=["unsafe;provider"],
            )

    def test_public_model_exports_are_bounded_and_complete(self) -> None:
        for model_class in MODEL_CLASSES:
            self.assertIn(model_class.__name__, public_models.__all__)
            self.assertIs(getattr(public_models, model_class.__name__), model_class)
        self.assertNotIn("BaseModel", public_models.__all__)
        self.assertFalse(hasattr(public_models, "BaseModel"))

    def test_external_contracts_require_a_supported_schema_version(self) -> None:
        base = {
            "contract_type": "ProjectIdentity",
            "stable_id": "project",
            "name": "project",
            "source": "test",
        }
        with self.assertRaisesRegex(InvalidInputError, "must declare schema_version"):
            parse_contract(base)
        for version in ("0.9", "1.1", "2.0", "99.0"):
            with self.subTest(version=version), self.assertRaises(IncompatibleVersionError):
                parse_contract({**base, "schema_version": version})

        parsed = parse_contract({**base, "schema_version": "1.0"})
        self.assertIsInstance(parsed, ProjectIdentity)

    def test_contract_migrations_are_explicit_pure_and_auditable(self) -> None:
        registry = ContractMigrationRegistry()

        def migrate_legacy(payload: dict[str, object]) -> dict[str, object]:
            migrated = dict(payload)
            migrated["name"] = migrated.pop("legacy_name")
            return migrated

        registry.register(
            ContractMigration(
                migration_id="ProjectIdentity-0.9-to-1.0",
                contract_type="ProjectIdentity",
                from_version="0.9",
                to_version="1.0",
                transform=migrate_legacy,
            )
        )
        original = {
            "contract_type": "ProjectIdentity",
            "schema_version": "0.9",
            "stable_id": "project",
            "legacy_name": "project",
            "source": "test",
            "provenance": [],
        }
        result = registry.migrate(
            original,
            contract_type="ProjectIdentity",
            target_version="1.0",
        )
        self.assertEqual(original["schema_version"], "0.9")
        self.assertIn("legacy_name", original)
        self.assertEqual(result.payload["schema_version"], "1.0")
        self.assertEqual(result.payload["name"], "project")
        self.assertEqual(
            result.payload["provenance"],
            ["contract-migration:ProjectIdentity-0.9-to-1.0"],
        )
        self.assertEqual(
            result.applied_migrations,
            ("ProjectIdentity-0.9-to-1.0",),
        )
        parsed = parse_contract(original, migration_registry=registry)
        self.assertIsInstance(parsed, ProjectIdentity)
        self.assertEqual(
            parsed.provenance,
            ["contract-migration:ProjectIdentity-0.9-to-1.0"],
        )
        with self.assertRaisesRegex(InvalidInputError, "already registered"):
            registry.register(
                ContractMigration(
                    migration_id="duplicate",
                    contract_type="ProjectIdentity",
                    from_version="0.9",
                    to_version="1.0",
                    transform=migrate_legacy,
                )
            )

        atomic_registry = ContractMigrationRegistry()
        with self.assertRaisesRegex(InvalidInputError, "already registered"):
            atomic_registry.register_many(
                (
                    ContractMigration(
                        migration_id="first",
                        contract_type="ProjectIdentity",
                        from_version="0.8",
                        to_version="0.9",
                        transform=migrate_legacy,
                    ),
                    ContractMigration(
                        migration_id="second",
                        contract_type="ProjectIdentity",
                        from_version="0.8",
                        to_version="1.0",
                        transform=migrate_legacy,
                    ),
                )
            )
        self.assertEqual(atomic_registry.migrations(), ())
        self.assertTrue(CONTRACT_MIGRATIONS.frozen)
        with self.assertRaisesRegex(InvalidInputError, "frozen"):
            CONTRACT_MIGRATIONS.register(
                ContractMigration(
                    migration_id="forbidden-runtime-mutation",
                    contract_type="ProjectIdentity",
                    from_version="0.1",
                    to_version="1.0",
                    transform=migrate_legacy,
                )
            )

    def test_json_serialization_is_strict_and_rejects_nan(self) -> None:
        intent = DesignIntent(
            stable_id="intent",
            name="intent",
            source="test",
            metrics={"bad": math.nan},
        )
        with self.assertRaises(ValueError):
            contract_json(intent)

    def test_passing_gate_requires_explicit_evidence(self) -> None:
        with self.assertRaisesRegex(ValidationError, "requires explicit evidence"):
            GateRecord(
                stable_id="gate:G1",
                name="port baseline",
                source="test",
                gate=GateName.G1,
                status=GateStatus.PASS,
            )

    def test_run_manifest_derives_legacy_status_from_authoritative_fields(self) -> None:
        manifest = RunManifest(
            stable_id="run:accepted",
            name="accepted run",
            source="test",
            execution_status=ExecutionStatus.SUCCEEDED,
            acceptance_status=AcceptanceStatus.ACCEPTED,
        )
        self.assertEqual(manifest.status, RunStatus.ACCEPTED)
        self.assertEqual(manifest.model_dump(mode="json")["status"], "accepted")

    def test_run_manifest_rejects_impossible_acceptance_state(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must have succeeded execution"):
            RunManifest(
                stable_id="run:impossible",
                name="impossible run",
                source="test",
                execution_status=ExecutionStatus.FAILED,
                acceptance_status=AcceptanceStatus.ACCEPTED,
            )

    def test_matlab_run_spec_uses_only_registered_entrypoint_id(self) -> None:
        spec = MatlabRunSpec(
            stable_id="matlab-run:fixed",
            name="fixed MATLAB run",
            source="test",
        )
        self.assertEqual(
            spec.entrypoint_id,
            "photonic.environment.validate.v1",
        )
        self.assertNotIn("entry_function", spec.model_dump())
        with self.assertRaisesRegex(ValidationError, "literal_error"):
            MatlabRunSpec(
                stable_id="matlab-run:arbitrary",
                name="arbitrary MATLAB run",
                source="test",
                entrypoint_id="user.supplied.function",
            )

    def test_matlab_run_spec_migrates_only_exact_legacy_alias(self) -> None:
        compatible = MatlabRunSpec.model_validate(
            {
                "stable_id": "matlab-run:legacy",
                "name": "legacy MATLAB run",
                "source": "test",
                "entry_function": "photonic.entry",
            }
        )
        self.assertEqual(
            compatible.entrypoint_id,
            "photonic.environment.validate.v1",
        )
        self.assertNotIn("entry_function", compatible.model_dump())
        with self.assertRaisesRegex(ValidationError, "only the legacy"):
            MatlabRunSpec.model_validate(
                {
                    "stable_id": "matlab-run:unsafe-legacy",
                    "name": "unsafe legacy MATLAB run",
                    "source": "test",
                    "entry_function": "system",
                }
            )


if __name__ == "__main__":
    unittest.main()
