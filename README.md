# Photonic Waveguide Optics Skill and Workflow

[![Python compatibility](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/python-compat.yml/badge.svg)](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/python-compat.yml)
[![Platform compatibility](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/platform-compat.yml/badge.svg)](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/platform-compat.yml)
[![Agent compatibility](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/agent-compat.yml/badge.svg)](https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/actions/workflows/agent-compat.yml)

- **Python compatibility** — lint, generated Java fragment compilation, and the full unit/integration suite on Python 3.11–3.14
- **Platform compatibility** — the same tests on Ubuntu, macOS, and Windows, plus building and installing the packaged wheel in a clean environment
- **Agent compatibility** — skill metadata, agent card structure, and discovery layout for Claude Code, Codex, and ChatGPT

`photonic-workflow` is an installable local Python runtime and Codex skill for
auditable photonic-integrated-circuit design closure. It connects design
intent, PDK aliases, component and compact-model contracts, complex
S-parameter circuits, layout/netlist comparisons, solver plans, optimization,
packaging, tapeout, measurement, provenance, and evidence gates.

The runtime coordinates external tools; it does not replace an electromagnetic
solver, a foundry PDK, DRC/LVS signoff, calibrated measurement, or engineering
judgment. A successful command, import, dry-run, or attractive plot is never
promoted automatically to physics evidence.

> Skill token: `$photonic-waveguide-optics`
>
> Python package and CLI: `photonic-workflow` / `photonic`
>
> Current package version: `0.4.0` (alpha)
>
> Repository: `Bian-M-X/comsol-photonic-waveguide-optics-skill`

## What Version 0.4.0 Provides

| Surface | Current role |
|---|---|
| Installable core | Click CLI, Pydantic contracts, NumPy circuit composition, project configuration, run store, provenance, artifact audit, and G0-G8/M0-M4 ledgers |
| PIC and PDK contracts | Design intent, devices, ports, components, netlists, layouts, PDK/technology/corner models, model cards, packaging, test, tapeout, and measurement records |
| Circuit compatibility | Legacy `assembly.json` 1.0 and long-form complex S-parameter CSV validation/composition |
| Reusable modeling recipes | Versioned, fail-closed circular/Euler geometry, segmented port windows, bulk material dispersion, and common-basis two-port diagnostics distilled from reviewed LT-aMZI workflows |
| External backends | Capability probes and bounded plans; commercial execution remains separately authorized and test-gated |
| MATLAB | Phase A check, inventory, plan, controlled-wrapper, result, and Engine-probe surfaces; real local smoke belongs to Phase B |
| MCP | Dependency-light stdio JSON-RPC transport whose manifest enumerates all registered skill resources and 10 narrow tools; no solver, MATLAB, instrument, or arbitrary-shell execution |
| Legacy entry points | Existing Python and PowerShell commands remain compatibility entry points while package-service parity is regression-tested |
| Research record | Official/project-maintained source surveys for PIC and MATLAB tools with explicit local and physics verification boundaries |

Implementation and local availability are reported separately:

- implementation: `implemented`, `experimental`, `planned`, or `unverified`;
- availability: `available`, `unavailable`, `incompatible`, or `unverified`.

Neither field is a device gate. Only inspected evidence can change a G or M
gate.

## Install

Python 3.11 or newer is required. Install the solver-independent core from a
reviewed checkout:

```powershell
git clone https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill.git
Set-Location .\comsol-photonic-waveguide-optics-skill

python -m pip install -e .
photonic --version
```

The core installs only Click, Pydantic, and NumPy. Optional extras describe
integration families; they do not download commercial products, licenses,
PDKs, MATLAB toolboxes, or instruments:

```powershell
python -m pip install -e ".[layout,circuit,sparams]"
python -m pip install -e ".[dev]"
```

Install optional dependencies only for an approved local workflow and review
their licenses independently. The `all` extra intentionally includes only
redistributable Python packages listed in `pyproject.toml`; it is not a
complete PIC environment.

To install the Codex skill itself, place this repository under a discovered
skills directory such as:

```powershell
$SkillRoot = Join-Path $env:USERPROFILE '.codex\skills\photonic-waveguide-optics'
git clone https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill.git $SkillRoot
```

Restart Codex or open a new task after changing skill discovery locations.

## Five-Minute Solver-Free Start

Create an MZI project, validate it, and inspect its fail-closed status:

