# Runtime Design

Status: accepted for Phase A

## Decision

The repository has two deliberately separate products:

1. `SKILL.md` and `references/` provide domain routing, modeling judgment,
   verification discipline, and claim boundaries.
2. `photonic_workflow` provides versioned data contracts, the `photonic` CLI,
   run state, provenance, security checks, capability probes, adapters, and
   deterministic numerical operations.

The CLI is the only public business-logic entry point. Legacy scripts and the
experimental MCP server delegate to the Python package or CLI. They do not
maintain independent implementations.

## Dependency direction

```text
SKILL.md and references
        |
        v
photonic CLI
        |
        +--> contracts/configuration
        +--> run store/provenance/gates
        +--> numerical S-parameter and circuit services
        +--> adapter check -> plan -> execute -> inspect -> cleanup
        |
        +--> bounded external tools

legacy scripts ----------------^
MCP dry-run/read layer ---------^
MATLAB fixed entry point <------ RunSpec/Result JSON
```

Domain packages never import Click or MCP. The CLI may import domain services.
MCP calls the same services and exposes only bounded read, validation,
composition, audit, and dry-run planning operations.

## State and evidence

A run records execution and acceptance separately:

- execution: `planned`, `running`, `succeeded`, `failed`, or `cancelled`;
- acceptance: `pending`, `accepted`, or `rejected`.

This allows a tool invocation to succeed while physics acceptance is rejected.
Gate records use `pass`, `fail`, `blocked`, or `not_applicable`; missing
evidence can never be inferred as a pass.

Capabilities use separate implementation and availability fields:

- implementation: `implemented`, `experimental`, `planned`, or `unverified`;
- availability: `available`, `unavailable`, `incompatible`, or `unverified`.

## External execution

- COMSOL Java batch remains the trusted full-wave execution route.
- MATLAB uses `matlab -batch` with a generated, controlled wrapper and a fixed
  package entry point.
- MATLAB Engine is optional and is probed without starting a session.
- Commercial solvers default to dry-run and concurrency one.
- No adapter accepts arbitrary shell, MATLAB statements, function names,
  Lumerical scripts, Python code, or SCPI strings.

Phase A implements contracts, probes, plans, controlled MATLAB batch plumbing,
and adapter descriptors. A descriptor is not evidence that the corresponding
commercial or experimental backend has run.

## Compatibility

The long-form complex S-parameter CSV remains:

```text
wavelength_nm,out_port,in_port,s_real,s_imag
```

The `assembly.json` version `1.0` contract remains readable. Legacy scripts
bootstrap the local `src/` tree when the package is not installed and delegate
to package services. Public GitHub CI uses only core dependencies and mocks;
commercial products, PDKs, licenses, networks, and instruments are not
required.

## Security boundary

All writes resolve beneath configured allowed roots. Generated labels reject
traversal and Windows reserved names. Commands are argument arrays executed
with `shell=False`. Logs and ordinary capability output redact usernames,
license settings, secrets, instrument resource addresses, and full commercial
installation paths. Unknown MEX files are never compiled or run. Frozen
tapeout manifests cannot be edited in place.
