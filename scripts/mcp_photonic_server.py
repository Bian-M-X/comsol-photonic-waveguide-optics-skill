from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from pathlib import Path
from typing import Any


SERVER_NAME = "photonic-waveguide-optics-mcp"
SERVER_VERSION = "0.1.0"


REFERENCE_RESOURCES = {
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


def parse_comsol_table(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
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
            t21_db = float(parts[4]) if len(parts) >= 5 else math.nan
        except ValueError as exc:
            raise McpError(f"{path}:{lineno}: cannot parse numeric row") from exc
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


def extrema(rows: list[dict[str, float]], mode: str, threshold: float) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for i in range(1, len(rows) - 1):
        prev_v = rows[i - 1]["T21"]
        cur_v = rows[i]["T21"]
        next_v = rows[i + 1]["T21"]
        if mode == "max" and cur_v >= prev_v and cur_v >= next_v and cur_v >= threshold:
            out.append(rows[i])
        if mode == "min" and cur_v <= prev_v and cur_v <= next_v:
            out.append(rows[i])
    return out


def summarize_rows(label: str, rows: list[dict[str, float]], peak_threshold: float) -> dict[str, Any]:
    max_row = max(rows, key=lambda row: row["T21"])
    min_row = min(rows, key=lambda row: row["T21"])
    peaks = extrema(rows, "max", peak_threshold)
    valleys = extrema(rows, "min", peak_threshold)
    peak_spacings = [peaks[i + 1]["lambda_nm"] - peaks[i]["lambda_nm"] for i in range(len(peaks) - 1)]
    valley_spacings = [valleys[i + 1]["lambda_nm"] - valleys[i]["lambda_nm"] for i in range(len(valleys) - 1)]
    peak_values = [row["T21"] for row in peaks]
    weak_strong = min(peak_values) / max(peak_values) if peak_values else math.nan
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


def safe_artifact_audit(project_root: Path) -> dict[str, Any]:
    blocked_suffixes = {".mph", ".class", ".mphbin", ".mphstatus"}
    large_limit = 25 * 1024 * 1024
    findings: list[dict[str, str]] = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in blocked_suffixes:
            findings.append({"kind": "blocked_extension", "path": str(path.relative_to(project_root))})
        if path.stat().st_size > large_limit:
            findings.append({"kind": "large_file", "path": str(path.relative_to(project_root))})
    return {"project_root": str(project_root), "finding_count": len(findings), "findings": findings}


def create_project_scaffold(project_root: Path, device_family: str) -> dict[str, Any]:
    folders = [
        "requirements",
        "models/java",
        "models/mph",
        "runs",
        "scripts",
        "data/raw",
        "data/processed",
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
    return {"project_root": str(project_root), "device_family": device_family, "created_folders": folders}


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
            return [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload, indent=2)}]
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
            label = str(arguments.get("label") or table.stem)
            threshold = float(arguments.get("peak_threshold", 0.02))
            rows = parse_comsol_table(table)
            summary = summarize_rows(label, rows, threshold)
            summary_csv = out_dir / f"{label}_summary.csv"
            trace_csv = out_dir / f"{label}_trace.csv"
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
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "structuredContent": result,
            "isError": False,
        }

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params") or {}
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
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self.tool_call(str(params.get("name", "")), dict(params.get("arguments") or {})),
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
        try:
            request = json.loads(raw)
            response = server.handle(request)
        except McpError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": locals().get("request", {}).get("id"),
                "error": {"code": exc.code, "message": str(exc)},
            }
        except Exception as exc:  # fail closed for protocol tests
            response = {
                "jsonrpc": "2.0",
                "id": locals().get("request", {}).get("id"),
                "error": {"code": -32000, "message": f"internal error: {exc}"},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