```powershell
$ProjectRoot = Join-Path $env:TEMP 'photonic-mzi-demo'

photonic init $ProjectRoot --device-family mzi --json
photonic check --project-root $ProjectRoot --json
photonic circuit validate "$ProjectRoot\circuits\assembly.json" --json
photonic circuit compose "$ProjectRoot\circuits\assembly.json" `
  --output "$ProjectRoot\data\processed\circuit_sparameters.csv" `
  --summary "$ProjectRoot\verification\circuit_summary.json" `
  --json
photonic status --project-root $ProjectRoot --json
```

The bundled fixtures are deterministic analytic examples. They exercise
contracts and network composition; they are not a qualified PDK, fabricated
device, or full-wave validation.

Available initialization profiles are:

- `pdk-first`;
- `layout-first`;
- `custom-device-first`;
- `matlab-legacy-layout`;
- `matlab-assisted-design`.

`photonic.toml` records runtime policy and aliases. Physical geometry,
materials, modes, topology, boundary conditions, objectives, and acceptance
thresholds belong in versioned design and run contracts.

## CLI Map

Run `photonic <group> --help` for the authoritative command schema.

| Area | Command groups |
|---|---|
| Project and recovery | `init`, `check`, `doctor`, `status`, `inspect`, `report` |
| PDK and device data | `pdk`, `component`, `model`, `sparams`, `variation` |
| Reusable modeling | `recipe list`, `recipe inspect`, `recipe render` |
| Circuit and layout | `circuit`, `netlist`, `layout` |
| External planning | `solver`, `matlab` |
| Campaigns and release | `optimize`, `package`, `testplan`, `tapeout`, `measurement` |
| Evidence and security | `gate`, `audit` |

Backend readiness is deliberately separate from device evidence. Initialize,
inspect, and evaluate one backend record at a time:

```powershell
photonic gate adoption list --project-root . --json
photonic gate adoption init matlab-runtime --project-root . --dry-run --json
photonic gate adoption init matlab-runtime --project-root . --json
photonic gate adoption inspect matlab-runtime --project-root . --json
photonic gate adoption record matlab-runtime capability-probe blocked `
  --reason "normal interactive-user probe is pending" `
  --project-root . --json
photonic gate adoption evaluate matlab-runtime --project-root . --json
```

Records live under `verification/adoption/`. Initialization never overwrites an
existing record, and `--dry-run` performs no writes. Pass/fail evidence supplied
to the CLI must be a readable project-relative file; a nonblank reference alone
is not accepted as proof.

JSON responses use a stable envelope with command, status, exit code, data,
warnings, and errors. Important exit codes are:

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

A read-only status command may return code 0 while every evidence gate remains
`blocked`. Execution success and physical acceptance are independent states.

### Reusable Modeling Recipes

The built-in recipe registry turns reviewed LT-aMZI modeling primitives into
stable, inspectable calls without copying project-specific models or claiming
solver acceptance:

```powershell
photonic recipe list --json
photonic recipe inspect geometry.symmetric-euler-bend --json
photonic recipe render geometry.symmetric-euler-bend `
  --input .\examples\recipes\symmetric-euler-bend.json `
  --renderer canonical-json `
  --json
```

Each recipe uses an exact semantic version, explicit units, strict input
validation, deterministic output, and packaged provenance. Only the allowlisted
geometry/port recipes can emit bounded COMSOL Java fragments; rendering is not
solver execution or physics evidence. Each Java fragment also requires an
explicit safe `--instance-id` so multiple MZI arms/routes can coexist without
feature-tag collisions. See `references/modeling-recipes.md`.

## Modeling and Evidence Workflow

Use the lowest-cost model that can answer the declared question:

```text
design intent and claim
  -> straight-waveguide and port baseline
  -> independently qualified component models
  -> complete complex multiport S data
  -> validated circuit and sensitivity
  -> port-aware layout and extracted connectivity
  -> selected promoted full-wave checks
  -> robustness and evidence package
  -> test readiness, measurement, correlation, recalibration
```

G0-G8 track design through evidence packaging. M0-M4 are a separate
post-fabrication track:

| Gate | Required evidence |
|---|---|
| `G0` | Device contract and intended claim |
| `G1` | Port and straight-waveguide baseline |
| `G2` | Component qualification |
| `G3` | Assembly contract |
| `G4` | Circuit behavior |
| `G5` | Layout and connectivity |
| `G6` | Promoted full-wave subassembly |
| `G7` | Robustness and optimization |
| `G8` | Reproducible evidence package |
| `M0` | Test readiness |
| `M1` | Raw-data integrity |
| `M2` | Calibrated measurement |
| `M3` | Simulation/measurement correlation |
| `M4` | Compact-model recalibration |

Missing evidence is `blocked`, not pass. A gate pass requires explicit evidence.

## Phase Boundaries

