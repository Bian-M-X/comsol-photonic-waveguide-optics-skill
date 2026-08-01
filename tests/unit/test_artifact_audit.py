from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from photonic_workflow.audit import audit_project_artifacts


class ArtifactAuditTests(unittest.TestCase):
    def test_sensitive_content_after_first_mib_is_detected_and_binary_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tail-secret.txt").write_text(
                ("safe-prefix\n" * 100000) + ("API_" + "KEY=tail-fixture-value\n"),
                encoding="utf-8",
            )
            (root / "binaryblob").write_bytes(bytes([0, 84, 79, 75, 69, 78, 61, 120]))
            result = audit_project_artifacts(root)
            paths = [finding["path"] for finding in result["findings"]]
            self.assertIn("tail-secret.txt", paths)
            self.assertNotIn("binaryblob", paths)

    def test_license_suffix_detection_does_not_match_python_attributes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.py").write_text(
                "record." + "license_verified = False\n",
                encoding="utf-8",
            )
            (root / "configuration.txt").write_text(
                "MODEL_FILE=device" + "." + "lic\n",
                encoding="utf-8",
            )
            result = audit_project_artifacts(root)
            license_paths = {
                finding["path"]
                for finding in result["findings"]
                if finding["kind"] == "possible_sensitive_content:license_file"
            }
            self.assertEqual(license_paths, {"configuration.txt"})


if __name__ == "__main__":
    unittest.main()
