from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from photonic_workflow.cli import main


def invoke(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(arguments)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def circular_request() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "recipe_id": "geometry.circular-route",
        "recipe_version": "1.0.0",
        "parameters": {
            "vertices_um": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0]],
            "radius_um": 2.0,
            "width_um": 0.5,
        },
    }


class RecipeCliTests(unittest.TestCase):
    def test_list_inspect_and_canonical_render_are_fail_closed(self) -> None:
        list_exit, list_output, list_error = invoke(["recipe", "list", "--json"])
        self.assertEqual((list_exit, list_error), (0, ""))
        recipes = json.loads(list_output)["data"]["recipes"]
        self.assertEqual(len(recipes), 6)
        self.assertTrue(all(item["physics_accepted"] is False for item in recipes))

        inspect_exit, inspect_output, inspect_error = invoke(
            ["recipe", "inspect", "geometry.circular-route", "--json"]
        )
        self.assertEqual((inspect_exit, inspect_error), (0, ""))
        inspected = json.loads(inspect_output)["data"]
        self.assertEqual(inspected["recipe_version"], "1.0.0")
        first_parameter = inspected["parameter_contract"][0]
        self.assertEqual(first_parameter["name"], "vertices_um")
        self.assertEqual(first_parameter["json_type"], "array")
        self.assertEqual(first_parameter["unit"], "um")
        self.assertTrue(first_parameter["required"])
        self.assertEqual(
            inspected["provenance"]["recipe_id"],
            "geometry.circular-route",
        )
        self.assertTrue(inspected["provenance"]["origins"])
        self.assertTrue(
            all(
                ":" not in item["path"] and "\\" not in item["path"]
                for origin in inspected["provenance"]["origins"]
                for collection in ("source_files", "evidence_files")
                for item in origin[collection]
            )
        )
        self.assertFalse(inspected["will_execute"])

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            init_exit, _, init_error = invoke(["init", str(project), "--json"])
            self.assertEqual((init_exit, init_error), (0, ""))
            request = project / "route-request.json"
            request.write_text(json.dumps(circular_request()), encoding="utf-8")
            output = project / "generated" / "route.json"

            dry_exit, dry_output, dry_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--output",
                    "generated/route.json",
                    "--project-root",
                    str(project),
                    "--dry-run",
                    "--json",
                ]
            )
            self.assertEqual((dry_exit, dry_error), (0, ""))
            dry_data = json.loads(dry_output)["data"]
            self.assertFalse(dry_data["written"])
            self.assertEqual(dry_data["artifact_path"], "generated/route.json")
            self.assertGreater(dry_data["output"]["centerline_length_um"], 0.0)
            self.assertFalse(dry_data["will_execute"])
            self.assertFalse(dry_data["physics_accepted"])
            self.assertFalse(output.exists())

            java_exit, java_output, java_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--renderer",
                    "comsol-java-fragment",
                    "--instance-id",
                    "route-main",
                    "--json",
                ]
            )
            self.assertEqual((java_exit, java_error), (0, ""))
            java_data = json.loads(java_output)["data"]
            self.assertEqual(java_data["renderer_id"], "comsol-java-fragment")
            self.assertEqual(java_data["instance_id"], "route-main")
            prefix_match = re.search(
                r'g\.create\("(recipe_route_main_[0-9a-f]{10})_circular_outer_0"',
                java_data["content"],
            )
            self.assertIsNotNone(prefix_match)
            created_tags = re.findall(r'g\.create\("([A-Za-z0-9_]+)"', java_data["content"])
            self.assertTrue(
                all(tag.startswith(prefix_match.group(1)) for tag in created_tags)
            )
            self.assertGreater(java_data["output"]["centerline_length_um"], 0.0)
            self.assertIsNone(java_data["artifact_path"])
            self.assertFalse(java_data["will_execute"])

            outside_exit, outside_output, outside_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--output",
                    "../escape.json",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual(outside_error, "")
            self.assertEqual(outside_exit, 7)
            self.assertIn("outside configured allowed roots", json.loads(outside_output)["errors"][0])
            self.assertFalse((project.parent / "escape.json").exists())

            write_exit, write_output, write_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--output",
                    "generated/route.json",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual((write_exit, write_error), (0, ""))
            written = json.loads(write_output)["data"]
            self.assertTrue(written["written"])
            self.assertEqual(written["artifact_path"], "generated/route.json")
            self.assertGreater(written["output"]["centerline_length_um"], 0.0)
            self.assertTrue(output.is_file())
            self.assertEqual(
                written["sha256"],
                hashlib.sha256(output.read_bytes()).hexdigest(),
            )

            overwrite_exit, overwrite_output, overwrite_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--output",
                    "generated/route.json",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual(overwrite_error, "")
            self.assertEqual(overwrite_exit, 2)
            self.assertIn("already exists", json.loads(overwrite_output)["errors"][0])

    def test_render_rejects_version_id_and_output_policy_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request = root / "request.json"
            payload = circular_request()
            payload["recipe_version"] = "2.0.0"
            request.write_text(json.dumps(payload), encoding="utf-8")
            version_exit, version_output, version_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--json",
                ]
            )
            self.assertEqual(version_error, "")
            self.assertEqual(version_exit, 4)
            self.assertIn("available version", json.loads(version_output)["errors"][0])

            payload = circular_request()
            request.write_text(json.dumps(payload), encoding="utf-8")
            policy_exit, policy_output, policy_error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--output",
                    "route.json",
                    "--json",
                ]
            )
            self.assertEqual(policy_error, "")
            self.assertEqual(policy_exit, 2)
            self.assertIn("requires --project-root", json.loads(policy_output)["errors"][0])

    def test_render_rejects_symlinked_output_ancestors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            init_exit, _, init_error = invoke(["init", str(project), "--json"])
            self.assertEqual((init_exit, init_error), (0, ""))
            request = project / "request.json"
            request.write_text(json.dumps(circular_request()), encoding="utf-8")
            actual = project / "actual"
            actual.mkdir()
            link = project / "linked"
            try:
                link.symlink_to(actual, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink is unavailable: {exc}")

            exit_code, output, error = invoke(
                [
                    "recipe",
                    "render",
                    "geometry.circular-route",
                    "--input",
                    str(request),
                    "--output",
                    "linked/route.json",
                    "--project-root",
                    str(project),
                    "--json",
                ]
            )
            self.assertEqual(error, "")
            self.assertEqual(exit_code, 7)
            self.assertIn("symlink or junction", json.loads(output)["errors"][0])
            self.assertFalse((actual / "route.json").exists())


if __name__ == "__main__":
    unittest.main()
