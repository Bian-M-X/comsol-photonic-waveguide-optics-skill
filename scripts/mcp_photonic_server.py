from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


SERVER_NAME = "photonic-waveguide-optics-mcp"
SERVER_VERSION = "0.2.2"

SAFE_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
WINDOWS_RESERVED_BASENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
AUDIT_TEXT_SUFFIXES = {
    ".md", ".txt", ".csv", ".java", ".py", ".ps1", ".psm1", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".config",
    ".properties", ".xml", ".sh", ".cmd", ".bat", ".log", ".sql",
    ".pem", ".key", ".pub",
}
AUDIT_EXCLUDED_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv"}
AUDIT_SCANNER_FILES = {"audit-simulation-artifacts.ps1", "mcp_photonic_server.py"}
AUDIT_SENSITIVE_NAME_RE = re.compile(
    r"^(?:\.env(?:\..+)?|credentials?(?:\..+)?|secrets?(?:\..+)?|tokens?(?:\..+)?|id_(?:rsa|dsa|ecdsa|ed25519)(?:\.pub)?)$",
    re.IGNORECASE,
)
AUDIT_SENSITIVE_CONTENT = {
    "license_setting": re.compile(r"\b(?:LM_LICENSE_FILE|COMSOL_LICENSE)\b\s*[:=]", re.IGNORECASE | re.MULTILINE),
    "license_file": re.compile(r"(?:license\." + r"dat|\S+\." + "lic)", re.IGNORECASE | re.MULTILINE),
    "credential_token": re.compile(
        r"^[\t ]*(?:export[\t ]+)?[\"']?(?:api[_-]?key|access[_-]?token|auth[_-]?token|token|password|passwd|secret)[\"']?[\t ]*[:=][\t ]*[^\s#;]+",
        re.IGNORECASE | re.MULTILINE,
    ),
    "private_key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----", re.MULTILINE),
    "user_profile_path": re.compile(r"C:\\Users\\", re.IGNORECASE),
    "solver_install_path": re.compile(r"(?:COMSOL64\\Multiphysics|D:\\COMSOL|D:\\cosmol)", re.IGNORECASE),
}


REFERENCE_RESOURCES = {
    "frequency-domain-source-sweeps": "references/frequency-domain-source-sweeps.md",
    "hierarchical-device-workflow": "references/hierarchical-device-workflow.md",
    "verification-gates": "references/verification-gates.md",
    "smooth-bend-geometry": "references/smooth-bend-geometry.md",
    "subagent-orchestration": "references/subagent-orchestration.md",
    "comsol-mcp-evaluation": "references/comsol-mcp-evaluation.md",
    "quantum-photonic-knowledge-base": "references/quantum-photonic-knowledge-base.md",
    "project-structure-and-git": "references/project-structure-and-git.md",
}

AGENT_RESOURCES = {
    "planning": "agents/planning-agent.md",
    "geometry-modeling": "agents/geometry-modeling-agent.md",
    "execution": "agents/execution-agent.md",
    "code-auditor": "agents/code-auditor-agent.md",
    "model-auditor": "agents/model-auditor-agent.md",
    "results-auditor": "agents/results-auditor-agent.md",
    "data-processing": "agents/data-processing-agent.md",
    "literature-knowledge": "agents/literature-knowledge-agent.md",
    "mcp-integration": "agents/mcp-integration-agent.md",
}


class McpError(Exception):
    def __init__(self, message: str, code: int = -32000) -> None:
        super().__init__(message)
        self.code = code


