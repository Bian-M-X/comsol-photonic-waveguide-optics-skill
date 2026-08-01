from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from photonic_workflow.exceptions import InvalidInputError
from photonic_workflow.gates import GATE_DEFINITIONS, GateLedger
from photonic_workflow.models import GateName, GateStatus


class GateLedgerTests(unittest.TestCase):
    def test_gate_definition_snapshot_covers_g_and_measurement_tracks(self) -> None:
        self.assertEqual(
            [gate.value for gate in GATE_DEFINITIONS],
            [f"G{index}" for index in range(9)] + [f"M{index}" for index in range(5)],
        )

    def test_missing_evidence_remains_blocked_and_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = GateLedger(Path(temporary))
            records = ledger.load(create_if_missing=True)
            self.assertTrue(all(record.status == GateStatus.BLOCKED for record in records))
            with self.assertRaisesRegex(InvalidInputError, "requires explicit evidence"):
                ledger.update(
                    GateName.G1,
                    GateStatus.PASS,
                    evidence=[],
                    reason="",
                    next_action="",
                )

    def test_g_and_m_tracks_remain_separate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ledger = GateLedger(Path(temporary))
            ledger.load(create_if_missing=True)
            updated = ledger.update(
                GateName.M0,
                GateStatus.PASS,
                evidence=["testplans/fixture.json"],
                reason="test plan recorded",
                next_action="capture raw data",
            )
            self.assertEqual(updated.gate, GateName.M0)
            summary = ledger.summary()
            self.assertFalse(summary["all_gates_passed"])
            self.assertFalse(summary["measurement_track_complete"])


if __name__ == "__main__":
    unittest.main()
