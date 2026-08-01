from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from photonic_workflow._version import compatible_minor_requirement
from photonic_workflow.circuits import validate_manifest
from photonic_workflow.config import load_project_config
from photonic_workflow.exceptions import IncompatibleVersionError
from photonic_workflow.models import WorkflowProfile
from photonic_workflow.project import create_project_scaffold


class ProjectScaffoldTests(unittest.TestCase):
    def test_dry_run_has_no_filesystem_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "dry-run-project"
            plan = create_project_scaffold(
                root,
                profile=WorkflowProfile.PDK_FIRST,
                device_family="mzi",
                dry_run=True,
            )
            self.assertTrue(plan["dry_run"])
            self.assertFalse(root.exists())

    def test_scaffold_is_loadable_and_mzi_fixture_composes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "fixture-project"
            result = create_project_scaffold(
                root,
                profile=WorkflowProfile.CUSTOM_DEVICE_FIRST,
                device_family="mzi",
            )
            self.assertEqual(result["template_kind"], "mzi-4port")
            _, config = load_project_config(root)
            self.assertEqual(config.profile, WorkflowProfile.CUSTOM_DEVICE_FIRST)
            self.assertEqual(
                (root / "requirements.txt").read_text(encoding="utf-8"),
                compatible_minor_requirement() + "\n",
            )
            manifest, data = validate_manifest(root / "circuits" / "assembly.json")
            self.assertEqual(len(manifest["instances"]), 4)
            self.assertEqual(len(data), 2)

            config_path = root / "photonic.toml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8").replace(
                    'schema_version = "1.0"',
                    'schema_version = "2.0"',
                ),
                encoding="utf-8",
            )
            with self.assertRaises(IncompatibleVersionError):
                load_project_config(root)


if __name__ == "__main__":
    unittest.main()
