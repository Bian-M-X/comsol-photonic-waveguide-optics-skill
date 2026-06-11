# COMSOL Automation And MCP Evaluation

Use this reference when deciding whether to run COMSOL through Java batch, an interactive server, LiveLink-style APIs, or a future MCP server bridge.

## Current Recommendation

| Route | Status | Use as | Reason |
|---|---|---|---|
| Java API source + `javac` + `comsolbatch` | Stable local default | First choice | Reproducible, scriptable, easy to log, good for long runs and CI-like workflows |
| `mphserver` / LiveLink-style interactive control | Useful but stateful | Backup or exploratory | Good for interactive inspection, but more fragile for unattended runs and environment setup |
| Custom MCP server bridge around the batch runner | Phase 1/2 tested; Phase 3 dry-run tested | Experimental backup after validation | Resource discovery, artifact audit, scaffold creation, sweep parsing, and redacted batch-plan rendering are feasible; solver execution still needs direct-batch equality tests |

As of the 2026-06 skill update, no verified, project-ready, off-the-shelf COMSOL MCP server was adopted. Treat MCP as an integration layer around the already reliable batch route, not as a replacement for the solver workflow.

## Local Prototype Test Status

A dependency-free stdio JSON-RPC prototype is provided in:

- `scripts/mcp_photonic_server.py`
- `scripts/test_mcp_photonic_server.py`

Tested MCP-style calls:

- `initialize`
- `resources/list`
- `resources/read` for `photonic://server/manifest`
- `tools/list`
- `tools/call` for `parse_sweep_table`
- `tools/call` for `create_project_scaffold`
- `tools/call` for `audit_project_artifacts`
- `tools/call` for `run_java_batch` in dry-run mode only

Smoke-test result on an existing LT-aMZI true-smooth sweep table:

```text
resource_count = 15
tools = list_allowed_roots, create_project_scaffold, audit_project_artifacts, parse_sweep_table, run_java_batch
row_count = 31
max_T21 = 0.3255039699650145
max_lambda_nm = 1520.4
S11_at_max = 0.42635136264708123
audit_finding_count = 0
run_java_batch dry_run = true
run_java_batch will_execute = false
raw_solver_root_returned = false
```

Verdict: Phase 1 and Phase 2 are practically feasible. Phase 3 dry-run rendering is practically feasible and now validates allowlisted paths, redacted solver-root display, timeout input, runtime directory shape, and refusal to execute. Keep real solver execution outside MCP until approval prompts, redaction audit, timeout behavior, failure-mode handling, and direct-batch equality checks pass.

## Why Batch Remains First Choice

- It keeps the model source auditable.
- It creates a durable `.mph`, `.log`, table, and plot artifact trail.
- It avoids hidden interactive server state.
- It works with isolated runtime directories for repeatable jobs.
- It is easy to wrap in PowerShell and Python without exposing proprietary binaries in the repository.

## When To Consider `mphserver`

Use only when the workflow needs:

- interactive model inspection;
- programmatic loading and editing of existing `.mph` files;
- iterative GUI-like debugging;
- APIs that are not convenient through one-shot Java source.

Do not use it as the default for long parameter sweeps until startup, authentication, timeout, and cleanup behavior are stable on the user's machine.

## Usable MCP Route To Prototype First

The first usable route should be a thin local MCP server that wraps existing, tested scripts. It should not attempt to control the GUI or open a broad shell. The MVP goal is: a new conversation can discover a photonic project, compile/run an approved Java model through the batch route, and read structured result summaries.

### Phase 0: Preconditions

- Keep `scripts/invoke-waveguide-java-batch.ps1` as the only solver execution backend.
- Keep `scripts/parse-comsol-sweep.py` as the first table parser.
- Require an explicit project root under an allowlist such as `%USERPROFILE%\Documents`, `D:\Quantum Chip Based on Light`, or another user-approved root.
- Resolve the solver location from `PHOTONIC_SOLVER_ROOT`; do not expose the full value in normal responses.
- Never place proprietary binaries, plugin jars, license files, `.mph` models, or raw logs inside the MCP server package.

### Phase 1: Read-Only Server

Build the first MCP server with resources only:

