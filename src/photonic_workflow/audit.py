from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

BLOCKED_SUFFIXES = {".mph", ".class", ".mphbin", ".mphstatus"}
EXCLUDED_DIRECTORIES = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".csv",
    ".java",
    ".py",
    ".ps1",
    ".psm1",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".config",
    ".properties",
    ".xml",
    ".sh",
    ".cmd",
    ".bat",
    ".log",
    ".sql",
    ".pem",
    ".key",
    ".pub",
    ".m",
}
SENSITIVE_NAME_RE = re.compile(
    r"^(?:\.env(?:\..+)?|credentials?(?:\..+)?|secrets?(?:\..+)?|tokens?(?:\..+)?|"
    r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?)$",
    re.IGNORECASE,
)
SENSITIVE_PATTERNS = {
    "license_setting": re.compile(r"\b(?:LM_LICENSE_FILE|COMSOL_LICENSE)\b\s*[:=]", re.IGNORECASE | re.MULTILINE),
    "license_file": re.compile(
        r"(?:\blicense\.dat\b|[^\s\"']+\.lic(?=[\s\"',;)]|$))",
        re.IGNORECASE | re.MULTILINE,
    ),
    "credential_token": re.compile(
        r"^[\t ]*(?:export[\t ]+)?[\"']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
        r"token|password|passwd|secret)[\"']?[\t ]*[:=][\t ]*[^\s#;]+",
        re.IGNORECASE | re.MULTILINE,
    ),
    "private_key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----", re.MULTILINE),
    "user_profile_path": re.compile(r"C:\\Users\\", re.IGNORECASE),
    "solver_install_path": re.compile(r"(?:COMSOL64\\Multiphysics|D:\\COMSOL|D:\\cosmol)", re.IGNORECASE),
}
SCANNER_FILES = {"audit-simulation-artifacts.ps1", "audit.py", "security.py"}


@dataclass(frozen=True)
class AuditFinding:
    kind: str
    path: str


def _is_likely_text(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return False
    if not sample:
        return True
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    if b"\x00" in sample:
        return False
    controls = sum(byte < 32 and byte not in {9, 10, 12, 13} for byte in sample)
    return controls <= max(1, int(len(sample) * 0.02))


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def audit_project_artifacts(
    project_root: Path,
    *,
    large_file_mb: int = 25,
    additional_excluded_dirs: Iterable[str] = (),
) -> dict[str, object]:
    root = project_root.resolve()
    large_limit = large_file_mb * 1024 * 1024
    excluded = {name.lower() for name in EXCLUDED_DIRECTORIES | set(additional_excluded_dirs)}
    findings: list[AuditFinding] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part.lower() in excluded for part in relative.parts[:-1]):
            continue
        suffix = path.suffix.lower()
        if suffix in BLOCKED_SUFFIXES:
            findings.append(AuditFinding("blocked_extension", relative.as_posix()))
        size = path.stat().st_size
        if size > large_limit:
            findings.append(AuditFinding(f"large_file>{large_file_mb}MB", relative.as_posix()))
        if SENSITIVE_NAME_RE.fullmatch(path.name):
            findings.append(AuditFinding("sensitive_file_name", relative.as_posix()))
        is_text_candidate = (
            suffix in TEXT_SUFFIXES
            or not suffix
            or path.name.lower().startswith(".env")
        )
        if is_text_candidate and path.name not in SCANNER_FILES and _is_likely_text(path):
            text = _read_text(path)
            if text is not None:
                for name, pattern in SENSITIVE_PATTERNS.items():
                    if pattern.search(text):
                        findings.append(AuditFinding(f"possible_sensitive_content:{name}", relative.as_posix()))
                        break
    serialized = [asdict(item) for item in findings]
    return {
        "project_root": str(root),
        "finding_count": len(serialized),
        "findings": serialized,
    }
