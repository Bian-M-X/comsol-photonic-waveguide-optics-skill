# Migration Guide

Status: Phase A compatibility contract

## Scope

This guide moves existing users from repository scripts to the installable
`photonic-workflow` package without rewriting valid projects or weakening their
evidence boundaries. Migration is additive: preserve the original project,
review a dry-run plan, and commit a new configuration/revision only after
validation.

## Preserved interfaces

The following remain compatibility contracts:

- `assembly.json` with `schema_version: "1.0"`;
- ordered component ports and external ports;
- v1 model levels remain exactly `analytic`, `reduced`,
  `full-wave-2d-eim`, `full-wave-3d`, and `measured`; expanded
  `FidelityLevel` values are not written into v1;
- `passive` defaults to `true` when omitted, matching the legacy loader;
- `wavelength_unit: "nm"`, `sparameter_normalization: "power-wave"`, and
  `exp(+iwt)`/`exp(-iwt)` time conventions;
- exact component wavelength-grid matching;
- ideal zero-length/zero-loss manifest connections;
- long-form input columns, in exactly this order,
  `wavelength_nm,out_port,in_port,s_real,s_imag`;
- preserved JSON port order and deterministic composed-output row ordering;
- existing six-column composed output including `power`;
- COMSOL sweep text with four or five whitespace-separated numeric columns;
- missing sweep dB is calculated from T21; wavelength direction does not change
  results; plateaus use one endpoint-midpoint extremum; zero/no-peak spectra do
  not emit NaN;
- `scripts/photonic_assembly.py validate|compose` arguments and assembly error
  exit code `2`;
- `scripts/parse-comsol-sweep.py` arguments and legacy CSV presentation;
- `scripts/invoke-waveguide-java-batch.ps1` as the trusted COMSOL execution
  backend;
- G0-G8 meanings and fail-closed evidence rules.

The repository versions of the assembly, sweep parser, project scaffold,
artifact audit, and MCP launchers are now compatibility shims over package
services, with delegation and parity regressions in the core suite. They carry
no independent numerical, parser, audit, or scaffold logic. The bounded COMSOL
PowerShell runner remains an execution backend rather than duplicated domain
logic. Existing project-local copies may continue to run unchanged; new
scaffolds depend on the installed package instead of copying business logic.

## Package installation

After the Phase A install/CLI acceptance tests pass, install from a reviewed
source checkout:

```powershell
python -m pip install -e .
photonic --version
```

If the console entry point or `photonic --version` is unavailable, stop and
report the package as incomplete; do not treat a `pyproject.toml` entry as a
working CLI.

Core installation provides Click, Pydantic, and NumPy only. MATLAB, COMSOL,
Lumerical, GDSFactory, KLayout, SAX, scikit-rf, instruments, and cloud services
remain optional and are discovered by capability probes.

## Project configuration

Add `photonic.toml` at the project root. It records identity and runtime policy:
profile, workspace, PDK alias, adapter defaults, allowed roots, dry-run,
timeout, commercial concurrency, MATLAB aliases, redaction, and artifact
limits. Third-party Python entry points require both a reviewed
`adapter_entrypoint_allowlist` and the explicit
`doctor --load-configured-adapters` switch; loading a project normally does not
import them.

Adapter SPI `1.0` loads third-party descriptors only. Providers declare literal
SPI and per-contract schema versions and must be retested after either axis
changes; they cannot inherit a new host constant and silently appear
compatible. The allowlist authorizes reviewed Python import for diagnosis, not
solver execution. Use `docs/providers/authoring-third-party-adapter.md`.

Do not move physical decisions into this file. Geometry, materials, band,
modes, topology, boundary conditions, thresholds, optimization variables, and
instrument safety limits belong in versioned design or run contracts.

For an existing project:

1. Preserve a clean version-control checkpoint.
2. Render initialization/migration with dry-run.
3. Select the matching profile.
4. Verify the discovered project and allowed roots.
5. Add stable IDs to new contracts without renaming existing artifacts.
6. Ingest legacy artifacts as references with hashes.
7. Run legacy and package paths on the same fixtures.
8. Commit only after numeric and output parity.

Migration never edits a frozen tapeout manifest or immutable raw measurement
data.

All external contracts, including `photonic.toml`, must declare
`schema_version`. Unknown old or future versions stop with incompatible-version
code `4`; a current-version unknown field or enum remains invalid-input code
`2`. Do not remove the version to force a file through current defaults.
Historical schema support must be an explicit, fixture-backed migration in the
central registry. Applied migrations preserve stable IDs and add a provenance
marker; reads never rewrite the source implicitly.

## Assembly and S-parameter migration

`CircuitManifest` and `SParameterDataset` add metadata around the legacy wire
formats; they do not silently alter them. Preserve port order, mode strings,
time convention, normalization, reference planes, and floating-point data.

