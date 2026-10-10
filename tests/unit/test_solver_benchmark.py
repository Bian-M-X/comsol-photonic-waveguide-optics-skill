from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import benchmark_comsol_solvers as benchmark


class SolverBenchmarkTests(unittest.TestCase):
    def test_literals_reject_control_characters_and_preserve_quoted_paths(self) -> None:
        value = 'D:\\models\\a "quoted" model.mph'
        self.assertEqual(json.loads(benchmark.java_literal(value)), value)
        with self.assertRaises(ValueError):
            benchmark.java_literal('bad\nexpression')

    @unittest.skipUnless(os.name == "nt", "Windows native entrypoints only")
    def test_dry_run_never_starts_process_or_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "bin/win64"
            binary.mkdir(parents=True)
            for name in ("comsolcompile.exe", "comsolbatch.exe"):
                (binary / name).touch()
            model = root / "model.mph"
            model.write_bytes(b"not executed")
            args = ["benchmark", "--solver-root", str(root), "--model", str(model),
                    "--output", str(root / "results"), "--metric", "real(ewfd.S21)"]
            with patch("sys.argv", args), redirect_stdout(io.StringIO()) as output, patch(
                "subprocess.Popen", side_effect=AssertionError("dry-run must not start a process"),
            ):
                self.assertEqual(benchmark.main(), 0)
            self.assertFalse(json.loads(output.getvalue())["execute"])
            self.assertFalse((root / "results").exists())
            self.assertEqual(model.read_bytes(), b"not executed")

    def test_timeout_targets_only_owned_process(self) -> None:
        process = Mock(pid=123456)
        process.wait.side_effect = [subprocess.TimeoutExpired("fixture", 1), 0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("subprocess.Popen", return_value=process), patch("subprocess.run") as kill:
                code, _ = benchmark.run_process(["fixture"], root, root / "log.txt", 1)
            self.assertEqual(code, 124)
            if os.name == "nt":
                self.assertEqual(kill.call_args.args[0], ["taskkill", "/PID", "123456", "/T", "/F"])
            else:
                process.kill.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
