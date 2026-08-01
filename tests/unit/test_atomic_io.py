from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from photonic_workflow.cli import _checked_recipe_output
from photonic_workflow.exceptions import SecurityViolationError
from photonic_workflow.models.io import atomic_create_text


class AtomicCreateTextTests(unittest.TestCase):
    def test_recipe_output_rejects_windows_reparse_attribute_without_symlink_privilege(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            junction = root / "junction"
            junction.mkdir()
            original_lstat = Path.lstat

            def lstat_with_reparse(path: Path):  # type: ignore[no-untyped-def]
                actual = original_lstat(path)
                if path == junction:
                    return SimpleNamespace(
                        st_mode=actual.st_mode,
                        st_file_attributes=0x400,
                    )
                return actual

            with patch.object(Path, "lstat", lstat_with_reparse), self.assertRaisesRegex(
                SecurityViolationError,
                "symlink or junction",
            ):
                _checked_recipe_output(root, junction / "artifact.java")

    def test_guard_is_rechecked_around_temporary_write_and_final_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "nested" / "artifact.txt"
            calls: list[Path] = []

            def guard(path: Path) -> None:
                calls.append(path)
                if len(calls) == 3:
                    raise SecurityViolationError("simulated reparse substitution")

            with self.assertRaisesRegex(
                SecurityViolationError,
                "simulated reparse substitution",
            ):
                atomic_create_text(target, "controlled\n", path_guard=guard)
            self.assertEqual(len(calls), 3)
            self.assertFalse(target.exists())
            self.assertEqual(list(target.parent.glob(".*.tmp")), [])

    def test_successful_guarded_create_is_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "artifact.txt"
            calls: list[Path] = []
            atomic_create_text(
                target,
                "first\n",
                path_guard=lambda path: calls.append(path),
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "first\n")
            self.assertEqual(len(calls), 4)
            with self.assertRaises(FileExistsError):
                atomic_create_text(target, "second\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "first\n")


if __name__ == "__main__":
    unittest.main()
