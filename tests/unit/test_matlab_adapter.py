from __future__ import annotations

import copy
import json
import tempfile
import unittest
from importlib.machinery import ModuleSpec
from pathlib import Path

from pydantic import ValidationError

from photonic_workflow.adapters import default_adapter_registry
from photonic_workflow.adapters.matlab.descriptors import (
    MATLAB_ADAPTER_DESCRIPTORS,
)
from photonic_workflow.adapters.matlab.engine import (
    EngineProbeResult,
    probe_matlab_engine,
)
from photonic_workflow.adapters.matlab.inventory import parse_product_inventory
from photonic_workflow.adapters.matlab.results import (
    load_matlab_result,
    parse_matlab_result,
)
from photonic_workflow.adapters.matlab.runtime import (
    WRAPPER_NAME,
    MatlabRuntimeAdapter,
    _default_matlab_entry_root,
)
from photonic_workflow.exceptions import (
    IncompatibleVersionError,
    InvalidInputError,
    SecurityViolationError,
    UnavailableCapabilityError,
)
from photonic_workflow.models.contracts import (
    AvailabilityStatus,
    ImplementationStatus,
    MatlabRunSpec,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures"


def unavailable_engine(_: str | None) -> EngineProbeResult:
    return EngineProbeResult(
        importable=False,
        distribution_version=None,
        compatible=False,
        shared_session_count=None,
        reasons=("mock Engine unavailable",),
    )


def make_run_spec(**updates: object) -> MatlabRunSpec:
    payload: dict[str, object] = {
        "stable_id": "matlab-run:unit",
        "name": "MATLAB unit dry-run",
        "source": "unit test",
        "operation": "environment.validate",
        "run_spec_path": "runs/unit/inputs.json",
        "result_path": "runs/unit/result.json",
        "runtime_directory": "runs/unit/runtime",
        "matlab_paths": ["toolboxes/approved"],
        "expected_artifacts": ["runs/unit/environment.json"],
        "toolbox_requirements": ["MATLAB"],
    }
    payload.update(updates)
    return MatlabRunSpec.model_validate(payload)


class MatlabRuntimeAdapterTests(unittest.TestCase):
    def test_packaged_matlab_entry_files_match_source_mirror(self) -> None:
        packaged = _default_matlab_entry_root()
        source = Path(__file__).resolve().parents[2] / "matlab"
        self.assertNotEqual(packaged.resolve(), source.resolve())
        packaged_files = {
            path.relative_to(packaged)
            for path in packaged.rglob("*.m")
            if path.is_file()
        }
        source_files = {
            path.relative_to(source)
            for path in source.rglob("*.m")
            if path.is_file()
        }
        self.assertEqual(packaged_files, source_files)
        relative_files = sorted(source_files)
        for relative in relative_files:
            self.assertEqual(
                (packaged / relative).read_text(encoding="utf-8"),
                (source / relative).read_text(encoding="utf-8"),
                str(relative),
            )

    def test_check_without_matlab_is_structured_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            adapter = MatlabRuntimeAdapter(
                project_root=root,
                executable_resolver=lambda _: None,
                engine_probe=unavailable_engine,
            )

            report = adapter.check()

        self.assertEqual(report.availability, AvailabilityStatus.UNAVAILABLE)
        self.assertFalse(report.batch_capable)
        self.assertFalse(report.engine_importable)
        self.assertEqual(report.status, "unavailable")
        self.assertIn("not resolved", " ".join(report.provenance))

    def test_check_parses_products_without_exposing_installation_root(self) -> None:
        private_root = "C:" + r"\Users\private\Commercial\MATLAB"
        private_executable = private_root + r"\bin\matlab.exe"
        inventory = {
            "source": "mock inventory",
            "availability": "available",
            "root": private_root,
            "release": "R2025b",
            "version": "25.2",
            "platform": "PCWIN64",
            "architecture": "win64",
            "batch_capable": True,
            "complete_product_inventory": True,
            "products": [
                {"product_name": "MATLAB", "version": "25.2", "installed": True},
                {"product_name": "Simulink", "version": "25.2", "installed": True},
                {
                    "product_name": "Instrument Control Toolbox",
                    "version": "25.2",
                    "installed": True,
                },
            ],
            "comsol_livelink": "unverified",
            "lumerical_api": "unavailable",
        }
        engine = EngineProbeResult(
            importable=True,
            distribution_version="25.2.0",
            compatible=None,
            shared_session_count=None,
            reasons=("mock compatibility unverified",),
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            adapter = MatlabRuntimeAdapter(
                project_root=root,
                inventory=inventory,
                executable_resolver=lambda _: private_executable,
                engine_probe=lambda _: engine,
            )
            report = adapter.check()

        encoded = report.model_dump_json()
        self.assertEqual(report.availability, AvailabilityStatus.AVAILABLE)
        self.assertEqual(report.root_alias, "<matlab-root>")
        self.assertEqual(report.simulink, AvailabilityStatus.AVAILABLE)
        self.assertEqual(report.instrument_control, AvailabilityStatus.AVAILABLE)
        self.assertNotIn("C:" + r"\Users\private", encoded)
        self.assertIsNone(report.engine_compatible)

    def test_plan_is_fixed_shell_free_and_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "toolboxes" / "approved").mkdir(parents=True)
            adapter = MatlabRuntimeAdapter(
                project_root=root,
                executable_resolver=lambda _: None,
                engine_probe=unavailable_engine,
            )

            plan = adapter.plan(make_run_spec())
            public = plan.public_payload()
            generated = {item.path.name: item.content for item in plan.generated_files}

        self.assertTrue(plan.dry_run)
        self.assertFalse(plan.shell)
        self.assertFalse(plan.execution_verified)
        self.assertEqual(plan.command[-2:], ("-batch", WRAPPER_NAME))
        self.assertEqual(plan.command[0], "matlab")
        self.assertIn("photonic_batch_wrapper.m", generated)
        self.assertIn('"contract_type": "MatlabRunSpec"', generated["inputs.json"])
        wrapper = generated["photonic_batch_wrapper.m"].casefold()
        for forbidden in ("eval(", "evalin(", "feval(", "system("):
            self.assertNotIn(forbidden, wrapper)
        self.assertNotIn(str(root), json.dumps(public))
        self.assertEqual(public["environment"]["PHOTONIC_RUN_SPEC"], "<redacted>")

    def test_plan_rejects_statement_injection_and_real_execution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "toolboxes" / "approved").mkdir(parents=True)
            adapter = MatlabRuntimeAdapter(
                project_root=root,
                executable_resolver=lambda _: None,
                engine_probe=unavailable_engine,
            )
            with self.assertRaises(ValidationError):
                make_run_spec(entrypoint_id="photonic.environment.validate.v1;system")
            with self.assertRaises(UnavailableCapabilityError):
                adapter.plan(make_run_spec(dry_run=False))
            with self.assertRaises(UnavailableCapabilityError):
                adapter.plan(make_run_spec(operation="layout.build"))

    def test_plan_rejects_path_traversal_and_startup_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "toolboxes" / "approved").mkdir(parents=True)
            (root / "startup.m").write_text("% unsafe implicit hook fixture\n", encoding="utf-8")
            adapter = MatlabRuntimeAdapter(
                project_root=root,
                executable_resolver=lambda _: None,
                engine_probe=unavailable_engine,
            )
            with self.assertRaises(SecurityViolationError):
                adapter.plan(make_run_spec(result_path="../outside.json"))
            with self.assertRaises(SecurityViolationError):
                adapter.plan(make_run_spec(matlab_paths=["startup.m"]))

    def test_executable_alias_cannot_be_a_shell_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as raw, self.assertRaises(InvalidInputError):
            MatlabRuntimeAdapter(
                project_root=Path(raw),
                executable_alias="matlab;calc",
            )