- `photonic://projects` lists registered project manifests.
- `photonic://project/<id>/manifest` returns project metadata, parameters, and latest handoff.
- `photonic://project/<id>/tables` lists parsed tables.
- `photonic://project/<id>/summary/<run>` returns a bounded metrics summary.
- `photonic://knowledge/<topic>` exposes selected skill references such as bend geometry, MZI workflow, and quantum photonic basics.

Acceptance test: the assistant can answer "what is the latest run, baseline, and next action?" without direct filesystem exploration.

### Phase 2: Safe Local Tools

Add tools that do not launch COMSOL:

- `create_project_scaffold(project_root, device_family)`
- `audit_project_artifacts(project_root)`
- `parse_sweep_table(table_file, output_dir, label)`
- `render_run_manifest(project_root, run_id)`

Acceptance test: the tools create or parse only inside the allowlisted project root and return structured JSON plus file links.

Prototype status: passed for scaffold creation, artifact audit, and sweep-table parsing.

### Phase 3: Batch Execution Tool

Add one controlled execution tool:

- `run_java_batch(java_file, output_mph, batch_log, runtime_dir, timeout_s, dry_run=false)`

Required behavior:

- show a dry-run command shape first for new projects or new model files;
- require user approval for non-dry-run long solves;
- create unique runtime dirs per job;
- enforce timeout;
- redact local solver root and username from returned logs;
- return `compile_status`, `run_status`, `output_files`, `key_stdout_rows`, and `errors`.

Acceptance test: run a straight-waveguide or analytic-bend smoke model and compare the generated summary with the direct PowerShell route.

Prototype status: dry-run command rendering is implemented and smoke-tested. Non-dry-run execution remains intentionally disabled in the prototype. Keep direct batch as the only solver execution route until this gate is tested against a straight-waveguide or analytic-bend smoke model.

### Phase 4: Comparison Against Existing Routes

Only after Phases 1-3 pass, compare MCP with direct batch and `mphserver` on the same task set:

| Task | Direct batch | MCP wrapper | `mphserver`/LiveLink |
|---|---|---|---|
| new model compile/run | primary baseline | should match baseline with better discoverability | unnecessary |
| read existing project status | manual file reads | strong use case through resources | unnecessary |
| parse sweep table | script call | strong use case through structured tool | unnecessary |
| interactive model inspection | weak | weak unless a narrow inspection tool exists | strong backup |
| long parameter sweep | strong with sequential runner | possible after queue/timeout support | risky until lifecycle is stable |
| GUI-like debugging | weak | weak | strongest |

Decision rule: use MCP as the daily assistant interface only if it matches direct batch results, reduces context/setup friction, and does not weaken security or reproducibility.

## Proposed MCP Server Shape

An MCP bridge should not expose arbitrary shell execution. It should expose narrow tools and resources:

### Tools

- `compile_java_model(java_file, solver_root_alias, class_output_dir)`
- `run_batch_model(class_file, output_mph, batch_log, runtime_dir)`
- `summarize_comsol_table(table_file)`
- `audit_artifact_folder(project_dir)`
- `create_project_scaffold(project_dir, device_family)`

### Resources

- `photonic://project/<id>/manifest`
- `photonic://project/<id>/logs/<job>`
- `photonic://project/<id>/tables/<table>`
- `photonic://knowledge/devices/<device-family>`

### Security Defaults

- allowlist project roots;
- no arbitrary command strings;
- timeout every solver call;
- require user confirmation for long jobs;
- redact solver root, username, license paths, and environment variables in returned text;
- return structured status and file links, not raw uncontrolled logs by default.

## Adoption Gate

Keep Java batch as primary until an MCP bridge passes:

1. dry-run command rendering;
2. one straight-waveguide smoke test;
3. one single-bend analytic geometry test;
4. one wavelength sweep with parsed CSV;
5. redaction audit;
6. failure-mode test for missing solver root and nonconverged solve;
7. comparison against the current `scripts/invoke-waveguide-java-batch.ps1` route;
8. direct-batch vs MCP equality check for parsed metrics on at least one known run.

Until then, the ranking is:

1. Direct Java batch for trusted execution.
2. MCP wrapper for structured project discovery, parsing, audit, and eventually controlled batch execution.
3. `mphserver`/LiveLink for interactive inspection and special cases.

## MCP Documentation Notes

MCP tools are model-invoked operations with schemas. MCP resources expose structured context, such as files or application data, through URIs. Sensitive or state-changing tools should keep a human approval path and validate inputs/outputs.
