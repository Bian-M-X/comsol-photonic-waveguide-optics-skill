from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from importlib.resources import as_file, files
from pathlib import Path

NAMES = {
    "README.md", "HadamardNative.java", "run.py", "campaign.py",
    "analyze.py", "extract_mask.py", "plot_results.py",
    "CvfDiscreteGradientProbe.java", "check_discrete_gradient.py",
}


class NativeExampleDeliveryTests(unittest.TestCase):
    def test_original_sources_match_finite_packaged_file_set(self) -> None:
        source = Path(__file__).resolve().parents[2] / "examples/comsol-hadamard-inverse"
        packaged = files("photonic_workflow").joinpath("data/skill/examples/comsol-hadamard-inverse")
        self.assertEqual({p.name for p in packaged.iterdir() if p.is_file()}, NAMES)
        for name in NAMES:
            self.assertEqual(
                hashlib.sha256((source / name).read_bytes()).hexdigest(),
                hashlib.sha256(packaged.joinpath(name).read_bytes()).hexdigest(), name,
            )

    def test_extracted_campaign_plans_without_checkout_or_solver(self) -> None:
        resource = files("photonic_workflow").joinpath("data/skill/examples/comsol-hadamard-inverse")
        with tempfile.TemporaryDirectory() as temporary, as_file(resource) as bundled:
            root = Path(temporary)
            extracted = root / "example"
            shutil.copytree(bundled, extracted)
            output = root / "fresh-run"
            result = subprocess.run(
                [sys.executable, "-B", str(extracted / "campaign.py"), "--output", str(output)],
                cwd=root, capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertTrue(plan["single_worker"])
            self.assertEqual(plan["binary_nominal"]["guided_modes"], 2)
            self.assertFalse(output.exists())
            self.assertTrue((extracted / "HadamardNative.java").is_file())
