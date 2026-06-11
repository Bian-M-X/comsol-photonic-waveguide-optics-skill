# Subagent Orchestration For Photonic Simulation

Use this reference only when the user explicitly asks for subagents, delegated work, parallel audit, or multi-agent simulation workflow. Otherwise the main assistant should work directly.

## Core Rule

The main assistant remains the orchestrator. Subagents receive bounded tasks, role instructions, allowed files, expected outputs, and explicit constraints. They should not receive private solver paths, license details, bulky `.mph` files, or unrelated project history unless the user authorizes that exposure.

Before spawning or instructing a subagent:

1. Read this file.
2. Read exactly one matching role file under `agents/`.
3. Define the subagent's write scope or read-only scope.
4. Give a concrete output contract.
5. Keep critical-path work local unless the delegated task can run independently.

## Recommended Roles

| Role file | Use when | Typical output |
|---|---|---|
| `agents/planning-agent.md` | plan a simulation campaign or milestone | task plan, assumptions, success criteria |
| `agents/geometry-modeling-agent.md` | create or revise geometry code | geometry notes, Java/Python patch, length audit |
| `agents/execution-agent.md` | compile/run solver jobs | command log summary, status table, artifacts |
| `agents/code-auditor-agent.md` | review scripts/Java before running | findings with file/line references |
| `agents/model-auditor-agent.md` | review `.mph`/Java model assumptions | material/port/boundary/mesh audit |
| `agents/results-auditor-agent.md` | review spectra, S-parameters, plots | metric validation, anomalies, overclaim risks |
| `agents/data-processing-agent.md` | parse tables and generate summaries | CSV/plot/report-ready metrics |
| `agents/literature-knowledge-agent.md` | gather references or standards | source-backed note with citations |
| `agents/mcp-integration-agent.md` | evaluate or prototype MCP bridge | tool/resource schema and security assessment |

## Safe Multi-Agent Pattern

1. Planning agent drafts the experiment contract.
2. Geometry agent implements or updates model geometry in a bounded write scope.
3. Code auditor reviews the model source before any long solve.
4. Execution agent runs the approved solve with isolated runtime dirs.
5. Data-processing agent parses outputs and produces deterministic summaries.
6. Results auditor checks whether conclusions are supported.
7. Model auditor performs a final physical-consistency pass before reporting.

For short tasks, combine roles locally rather than spawning a full team.

## Constraints

- No destructive filesystem operations.
- No parallel COMSOL batch jobs sharing the same `prefs`, `configuration`, or `tmp` directories.
- No claim of convergence without a declared sweep, mesh, or reference check.
- No publication of local absolute paths, credentials, license files, `.mph`, `.class`, or raw proprietary logs unless explicitly approved.
- Audit agents should fail closed: if data is missing, report missing data instead of inferring success.

## Handoff Template

```text
Role: <role>
Read first: agents/<role-file>.md
Scope: <files/folders allowed>
Task: <single concrete task>
Inputs: <paths, parameters, assumptions>
Do not touch: <files/folders/secrets>
Output: <exact artifact or final message format>
Verification: <checks to run>
```
