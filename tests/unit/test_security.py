from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from photonic_workflow.exceptions import SecurityViolationError
from photonic_workflow.security import (
    enforce_commercial_concurrency,
    enforce_instrument_safety,
    enforce_tapeout_mutable,
    ensure_within_allowed_roots,
    redact_text,
    require_known_mex,
    validate_matlab_function,
    validate_matlab_paths,
    validate_safe_label,
    verify_engine_session_identity,
)


class SecurityTests(unittest.TestCase):
    def test_path_traversal_and_windows_reserved_labels_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ensure_within_allowed_roots(root / "safe" / "result.json", [root])
            with self.assertRaises(SecurityViolationError):
                ensure_within_allowed_roots(root.parent / "escape", [root])
        for label in ("../escape", "..\\escape", "CON.report", ".", ""):
            with self.subTest(label=label), self.assertRaises(SecurityViolationError):
                validate_safe_label(label)

    def test_matlab_statement_and_function_allowlist(self) -> None:
        self.assertEqual(
            validate_matlab_function("photonic.entry", ["photonic.entry"]),
            "photonic.entry",
        )
        for value in ("eval", "photonic.entry;delete('*')", "system('whoami')"):
            with self.subTest(value=value), self.assertRaises(SecurityViolationError):
                validate_matlab_function(value, ["photonic.entry"])

    def test_matlab_path_pollution_unknown_mex_and_session_identity_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            startup = root / "startup.m"
            startup.write_text("", encoding="utf-8")
            with self.assertRaises(SecurityViolationError):
                validate_matlab_paths([startup], [root])
            mex = root / "unknown.mexw64"
            mex.write_bytes(b"fixture")
            with self.assertRaisesRegex(SecurityViolationError, "unknown MEX"):
                require_known_mex(mex, None, [root])
            session = "shared-session-fixture"
            expected = hashlib.sha256(session.encode()).hexdigest()
            verify_engine_session_identity(session, expected)
            with self.assertRaises(SecurityViolationError):
                verify_engine_session_identity(session, hashlib.sha256(b"other").hexdigest())

    def test_commercial_parallelism_instrument_safety_and_frozen_tapeout(self) -> None:
        with self.assertRaises(SecurityViolationError):
            enforce_commercial_concurrency(2, False)
        self.assertEqual(enforce_commercial_concurrency(2, True), 2)
        with self.assertRaises(SecurityViolationError):
            enforce_instrument_safety({"max_laser_power": None})
        with self.assertRaises(SecurityViolationError):
            enforce_tapeout_mutable(True)

    def test_redaction_hides_credentials_license_user_and_instrument_address(self) -> None:
        credential = "API_" + "KEY=secret"
        license_setting = "LM_" + "LICENSE_FILE=27000@server"
        user_path = "C:" + "\\Users\\person\\file"
        instrument = "GPIB0::12::INSTR"
        value = f"{credential} {license_setting} {user_path} {instrument}"
        redacted = redact_text(value)
        private_user_path = "C:" + "\\Users\\person"
        for secret in ("secret", "27000@server", private_user_path, instrument):
            self.assertNotIn(secret, redacted)


if __name__ == "__main__":
    unittest.main()
