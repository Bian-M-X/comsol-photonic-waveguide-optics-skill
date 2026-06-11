# COMSOL Automation And MCP Evaluation

Use this reference when deciding whether to run COMSOL through Java batch, an interactive server, LiveLink-style APIs, or a future MCP server bridge.

## Current Recommendation

| Route | Status | Use as | Reason |
|---|---|---|---|
| Java API source + `javac` + `comsolbatch` | Stable local default | First choice | Reproducible, scriptable, easy to log, good for long runs and CI-like workflows |
| `mphserver` / LiveLink-style interactive control | Useful but stateful | Backup or exploratory | Good for interactive inspection, but more fragile for unattended runs and environment setup |
| Custom MCP server bridge | Experimental | Future research path | Promising for tool discovery and structured resources, but needs careful security, licensing, and process isolation |

As of the 2026-06 skill update, no verified, project-ready, off-the-shelf COMSOL MCP server was found in the quick public search. Treat MCP as a design direction, not the current primary execution backend.

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
7. comparison against the current `scripts/invoke-waveguide-java-batch.ps1` route.

## MCP Documentation Notes

MCP tools are model-invoked operations with schemas. MCP resources expose structured context, such as files or application data, through URIs. Sensitive or state-changing tools should keep a human approval path and validate inputs/outputs.
