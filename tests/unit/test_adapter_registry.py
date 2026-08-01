from __future__ import annotations

import unittest
from types import SimpleNamespace

import photonic_workflow.adapters as public_adapters
from photonic_workflow.adapters import (
    AdapterRegistration,
    AdapterRegistry,
    registry_for_project,
    validate_adapter_provider_contract,
)
from photonic_workflow.compatibility import ADAPTER_ENTRY_POINT_GROUP
from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.models import (
    AdapterDescriptor,
    ImplementationStatus,
    ProjectConfig,
    current_contract_schema_versions,
)


def descriptor(name: str) -> AdapterDescriptor:
    return AdapterDescriptor(
        stable_id=f"adapter:{name}",
        name=f"{name} adapter",
        source="adapter registry unit test",
        adapter=name,
    )


class FakeEntryPoint:
    def __init__(
        self,
        name: str,
        provider: object,
        *,
        value: str | None = None,
    ) -> None:
        self.name = name
        self._provider = provider
        self.value = value
        self.dist = SimpleNamespace(name="test-provider", version="0.1.0")

    def load(self) -> object:
        return self._provider


class AdapterRegistryTests(unittest.TestCase):
    def test_public_adapter_exports_include_provider_contract(self) -> None:
        for name in (
            "AdapterRegistration",
            "LoadedAdapterProvider",
            "registry_for_project",
            "validate_adapter_provider_contract",
        ):
            self.assertIn(name, public_adapters.__all__)

    def test_registration_is_descriptor_first_and_duplicate_safe(self) -> None:
        registry = AdapterRegistry()
        registration = AdapterRegistration(descriptor("example"))
        registry.register(registration)
        self.assertEqual(registry.descriptor("example").adapter, "example")
        self.assertFalse(registry.has_factory("example"))
        with self.assertRaisesRegex(InvalidInputError, "already registered"):
            registry.register(registration)
        with self.assertRaisesRegex(InvalidInputError, "SPI"):
            AdapterRegistry().register(
                AdapterRegistration(
                    descriptor("future"),
                    spi_version="2.0",
                )
            )
        future_descriptor = AdapterDescriptor(
            stable_id="adapter:future-contract",
            name="future contract adapter",
            source="adapter registry unit test",
            adapter="future-contract",
            input_contracts=["RunSpec"],
            contract_schema_versions={"RunSpec": "2.0"},
        )
        with self.assertRaisesRegex(InvalidInputError, "contract schema"):
            AdapterRegistry().register(
                AdapterRegistration(future_descriptor)
            )

        atomic_registry = AdapterRegistry()
        with self.assertRaisesRegex(InvalidInputError, "already registered"):
            atomic_registry.register_many(
                (
                    AdapterRegistration(descriptor("duplicate")),
                    AdapterRegistration(descriptor("duplicate")),
                )
            )
        with self.assertRaisesRegex(InvalidInputError, "unknown adapter"):
            atomic_registry.descriptor("duplicate")

    def test_entrypoint_loading_is_explicit_allowlisted_and_deterministic(self) -> None:
        calls: list[str] = []

        def reader(*, group: str) -> list[FakeEntryPoint]:
            calls.append(group)
            return [
                FakeEntryPoint(
                    "ignored",
                    lambda: (AdapterRegistration(descriptor("ignored")),),
                ),
                FakeEntryPoint(
                    "approved",
                    lambda: (AdapterRegistration(descriptor("approved-adapter")),),
                    value="approved_provider:provide_adapters",
                ),
            ]

        registry = AdapterRegistry()
        self.assertEqual(
            registry.load_entrypoint_adapters(
                ["approved"],
                entry_points_reader=reader,
            ),
            ("approved",),
        )
        self.assertEqual(calls, [ADAPTER_ENTRY_POINT_GROUP])
        self.assertEqual(
            registry.descriptor("approved-adapter").adapter,
            "approved-adapter",
        )
        self.assertEqual(
            registry.loaded_providers()[0].as_dict(),
            {
                "name": "approved",
                "target": "approved_provider:provide_adapters",
                "distribution": "test-provider",
                "distribution_version": "0.1.0",
            },
        )
        with self.assertRaisesRegex(InvalidInputError, "were not found"):
            registry.load_entrypoint_adapters(
                ["missing"],
                entry_points_reader=reader,
            )

    def test_empty_allowlist_never_discovers_or_imports_plugins(self) -> None:
        def forbidden_reader(**_: object) -> object:
            raise AssertionError("entry-point discovery must not run")

        registry = AdapterRegistry()
        self.assertEqual(
            registry.load_entrypoint_adapters(
                [],
                entry_points_reader=forbidden_reader,
            ),
            (),
        )

    def test_invalid_provider_shape_and_factory_result_fail_closed(self) -> None:
        registry = AdapterRegistry()
        with self.assertRaisesRegex(InvalidInputError, "must return a tuple"):
            registry.load_entrypoint_adapters(
                ["bad"],
                entry_points_reader=lambda **_: [
                    FakeEntryPoint("bad", lambda: ["not-a-registration"])
                ],
            )
        with self.assertRaisesRegex(InvalidInputError, "descriptor-only"):
            registry.load_entrypoint_adapters(
                ["bad-factory-provider"],
                entry_points_reader=lambda **_: [
                    FakeEntryPoint(
                        "bad-factory-provider",
                        lambda: (
                            AdapterRegistration(
                                descriptor("external-factory"),
                                factory=lambda: object(),  # type: ignore[return-value]
                            ),
                        ),
                    )
                ],
            )

        registry.register(
            AdapterRegistration(
                descriptor("bad-factory"),
                factory=lambda: object(),  # type: ignore[return-value]
            )
        )
        with self.assertRaisesRegex(InvalidInputError, "did not return an Adapter"):
            registry.create("bad-factory")

    def test_project_registry_requires_config_and_explicit_load_switch(self) -> None:
        config = ProjectConfig(
            stable_id="project",
            name="project",
            source="test",
            adapter_entrypoint_allowlist=["approved"],
        )
        calls: list[str] = []

        def reader(*, group: str) -> list[FakeEntryPoint]:
            calls.append(group)
            return [
                FakeEntryPoint(
                    "approved",
                    lambda: (AdapterRegistration(descriptor("project-adapter")),),
                )
            ]

        safe_registry = registry_for_project(
            config,
            load_entry_points=False,
            entry_points_reader=reader,
        )
        self.assertEqual(calls, [])
        self.assertEqual(safe_registry.loaded_entry_points(), ())

        loaded_registry = registry_for_project(
            config,
            load_entry_points=True,
            entry_points_reader=reader,
        )
        self.assertEqual(calls, [ADAPTER_ENTRY_POINT_GROUP])
        self.assertEqual(loaded_registry.loaded_entry_points(), ("approved",))
        self.assertEqual(
            loaded_registry.descriptor("project-adapter").adapter,
            "project-adapter",
        )

    def test_descriptor_only_provider_contract_is_reusable_and_atomic(self) -> None:
        provider_descriptor = AdapterDescriptor(
            stable_id="adapter:provider-example",
            name="Provider example",
            source="third-party provider contract test",
            adapter="provider-example",
            adapter_spi_version="1.0",
            implementation=ImplementationStatus.PLANNED,
            execution_modes=["descriptor"],
            input_contracts=["RunSpec"],
            output_contracts=["CapabilityReport"],
            contract_schema_versions=current_contract_schema_versions(
                ["RunSpec", "CapabilityReport"]
            ),
            default_dry_run=True,
            default_concurrency=1,
        )

        def provider() -> tuple[AdapterRegistration, ...]:
            return (
                AdapterRegistration(
                    descriptor=provider_descriptor.model_copy(deep=True),
                    factory=None,
                    spi_version="1.0",
                ),
            )

        validated = validate_adapter_provider_contract(
            provider,
            provider_name="reviewed-example",
        )
        self.assertEqual(validated[0].descriptor.adapter, "provider-example")

        registry = AdapterRegistry()
        with self.assertRaisesRegex(InvalidInputError, "invalid registration"):
            registry.load_entrypoint_adapters(
                ["first", "second"],
                entry_points_reader=lambda **_: [
                    FakeEntryPoint("first", provider),
                    FakeEntryPoint("second", lambda: ("invalid",)),
                ],
            )
        with self.assertRaisesRegex(InvalidInputError, "unknown adapter"):
            registry.descriptor("provider-example")


if __name__ == "__main__":
    unittest.main()
