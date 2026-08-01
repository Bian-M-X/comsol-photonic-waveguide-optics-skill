from __future__ import annotations

import copy
import unittest

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.recipes.catalog import recipe_definitions
from photonic_workflow.recipes.provenance import (
    load_recipe_provenance,
    provenance_for,
    validate_recipe_provenance,
)


class RecipeProvenanceTests(unittest.TestCase):
    def test_packaged_manifest_exactly_matches_static_catalog(self) -> None:
        manifest = load_recipe_provenance()
        manifest_ids = {
            (item["recipe_id"], item["recipe_version"])
            for item in manifest["recipes"]
        }
        catalog_ids = {
            (item.descriptor.recipe_id, item.descriptor.recipe_version)
            for item in recipe_definitions()
        }
        self.assertEqual(manifest_ids, catalog_ids)
        self.assertEqual(len(manifest_ids), 6)
        self.assertEqual(
            provenance_for("geometry.symmetric-euler-bend")["distillation"],
            {
                "method": "behavioral-reimplementation",
                "copied_vendor_code": False,
            },
        )

    def test_manifest_contains_no_absolute_or_windows_paths(self) -> None:
        manifest = load_recipe_provenance()
        for recipe in manifest["recipes"]:
            for origin in recipe["origins"]:
                for item in [*origin["source_files"], *origin["evidence_files"]]:
                    self.assertNotIn("\\", item["path"])
                    self.assertNotIn(":", item["path"])
                    self.assertFalse(item["path"].startswith("/"))

    def test_absolute_path_unknown_recipe_and_vendor_copy_fail_closed(self) -> None:
        manifest = load_recipe_provenance()

        absolute = copy.deepcopy(manifest)
        absolute["recipes"][0]["origins"][0]["source_files"][0]["path"] = (
            "D:/private/model.java"
        )
        with self.assertRaisesRegex(InvalidInputError, "relative POSIX path"):
            validate_recipe_provenance(absolute)

        unknown = copy.deepcopy(manifest)
        unknown["recipes"][0]["recipe_id"] = "geometry.unreviewed"
        with self.assertRaisesRegex(InvalidInputError, "catalog identities differ"):
            validate_recipe_provenance(unknown)

        copied = copy.deepcopy(manifest)
        copied["recipes"][0]["distillation"]["copied_vendor_code"] = True
        with self.assertRaisesRegex(InvalidInputError, "must not include copied"):
            validate_recipe_provenance(copied)

        invalid_alias = copy.deepcopy(manifest)
        invalid_alias["recipes"][0]["origins"][0]["project_alias"] = ["private"]
        with self.assertRaisesRegex(InvalidInputError, "nonblank string"):
            validate_recipe_provenance(invalid_alias)


if __name__ == "__main__":
    unittest.main()