class MatlabInventoryAndEngineTests(unittest.TestCase):
    def test_product_inventory_derives_optional_product_availability(self) -> None:
        inventory = parse_product_inventory(
            {
                "availability": "available",
                "batch_capable": True,
                "complete_product_inventory": True,
                "products": [
                    {"product_name": "MATLAB", "installed": True},
                    {"product_name": "Simulink", "installed": False},
                ],
            }
        )
        self.assertEqual(inventory.simulink, AvailabilityStatus.UNAVAILABLE)
        self.assertEqual(
            inventory.instrument_control,
            AvailabilityStatus.UNAVAILABLE,
        )
        self.assertFalse(inventory.products[1].license_verified)

    def test_engine_probe_only_enumerates_when_explicitly_requested(self) -> None:
        calls: list[str] = []

        def finder(name: str) -> ModuleSpec | None:
            calls.append(name)
            return ModuleSpec(name, loader=None)

        result = probe_matlab_engine(
            matlab_release="R2025b",
            inspect_shared_sessions=True,
            spec_finder=finder,
            version_getter=lambda _: "25.2.0",
            session_finder=lambda: ("session-a", "session-b"),
        )
        self.assertTrue(result.importable)
        self.assertIsNone(result.compatible)
        self.assertEqual(result.shared_session_count, 2)
        self.assertEqual(calls, ["matlab", "matlab.engine"])