The phase labels describe integration maturity, not device acceptance:

- **Phase A — reliable local core:** installable package, contracts, safe
  plans, mock fixtures, run recovery, gates, legacy parity, MATLAB
  check/plan surfaces, thin MCP, and public-CI-safe tests.
- **Phase B — authorized local validation:** licensed `matlab -batch` and
  `matlab.unittest` smoke, optional Engine checks, data round trips, legacy
  layout/FDFD/RF fixtures, and local numerical parity.
- **Phase C — bounded external integrations:** COMSOL LiveLink, Lumerical,
  instruments, Simulink, commercial PDK/tapeout, packaging/test execution,
  measurement correlation, and large or remote optimization after
  backend-specific adoption gates.

Files, descriptors, schemas, product listings, imports, and dry-run plans do
not prove Phase B/C execution. A MATLAB FDFD result is not 3D full-wave
evidence; generated GDS is not foundry DRC signoff; solver convergence is not
measurement correlation.

## MATLAB

MATLAB is optional. The default controlled route is `matlab -batch`; MATLAB
Engine is an optional probe and low-latency route, not the workflow authority.

```powershell
photonic matlab check --json
photonic matlab doctor --json
photonic matlab products --json
photonic matlab toolboxes --json
photonic matlab sessions --json
photonic matlab plan .\runs\example\run_spec.json --project-root . --json
```

Phase A planning accepts only registered entrypoint IDs and constructs argument
arrays around fixed repository-owned MATLAB functions. It does not accept
arbitrary MATLAB code. An absent executable must be reported as structured
`unavailable`; an importable Engine package does not prove a compatible,
licensed, trusted session.

In the Phase A runtime, `matlab run` without `--execute` is another planning
surface; real execution and `matlab test` remain fail-closed Phase B hooks.
When a later version enables an explicitly authorized local Phase B
validation, record MATLAB release, product/toolbox inventory, wrapper and input
hashes, result manifest, expected artifacts, tolerance, and claim limits.
LiveLink, Lumerical, instrument, Simulink, and real tapeout workflows remain
Phase C until their own adoption gates pass.

See `docs/architecture/matlab-integration.md`,
`docs/architecture/matlab-security.md`, and
`docs/research/matlab-tool-landscape.md`.

## COMSOL and Other Solvers

Provide your own compatible, licensed installation. The trusted legacy COMSOL
execution path remains the bounded Java API plus batch runner:

```powershell
$env:PHOTONIC_SOLVER_ROOT = 'C:\Path\To\LicensedSolverRoot'

.\scripts\invoke-waveguide-java-batch.ps1 `
  -SolverRoot $env:PHOTONIC_SOLVER_ROOT `
  -JavaFile 'C:\Path\To\ModelSource.java' `
  -OutputFile 'C:\Path\To\OutputModel.mph' `
  -BatchLog 'C:\Path\To\BatchLog.log' `
  -DryRun
```

Review paths, selections, study order, cost, concurrency, expected outputs, and
claim level before removing `-DryRun`. A rendered solver plan is provenance
support, not solver execution or physics evidence.

The official-source tool surveys in `docs/research/tool-landscape.md` and
`docs/research/matlab-tool-landscape.md` distinguish documented capability from
local availability and verified physics.

## MCP Surface

`scripts/mcp_photonic_server.py` is a compatibility launcher for the package
transport. The current version exposes:

- resources declared by one authoritative registry: one server manifest, every
  registered reference document, and every bounded agent role contract;
- 10 tools: `list_allowed_roots`, `create_project_scaffold`,
  `audit_project_artifacts`, `parse_sweep_table`, `validate_contract`,
  `inspect_project`, `validate_circuit`, `compose_circuit`, `gate_status`, and
  the compatibility-named `run_java_batch`.

`run_java_batch` renders a redacted dry-run plan only. MCP never exposes
arbitrary shell/Python/MATLAB execution or real solver/instrument execution.
Read roots and write roots are separate; write operations fail when no writable
root is configured. Installed wheels carry a read-only mirror of all MCP
reference and agent resources, so `photonic-mcp` does not depend on the current
working directory or a source checkout. `PHOTONIC_SKILL_ROOT` remains an
explicit override for a reviewed skill tree.

See `references/comsol-mcp-evaluation.md` for the adoption boundary.

## Legacy Compatibility

Existing interfaces remain supported while business logic moves into the
package:

- `scripts/photonic_assembly.py validate|compose`;
- `scripts/parse-comsol-sweep.py`;
- `scripts/new-photonic-project.ps1`;
- `scripts/audit-simulation-artifacts.ps1`;
- `scripts/invoke-waveguide-java-batch.ps1`;
- `scripts/mcp_photonic_server.py`.

The v1 assembly schema, port order, model-level vocabulary, exact wavelength
grid, long-form complex CSV columns, and six-column composed output remain
compatibility contracts. See `docs/migration.md` before changing an existing
project.

## Validate a Checkout

The public core validation deliberately requires no MATLAB, COMSOL, Lumerical,
commercial PDK, instrument, network API, or cloud account:

```powershell
python -m pip install -e '.[dev]'