Legitimate component paths such as `circuits/../components/...` are allowed
only when their resolved target remains beneath the discovered/configured
project root. Absolute paths and escapes outside allowed roots are rejected.

Old CSVs without complete sidecar metadata remain readable as
legacy/unverified data. Add an `SParameterMetadata` record for ports/modes,
normalization, reference planes, time convention, producer version, and hash;
link source runs through inherited provenance until a dedicated source-run
field exists. Do this before using the data as G2/G4 evidence. Do not infer
these fields from a visually plausible trace.

No interpolation is introduced during migration. Components with mismatched
wavelength grids continue to fail validation until an explicit, provenanced
conversion is requested.

## Run and gate migration

Historical commands and outputs may be registered as immutable artifacts, but
their execution or acceptance state is not guessed. New runs separate:

- execution: `planned`, `running`, `succeeded`, `failed`, `cancelled`;
- acceptance: `pending`, `accepted`, `rejected`.

`execution_status` and `acceptance_status` are authoritative. The legacy
summary `status` is a derived compatibility projection and must be kept in sync
by the Run service; readers must not use it as a third independent state. Gate
`blocked` represents missing evidence, while acceptance remains `pending` until
an evaluation is recorded.

Gate records use `pass`, `fail`, `blocked`, or `not_applicable`; a pass requires
explicit evidence. If a historical claim lacks the required artifacts, import
it as `blocked` or `unverified`, not pass.

M0-M4 are new measurement gates and do not replace G0-G8. Existing measurement
files remain uncalibrated/unverified until raw integrity, calibration,
uncertainty, and linkage are recorded.

## MATLAB migration

Legacy `.m` projects are registered by source hash, registered entrypoint ID,
toolbox path aliases, and required products. The runtime:

- probes without inventing inventory;
- defaults to a `matlab -batch` dry-run;
- uses an isolated controlled wrapper and RunSpec/Result JSON;
- changes MATLAB paths only for the owned process;
- blocks unknown `startup.m`, `pathdef.m` changes, arbitrary functions, and
  unknown MEX binaries.

Phase A migration proves contracts and plans only. Real batch, layout, FDFD,
RF, LiveLink, Lumerical, instrument, or Simulink behavior remains Phase B/C and
`unverified` until its local tests pass.

## MCP migration

The Phase A migration target keeps existing MCP tool names as compatibility
aliases and routes them to the same package services used by the CLI. Until a
regression proves that delegation, the current prototype remains an
experimental implementation with duplicated logic and must not be described as
thin. The accepted MCP surface exposes bounded status, gate, card, summary,
validation, composition, audit, and dry-run plan operations. It never exposes
arbitrary shell, Python, MATLAB, solver, or instrument execution.

MCP server version and resource lists come from one registry. A protocol smoke
test is not solver parity and does not promote MCP to a trusted execution
backend. Installed wheels include a read-only mirror of every registered
reference and agent role resource; source and packaged trees must pass the
registry and mirror hash checks before release.

## Exit codes

New CLI commands distinguish:

| Code | Meaning |
|---:|---|
| 0 | success |
| 1 | internal or unclassified failure |
| 2 | invalid input |
| 3 | unavailable capability |
| 4 | incompatible version |
| 5 | execution failure |
| 6 | acceptance rejected |
| 7 | security violation |
| 8 | timeout |

Read-only status commands may exit `0` while reporting blocked gates. A
requested missing backend returns structured JSON and code `3`. Physical
rejection after a successful tool run returns code `6`, not `5`.

## Verification and rollback

Before adopting the migrated path, require:

- schema and JSON round trips;
- legacy MZI and S-matrix numeric parity;
- sweep-summary parity;
- path traversal and redaction tests;
- Run recovery and gate tests;
- no-MATLAB structured behavior;
- MCP/service parity;
- isolated wheel installation outside the checkout, including all MCP
  resources and project templates;
- artifact audit and `git diff --check`.

Keep the pre-migration commit/tag and original artifacts. Rollback restores the
old invocation and configuration; it must not delete newly produced evidence.
Any semantic difference is documented as a new revision rather than hidden by
format conversion.

## Phase and claim boundary

- **Phase A:** package, contracts, shims, compatibility tests, safe plans, mocks,
  and documentation.
- **Phase B:** optional licensed local MATLAB/data/layout fixtures.
- **Phase C:** commercial solver, PDK, instrument, tapeout, and correlation
  integrations after adoption gates.

Migration success means the workflow and data are reproducibly represented. It
does not mean the device passed G0-G8, the measurement passed M0-M4, or any
optional backend was executed. Mock and unverified evidence stays labeled.

## No-fake boundary

Do not convert missing historical metadata into asserted facts, mark imported
artifacts accepted without their original evidence, or report an optional
adapter as verified because migration created its descriptor. Compatibility
means the old behavior is preserved and auditable; it is not a new physics,
solver, PDK, MATLAB, measurement, or tapeout claim.