class MatlabResultAndDescriptorTests(unittest.TestCase):
    def test_mock_result_parser_preserves_execution_only_semantics(self) -> None:
        result = load_matlab_result(
            FIXTURE_ROOT / "mock_matlab_result.json",
            expected_run_id="mock-run",
        )
        self.assertEqual(result.execution_status.value, "succeeded")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.validity.value, "unknown")
        self.assertIn("not physical evidence", result.artifacts[0].provenance)

    def test_result_parser_rejects_contradiction_and_traversal(self) -> None:
        payload = json.loads(
            (FIXTURE_ROOT / "mock_matlab_result.json").read_text(encoding="utf-8")
        )
        contradictory = copy.deepcopy(payload)
        contradictory["exit_code"] = 9
        with self.assertRaises(InvalidInputError):
            parse_matlab_result(contradictory)

        traversal = copy.deepcopy(payload)
        traversal["artifacts"][0]["relative_path"] = "../secret.txt"
        with self.assertRaises(InvalidInputError):
            parse_matlab_result(traversal)

        future = copy.deepcopy(payload)
        future["schema_version"] = "2.0"
        with self.assertRaises(IncompatibleVersionError):
            parse_matlab_result(future)

    def test_descriptors_and_registry_do_not_invent_runtime_factories(self) -> None:
        descriptors = {item.adapter: item for item in MATLAB_ADAPTER_DESCRIPTORS}
        self.assertEqual(
            set(descriptors),
            {
                "matlab-runtime",
                "matlab-engine",
                "matlab-layout",
                "matlab-fdfd",
                "matlab-comsol-livelink",
                "matlab-lumerical",
                "matlab-instrument",
                "matlab-simulink",
            },
        )
        self.assertEqual(
            descriptors["matlab-runtime"].implementation,
            ImplementationStatus.IMPLEMENTED,
        )
        self.assertEqual(
            descriptors["matlab-simulink"].implementation,
            ImplementationStatus.PLANNED,
        )
        self.assertIn(
            "no Phase-A execution or result parity evidence",
            descriptors["matlab-lumerical"].limitations,
        )

        registry = default_adapter_registry()
        for adapter_name in (
            "comsol-native-java-batch",
            "sim-cli",
            "lumerical",
            "gdsfactory",
            "klayout",
            "sax",
            "meep",
            "femwell",
            "tidy3d",
        ):
            self.assertEqual(registry.descriptor(adapter_name).adapter, adapter_name)
        self.assertTrue(registry.has_factory("matlab-runtime"))
        self.assertTrue(registry.has_factory("matlab-engine"))
        self.assertFalse(registry.has_factory("matlab-layout"))
        with self.assertRaises(InvalidInputError):
            registry.create("matlab-layout")


if __name__ == "__main__":
    unittest.main()