python -B -m unittest discover -s tests -p 'test_*.py'
python -B .\scripts\update_contract_surface_snapshot.py
python -B .\scripts\test_photonic_assembly.py
python -B .\scripts\test_numeric_tools.py
python -B .\scripts\test_mcp_photonic_server.py
python -B .\scripts\test_skill_metadata.py
.\scripts\test_powershell_safety.ps1
.\scripts\sync-packaged-skill-resources.ps1
.\scripts\sync-packaged-matlab-resources.ps1
ruff check src tests scripts

photonic --version
photonic audit artifacts . --fail-on-issues --json
git diff --check
```

Before committing a new package surface, stage the intended files and run
`git diff --cached --check`; after committing, run `git show --check --oneline
HEAD`. Plain `git diff --check` does not inspect untracked files.

CI also enforces Ruff and skill metadata schemas, runs the full Windows suite
on Python 3.11-3.14, runs
portable-core tests on Ubuntu and macOS, builds the sdist and wheel, installs
the wheel into a clean environment outside the checkout, reads all MCP
resources, validates packaged templates, and runs `pip check`. A version tag
triggers a fresh release build, SHA-256 inventory, and GitHub build-provenance
attestations. See `docs/maintenance.md` for the release sequence.

When the Codex `skill-creator` validation script and PyYAML are available in
the selected environment, also run:

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .
```

Do not install or mutate a global Python environment merely to make an optional
validator available.

## Documentation Map

`SKILL.md` is the concise operational router. Detailed material lives under
`references/` and `docs/`:

| Need | Read |
|---|---|
| Runtime architecture and phases | `docs/architecture/runtime-design.md`, `docs/roadmap.md` |
| Contracts and adapters | `docs/architecture/adapter-contract.md`, `docs/architecture/design-intent.md` |
| Third-party adapter authoring | `docs/providers/authoring-third-party-adapter.md` |
| PDKs and compact models | `docs/architecture/pdk-model.md`, `docs/architecture/compact-model-lifecycle.md` |
| MATLAB integration and security | `docs/architecture/matlab-integration.md`, `docs/architecture/matlab-security.md` |
| Provenance and migration | `docs/architecture/provenance.md`, `docs/migration.md` |
| Maintenance and compatibility | `docs/maintenance.md` |
| Release history | `CHANGELOG.md` |
| PIC and MATLAB tool research | `docs/research/tool-landscape.md`, `docs/research/matlab-tool-landscape.md` |
| Workflow profiles | `docs/workflows/` |
| COMSOL environment and physics | `references/environment-and-runner.md`, `references/wave-optics-port-models.md` |
| Source sweeps and complex S matrices | `references/frequency-domain-source-sweeps.md` |
| Device and interferometer workflows | `references/device-family-workflows.md`, `references/interferometer-workflows.md` |
| Reusable modeling recipes and provenance | `references/modeling-recipes.md` |
| Hierarchical composition | `references/hierarchical-device-workflow.md` |
| Gates and reporting | `references/verification-gates.md`, `references/optimization-and-reporting.md` |
| MCP evaluation | `references/comsol-mcp-evaluation.md` |
| Sources, licensing, and publication | `references/source-notes.md`, `references/legal-and-trademark-notes.md` |

## Safety, Licensing, and Claims

This repository is an independent workflow aid. It is not affiliated with,
endorsed by, sponsored by, or authorized by COMSOL AB, MathWorks, Ansys, a
foundry, or any other tool vendor. It contains no commercial solver, MATLAB
product, PDK, license file, proprietary model, or vendor dataset. Product and
company names identify optional third-party environments only.

Before publication, remove local paths and usernames, credentials, license
data, instrument addresses, NDA material, proprietary papers/models, `.mph`,
compiled artifacts, raw logs, caches, and unpublished results. Audit the full
artifact tree and review every third-party license. Open-source software does
not grant access to commercial products or foundry PDKs.

The repository's original text and helper code are available under the
[MIT License](LICENSE). Third-party tools, APIs, trademarks, documentation,
models, datasets, and generated artifacts remain subject to their owners'
terms.
