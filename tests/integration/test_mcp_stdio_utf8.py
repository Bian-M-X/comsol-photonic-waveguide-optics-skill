from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest


class McpStdioUtf8Tests(unittest.TestCase):
    def test_utf8_request_and_reference_ignore_legacy_console_encoding(self) -> None:
        request = {"jsonrpc": "2.0", "id": "光子-μ-∂", "method": "resources/read",
                   "params": {"uri": "photonic://skill/reference/adjoint-and-fabrication"}}
        environment = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        result = subprocess.run(
            [sys.executable, "-B", "-m", "photonic_workflow.mcp.server"],
            input=(json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"),
            capture_output=True, env=environment, timeout=20, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        response = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(response["id"], request["id"])
        self.assertIn("∂", response["result"]["contents"][0]["text"])


if __name__ == "__main__":
    unittest.main()