def norm(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def ensure_allowed(path: Path, allowed_roots: list[Path]) -> Path:
    resolved = path.resolve()
    resolved_norm = norm(resolved)
    for root in allowed_roots:
        root_norm = norm(root)
        if resolved_norm == root_norm or resolved_norm.startswith(root_norm + os.sep):
            return resolved
    raise McpError(f"path is outside allowed roots: {path}", code=-32602)


def validate_artifact_label(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise McpError("label must be a non-empty string", code=-32602)
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise McpError("label must be a basename without path separators", code=-32602)
    if Path(value).is_absolute() or not SAFE_LABEL_RE.fullmatch(value):
        raise McpError(
            "label must be a safe basename using only ASCII letters, digits, '.', '_' and '-'",
            code=-32602,
        )
    reserved_prefix = value.split(".", 1)[0].upper()
    if reserved_prefix in WINDOWS_RESERVED_BASENAMES:
        raise McpError(f"label is a reserved basename: {value}", code=-32602)
    return value


def strict_json_dumps(value: Any, **kwargs: Any) -> str:
    return json.dumps(value, allow_nan=False, **kwargs)


def request_id_from(request: Any) -> str | int | float | None:
    if not isinstance(request, dict):
        return None
    request_id = request.get("id")
    if request_id is None or isinstance(request_id, str):
        return request_id
    if isinstance(request_id, bool) or not isinstance(request_id, (int, float)):
        return None
    if isinstance(request_id, float) and not math.isfinite(request_id):
        return None
    return request_id


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def parse_comsol_table(path: Path) -> list[dict[str, float | None]]:
    rows: list[dict[str, float | None]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        parts = line.split()
        if len(parts) < 4:
            raise McpError(f"{path}:{lineno}: expected at least 4 numeric columns", code=-32602)
        try:
            freq_ghz = float(parts[0])
            lambda_um = float(parts[1])
            s11 = float(parts[2])
            t21 = float(parts[3])
            t21_db = float(parts[4]) if len(parts) >= 5 else None
        except ValueError as exc:
            raise McpError(f"{path}:{lineno}: cannot parse numeric row", code=-32602) from exc
        numeric_values = [freq_ghz, lambda_um, s11, t21]
        if t21_db is not None:
            numeric_values.append(t21_db)
        if not all(math.isfinite(value) for value in numeric_values):
            raise McpError(f"{path}:{lineno}: non-finite numeric value is not allowed", code=-32602)
        rows.append(
            {
                "freq_GHz": freq_ghz,
                "lambda_nm": lambda_um * 1000.0,
                "S11": s11,
                "T21": t21,
                "T21_dB": t21_db,
                "S11_plus_T21": s11 + t21,
            }
        )
    if not rows:
        raise McpError(f"no data rows parsed from {path}", code=-32602)
    return rows


def extrema(
    rows: list[dict[str, float | None]], mode: str, threshold: float
) -> list[dict[str, float | None]]:
    """Return one representative sample for each strict local extremum plateau."""
    out: list[dict[str, float | None]] = []
    i = 0
    while i < len(rows):
        start = i
        current = float(rows[i]["T21"])
        while i + 1 < len(rows) and math.isclose(
            float(rows[i + 1]["T21"]), current, rel_tol=1e-12, abs_tol=1e-15
        ):
            i += 1
        end = i
        if start > 0 and end < len(rows) - 1:
            left = float(rows[start - 1]["T21"])
            right = float(rows[end + 1]["T21"])
            is_peak = mode == "max" and current > left and current > right and current >= threshold
            is_valley = mode == "min" and current < left and current < right
            if is_peak or is_valley:
                representative = dict(rows[(start + end) // 2])
                representative["lambda_nm"] = 0.5 * (
                    float(rows[start]["lambda_nm"]) + float(rows[end]["lambda_nm"])
                )
                out.append(representative)
        i += 1
    return out


def summarize_rows(label: str, rows: list[dict[str, float | None]], peak_threshold: float) -> dict[str, Any]:
    if not math.isfinite(peak_threshold):
        raise McpError("peak_threshold must be finite", code=-32602)
    spectral_rows = sorted(rows, key=lambda row: float(row["lambda_nm"]))
    max_row = max(spectral_rows, key=lambda row: float(row["T21"]))
    min_row = min(spectral_rows, key=lambda row: float(row["T21"]))
    peaks = extrema(spectral_rows, "max", peak_threshold)
    valleys = extrema(spectral_rows, "min", peak_threshold)
    peak_spacings = [peaks[i + 1]["lambda_nm"] - peaks[i]["lambda_nm"] for i in range(len(peaks) - 1)]
    valley_spacings = [valleys[i + 1]["lambda_nm"] - valleys[i]["lambda_nm"] for i in range(len(valleys) - 1)]
    peak_values = [row["T21"] for row in peaks]
    strongest_peak = max(peak_values) if peak_values else None
    weak_strong = min(peak_values) / strongest_peak if strongest_peak is not None and strongest_peak > 0 else None
    return {
        "label": label,
        "row_count": len(rows),
        "max_T21": max_row["T21"],
        "max_lambda_nm": max_row["lambda_nm"],
        "S11_at_max": max_row["S11"],
        "Ssum_at_max": max_row["S11_plus_T21"],
        "min_T21": min_row["T21"],
        "min_lambda_nm": min_row["lambda_nm"],
        "peak_lambdas_nm": [row["lambda_nm"] for row in peaks],
        "peak_T21s": [row["T21"] for row in peaks],
        "peak_spacings_nm": peak_spacings,
        "valley_lambdas_nm": [row["lambda_nm"] for row in valleys],
        "valley_spacings_nm": valley_spacings,
        "weak_strong_ratio": weak_strong,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_likely_text_sample(path: Path, limit: int = 1024 * 1024) -> str | None:
    try:
        with path.open("rb") as handle:
            raw = handle.read(limit)
    except OSError:
        return None
    if not raw:
        return ""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if b"\x00" in raw:
        return None
    control_count = sum(byte < 32 and byte not in {9, 10, 12, 13} for byte in raw)
    if control_count > max(1, int(len(raw) * 0.02)):
        return None
    return raw.decode("utf-8", errors="replace")


def safe_artifact_audit(project_root: Path) -> dict[str, Any]:
    blocked_suffixes = {".mph", ".class", ".mphbin", ".mphstatus"}
    large_limit = 25 * 1024 * 1024
    findings: list[dict[str, str]] = []
    for path in project_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(project_root)
        if any(part.lower() in AUDIT_EXCLUDED_DIRS for part in relative.parts[:-1]):
            continue
        suffix = path.suffix.lower()
        if suffix in blocked_suffixes:
            findings.append({"kind": "blocked_extension", "path": str(relative)})
        if path.stat().st_size > large_limit:
            findings.append({"kind": "large_file", "path": str(relative)})
        if AUDIT_SENSITIVE_NAME_RE.fullmatch(path.name):
            findings.append({"kind": "sensitive_file_name", "path": str(relative)})
        is_text_candidate = suffix in AUDIT_TEXT_SUFFIXES or not suffix or path.name.lower().startswith(".env")
        if is_text_candidate and path.name not in AUDIT_SCANNER_FILES:
            content = read_likely_text_sample(path)
            if content is not None:
                for name, pattern in AUDIT_SENSITIVE_CONTENT.items():
                    if pattern.search(content):
                        findings.append({"kind": f"possible_sensitive_content:{name}", "path": str(relative)})
                        break
    return {"project_root": str(project_root), "finding_count": len(findings), "findings": findings}


def create_project_scaffold(project_root: Path, device_family: str) -> dict[str, Any]:
    folders = [
        "requirements",
        "components/contracts",
        "components/sparameters",
        "circuits",
        "layout",
        "models/java",
        "models/mph",
        "runs",
        "scripts",
        "data/raw",
        "data/processed",
        "verification",
        "reports",
        "handoff",
    ]
    project_root.mkdir(parents=True, exist_ok=True)
    for folder in folders:
        (project_root / folder).mkdir(parents=True, exist_ok=True)
    project_file = project_root / "PROJECT.md"
    if not project_file.exists():
        project_file.write_text(
            "\n".join(
                [
                    "# Photonic Simulation Project",
                    "",
                    f"Device family: {device_family}",
                    "",
                    "## Objective",
                    "",
                    "## Assumptions",
                    "",
                    "## Validation Targets",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    handoff = project_root / "handoff" / "latest.md"
    if not handoff.exists():
        handoff.write_text("# Latest Handoff\n\nStatus: initialized\n", encoding="utf-8")
    skill_root = Path(__file__).resolve().parent.parent
    template_root = skill_root / "assets" / "templates" / "hierarchical-device"
    normalized_family = device_family.strip().lower()
    use_mzi_template = normalized_family in {"mzi", "balanced-mzi", "interferometer"}
    assembly = project_root / "circuits" / "assembly.json"
    assembly_tool = project_root / "scripts" / "photonic_assembly.py"
    requirements_file = project_root / "requirements.txt"
    gitignore = project_root / ".gitignore"
    if use_mzi_template:
        assembly_template = template_root / "mzi-4port" / "circuits" / "assembly.json"
        sparameter_templates = {
            "directional_coupler.csv": template_root / "mzi-4port" / "components" / "sparameters" / "directional_coupler.csv",
            "arm.csv": template_root / "mzi-4port" / "components" / "sparameters" / "arm.csv",
        }
        template_kind = "mzi-4port"
    else:
        assembly_template = template_root / "assembly.json"
        sparameter_templates = {"waveguide.csv": template_root / "waveguide.csv"}
        template_kind = "waveguide-cascade"
    if assembly_template.exists() and not assembly.exists():
        assembly.write_text(assembly_template.read_text(encoding="utf-8"), encoding="utf-8")
    for filename, source in sparameter_templates.items():
        destination = project_root / "components" / "sparameters" / filename
        if source.exists() and not destination.exists():
            destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    if not assembly_tool.exists():
        assembly_tool.write_text((skill_root / "scripts" / "photonic_assembly.py").read_text(encoding="utf-8"), encoding="utf-8")
    if not requirements_file.exists():
        requirements_file.write_text((skill_root / "requirements.txt").read_text(encoding="utf-8"), encoding="utf-8")
    if not gitignore.exists():
        gitignore.write_text(
            "\n".join(
                [
                    "*.mph",
                    "*.class",
                    "*.log",
                    "*.mphbin",
                    "models/mph/",
                    "runs/**/runtime/",
                    "data/raw/",
                    "__pycache__/",
                    "*.pyc",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return {
        "project_root": str(project_root),
        "device_family": device_family,
        "template_kind": template_kind,
        "created_folders": folders,
        "created_files": [
            "PROJECT.md",
            "handoff/latest.md",
            "circuits/assembly.json",
            *[f"components/sparameters/{name}" for name in sparameter_templates],
            "scripts/photonic_assembly.py",
            "requirements.txt",
            ".gitignore",
        ],
    }


def read_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def build_java_batch_plan(
    java_file: Path,
    output_mph: Path,
    batch_log: Path,
    runtime_dir: Path,
    timeout_s: int,
    solver_root_source: str,
    execution_enabled: bool,
) -> dict[str, Any]:
    if java_file.suffix.lower() != ".java":
        raise McpError(f"java_file must end with .java: {java_file}", code=-32602)
    if output_mph.suffix.lower() != ".mph":
        raise McpError(f"output_mph must end with .mph: {output_mph}", code=-32602)
    if batch_log.suffix.lower() != ".log":
        raise McpError(f"batch_log must end with .log: {batch_log}", code=-32602)
    if timeout_s < 1 or timeout_s > 7 * 24 * 60 * 60:
        raise McpError("timeout_s must be between 1 and 604800 seconds", code=-32602)

    class_file = java_file.with_suffix(".class")
    prefs_dir = runtime_dir / "prefs"
    config_dir = runtime_dir / "config"
    tmp_dir = runtime_dir / "tmp"
    return {
        "dry_run": True,
        "execution_enabled": execution_enabled,
        "will_execute": False,
        "solver_root_source": solver_root_source,
        "solver_root_redacted_as": "<PHOTONIC_SOLVER_ROOT>",
        "java_file": str(java_file),
        "class_file": str(class_file),
        "output_mph": str(output_mph),
        "batch_log": str(batch_log),
        "runtime_dirs": {
            "root": str(runtime_dir),
            "prefs": str(prefs_dir),
            "config": str(config_dir),
            "tmp": str(tmp_dir),
        },
        "timeout_s": timeout_s,
        "compile_command_shape": [
            "<PHOTONIC_SOLVER_ROOT>\\java\\win64\\jre\\bin\\javac.exe",
            "-proc:none",
            "-cp",
            "<PHOTONIC_SOLVER_ROOT>\\plugins\\*.jar",
            str(java_file),
        ],
        "batch_command_shape": [
            "<PHOTONIC_SOLVER_ROOT>\\bin\\win64\\comsolbatch.exe",
            "-prefsdir",
            str(prefs_dir),
            "-configuration",
            str(config_dir),
            "-tmpdir",
            str(tmp_dir),
            "-inputfile",
            str(class_file),
            "-outputfile",
            str(output_mph),
            "-batchlog",
            str(batch_log),
        ],
        "safety_gate": "dry-run only; call scripts/invoke-waveguide-java-batch.ps1 directly until direct-batch equality tests pass",
    }


class PhotonicMcpServer:
    def __init__(self, skill_root: Path, allowed_roots: list[Path], enable_execution: bool = False) -> None:
        self.skill_root = skill_root.resolve()
        self.allowed_roots = [root.resolve() for root in allowed_roots]
        self.enable_execution = enable_execution

    def resource_list(self) -> list[dict[str, str]]:
        resources = [
            {
                "uri": "photonic://server/manifest",
                "name": "server manifest",
                "description": "Server capabilities and allowlist summary",
                "mimeType": "application/json",
            }
        ]
        for name in REFERENCE_RESOURCES:
            resources.append(
                {
                    "uri": f"photonic://skill/reference/{name}",
                    "name": f"reference: {name}",
                    "description": "Photonic simulation skill reference",
                    "mimeType": "text/markdown",
                }
            )
        for name in AGENT_RESOURCES:
            resources.append(
                {
                    "uri": f"photonic://skill/agent/{name}",
                    "name": f"agent: {name}",
                    "description": "Subagent role contract",
                    "mimeType": "text/markdown",
                }
            )
        return resources

    def resource_read(self, uri: str) -> list[dict[str, str]]:
        if uri == "photonic://server/manifest":
            payload = {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "allowed_roots_count": len(self.allowed_roots),
                "tools": [tool["name"] for tool in self.tool_list()],
                "resources": [item["uri"] for item in self.resource_list()],
            }
            return [{"uri": uri, "mimeType": "application/json", "text": strict_json_dumps(payload, indent=2)}]
        if uri.startswith("photonic://skill/reference/"):
            name = uri.rsplit("/", 1)[-1]
            rel = REFERENCE_RESOURCES.get(name)
            if not rel:
                raise McpError(f"unknown reference resource: {name}", code=-32602)
            path = ensure_allowed(self.skill_root / rel, self.allowed_roots)
            return [{"uri": uri, "mimeType": "text/markdown", "text": path.read_text(encoding="utf-8")}]
        if uri.startswith("photonic://skill/agent/"):
            name = uri.rsplit("/", 1)[-1]
            rel = AGENT_RESOURCES.get(name)
            if not rel:
                raise McpError(f"unknown agent resource: {name}", code=-32602)
            path = ensure_allowed(self.skill_root / rel, self.allowed_roots)
            return [{"uri": uri, "mimeType": "text/markdown", "text": path.read_text(encoding="utf-8")}]
        raise McpError(f"unknown resource uri: {uri}", code=-32602)

    def tool_list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list_allowed_roots",
                "title": "List allowed roots",
                "description": "Return the allowlisted roots this server can access.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "create_project_scaffold",
                "title": "Create photonic project scaffold",
                "description": "Create a standard photonic simulation project folder layout.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "project_root": {"type": "string"},
                        "device_family": {"type": "string", "default": "waveguide"},
                    },
                    "required": ["project_root"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "audit_project_artifacts",
                "title": "Audit project artifacts",
                "description": "Scan for obvious large or blocked solver artifacts under a project root.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"project_root": {"type": "string"}},
                    "required": ["project_root"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "parse_sweep_table",
                "title": "Parse COMSOL sweep table",
                "description": "Parse a COMSOL text sweep table and write summary/trace CSV files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_file": {"type": "string"},
                        "output_dir": {"type": "string"},
                        "label": {"type": "string"},
                        "peak_threshold": {"type": "number", "default": 0.02},
                    },
                    "required": ["table_file", "output_dir"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "run_java_batch",
                "title": "Render Java batch run plan",
                "description": "Render a redacted, allowlist-checked COMSOL Java batch dry-run plan. Real execution is disabled in this prototype.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "java_file": {"type": "string"},
                        "output_mph": {"type": "string"},
                        "batch_log": {"type": "string"},
                        "runtime_dir": {"type": "string"},
                        "solver_root": {"type": "string"},
                        "timeout_s": {"type": "integer", "default": 3600},
                        "dry_run": {"type": "boolean", "default": True},
                        "allow_execute": {"type": "boolean", "default": False},
                    },
                    "required": ["java_file", "output_mph", "batch_log", "runtime_dir"],
                    "additionalProperties": False,
                },
            },
        ]

    def tool_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "list_allowed_roots":
            result = {"allowed_roots": [str(root) for root in self.allowed_roots]}
        elif name == "create_project_scaffold":
            root = ensure_allowed(Path(arguments["project_root"]), self.allowed_roots)
            result = create_project_scaffold(root, str(arguments.get("device_family", "waveguide")))
        elif name == "audit_project_artifacts":
            root = ensure_allowed(Path(arguments["project_root"]), self.allowed_roots)
            result = safe_artifact_audit(root)
        elif name == "parse_sweep_table":
            table = ensure_allowed(Path(arguments["table_file"]), self.allowed_roots)
            out_dir = ensure_allowed(Path(arguments["output_dir"]), self.allowed_roots)
            raw_label = arguments["label"] if "label" in arguments else table.stem
            label = validate_artifact_label(raw_label)
            threshold = float(arguments.get("peak_threshold", 0.02))
            rows = parse_comsol_table(table)
            summary = summarize_rows(label, rows, threshold)
            summary_csv = ensure_allowed(out_dir / f"{label}_summary.csv", self.allowed_roots)
            trace_csv = ensure_allowed(out_dir / f"{label}_trace.csv", self.allowed_roots)
            write_csv(summary_csv, [summary])
            write_csv(trace_csv, rows)
            result = {"summary": summary, "summary_csv": str(summary_csv), "trace_csv": str(trace_csv)}
        elif name == "run_java_batch":
            java_file = ensure_allowed(Path(arguments["java_file"]), self.allowed_roots)
            output_mph = ensure_allowed(Path(arguments["output_mph"]), self.allowed_roots)
            batch_log = ensure_allowed(Path(arguments["batch_log"]), self.allowed_roots)
            runtime_dir = ensure_allowed(Path(arguments["runtime_dir"]), self.allowed_roots)
            dry_run = read_bool(arguments.get("dry_run"), True)
            allow_execute = read_bool(arguments.get("allow_execute"), False)
            timeout_s = int(arguments.get("timeout_s", 3600))
            solver_root_source = "argument" if arguments.get("solver_root") else "env:PHOTONIC_SOLVER_ROOT"
            if not arguments.get("solver_root") and not os.environ.get("PHOTONIC_SOLVER_ROOT"):
                solver_root_source = "unset"
            if not dry_run:
                if not allow_execute:
                    raise McpError("non-dry-run requires allow_execute=true and explicit user approval", code=-32602)
                if not self.enable_execution:
                    raise McpError("server was not started with --enable-execution; non-dry-run is disabled", code=-32602)
                raise McpError(
                    "non-dry-run solver execution is intentionally not implemented in this prototype; use scripts/invoke-waveguide-java-batch.ps1 directly",
                    code=-32000,
                )
            result = build_java_batch_plan(
                java_file,
                output_mph,
                batch_log,
                runtime_dir,
                timeout_s,
                solver_root_source,
                self.enable_execution,
            )
        else:
            raise McpError(f"unknown tool: {name}", code=-32602)

        return {
            "content": [{"type": "text", "text": strict_json_dumps(result, indent=2)}],
            "structuredContent": result,
            "isError": False,
        }

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict):
            raise McpError("invalid request: expected a JSON object", code=-32600)
        if request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            raise McpError("invalid JSON-RPC request", code=-32600)
        if "id" in request and request_id_from(request) is None and request.get("id") is not None:
            raise McpError("invalid JSON-RPC request id", code=-32600)
        method = request.get("method")
        request_id = request_id_from(request)
        params = request.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise McpError("params must be an object", code=-32602)
        if method == "notifications/initialized":
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"resources": {"listChanged": False}, "tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            }
        if method == "resources/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"resources": self.resource_list()}}
        if method == "resources/read":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"contents": self.resource_read(str(params.get("uri", "")))},
            }
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": self.tool_list()}}
        if method == "tools/call":
            arguments = params.get("arguments", {})
            if arguments is None:
                arguments = {}
            if not isinstance(arguments, dict):
                raise McpError("tool arguments must be an object", code=-32602)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self.tool_call(str(params.get("name", "")), arguments),
            }
        raise McpError(f"unknown method: {method}", code=-32601)


def parse_roots(values: list[str], skill_root: Path) -> list[Path]:
    roots = [skill_root.resolve()]
    env_roots = os.environ.get("PHOTONIC_MCP_ALLOWED_ROOTS", "")
    for raw in [*values, *env_roots.split(os.pathsep)]:
        if raw.strip():
            roots.append(Path(raw).resolve())
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = norm(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal stdio MCP server for photonic-waveguide-optics workflows.")
    parser.add_argument("--skill-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allow-root", action="append", default=[])
    parser.add_argument("--enable-execution", action="store_true", help="Reserve flag for future non-dry-run solver execution gates.")
    args = parser.parse_args()

    server = PhotonicMcpServer(
        args.skill_root.resolve(),
        parse_roots(args.allow_root, args.skill_root.resolve()),
        enable_execution=args.enable_execution,
    )
    for raw in sys.stdin:
        request: Any = None
        try:
            request = json.loads(raw, parse_constant=reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"parse error: {exc}"},
            }
        else:
            try:
                response = server.handle(request)
            except McpError as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id_from(request),
                    "error": {"code": exc.code, "message": str(exc)},
                }
            except Exception as exc:  # fail closed for protocol tests
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id_from(request),
                    "error": {"code": -32000, "message": f"internal error: {exc}"},
                }
        if response is not None:
            try:
                encoded = strict_json_dumps(response)
            except (TypeError, ValueError):
                encoded = strict_json_dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32000, "message": "internal error: response is not strict JSON"},
                    }
                )
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
