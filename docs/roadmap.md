# Roadmap

Status: delivery plan, not implementation evidence

## Objective

Evolve the repository into an auditable local workflow runtime for PIC design
closure while retaining the installable domain skill and the trusted existing
COMSOL/S-parameter workflows. The runtime coordinates external tools; it does
not reimplement them.

## Status vocabulary

Every capability reports two independent facts:

- implementation: `implemented`, `experimental`, `planned`, or `unverified`;
- local availability: `available`, `unavailable`, `incompatible`, or
  `unverified`.

Only tests and run evidence may advance these fields. A roadmap entry,
descriptor, importable module, executable path, or dry-run plan is not proof of
execution or physics acceptance.

## Phase A: reliable local core

Phase A targets a solver-independent, public-CI-safe core:

- installable Python package and `photonic` CLI;
- project configuration that contains runtime policy, not hidden physical
  defaults;
- versioned PIC, PDK, run, provenance, gate, MATLAB, packaging, test, tapeout,
  and measurement contracts, including a freeze policy whose full enforcement
  remains test-gated;
- recoverable Run store with execution and acceptance kept separate;
- allowed-root, redaction, injection, MEX, frozen-tapeout, and commercial
  concurrency controls;
- migrated NumPy assembly and COMSOL sweep parsing;
- unchanged legacy `assembly.json` 1.0 and long-form complex CSV compatibility;
- G0-G8 and M0-M4 records with missing evidence fail-closed;
- independent backend-adoption records with confined atomic persistence,
  dry-run lifecycle commands, and readable project-relative evidence;
- MATLAB runtime check/plan, controlled batch wrapper, Engine probe, inventory,
  adapter descriptors, and mock results;
- thin legacy scripts and MCP that delegate to package services;
- mock PDK and deterministic core tests;
- a single package-version source, explicit contract migration registry,
  adapter SPI version, installed MCP resource mirror, and public-surface
  compatibility snapshots;
- architecture, workflow, migration, security, and capability documentation.

### Phase A acceptance

Acceptance requires successful clean-install and CLI smoke tests, legacy MZI
numeric parity, schema round trips, Run recovery, gate semantics, MATLAB-absent
behavior, wrapper-injection rejection, MCP/service parity, security tests,
artifact audit, and reviewed-diff whitespace checks. The built wheel must also
work from outside the checkout, including project templates and all MCP
resources.

Phase A does not require MATLAB, COMSOL, Lumerical, a commercial PDK, network
access, an API key, or an instrument. Their absence must produce structured
`unavailable` or `unverified` results, not failures disguised as passes.

## Phase B: authorized local validation

Phase B uses explicitly licensed local machines and non-confidential fixtures:

- `matlab -batch` and `matlab.unittest` smoke tests;
- optional Engine smoke and session-identity validation;
- JSON/MAT v7.3/HDF5 and complex-array round trips;
- legacy MATLAB GDS capability and a minimal non-tapeout layout fixture;
- KLayout inspection of that fixture;
- MATLAB FDFD and RF/Touchstone fixtures;
- Python/MATLAB numerical comparisons;
- optional direct-tool parity checks that do not require a foundry PDK.

Each test records product releases, toolbox versions, input/output hashes,
error tolerances, and claim limits. Phase B evidence remains local unless
explicitly cleared for publication.

The `matlab-runtime` adoption record keeps these checks separate and defaults
all of them to `blocked`: capability and normal interactive-user-context
probes, dry-run planning, fixed batch and `matlab.unittest` smoke tests,
JSON/MAT v7.3/HDF5/complex-array round trips, legacy GDS-to-KLayout, FDFD and
RF/Touchstone fixtures, timeout/cancellation/orphan cleanup, redaction, result
inspection, and rollback. The contract and checklist exist in Phase A; no
Phase B execution is claimed until real local evidence fills every check.

## Phase C: bounded external integrations

Phase C contains optional, version-sensitive, or physical integrations:

- COMSOL LiveLink for MATLAB and sim-cli parity/adoption;
- Lumerical MATLAB API;
- instrument control and real measurement;
- Simulink and reduced-order co-simulation;
- large MATLAB optimization, parallel, Compiler, remote, or HPC workflows;
- foundry MATLAB PCells, real PDK extraction, DRC/LVS, and tapeout;
- packaging, test execution, measurement correlation, and model recalibration.

Every backend has its own adoption gate: capability probe, dry-run, authorized
smoke, timeout/failure cleanup, redaction audit, result inspection, parity where
applicable, and documented rollback. Commercial concurrency remains one unless
explicitly authorized and isolated.

The serialized Phase C records are independent for
`matlab-comsol-livelink`, `matlab-lumerical`, `matlab-instrument`,
`matlab-simulink`, direct `lumerical`, and `real-pdk-drc-lvs`. Passing one
cannot alter another. Backend-specific checks add native COMSOL Java parity,
direct Lumerical parity, instrument identity and safety, Simulink model-I/O and
claim boundaries, product-specific entitlements, or controlled PDK/deck,
DRC/LVS, extraction, and signoff-scope evidence as appropriate.

## Evidence progression

G0-G8 retain their current meanings from device contract through final evidence
package. M0-M4 remain a separate post-fabrication track. Phase completion does
not automatically pass any device gate. A project advances only on its own
evidence:

```text
intent -> qualified ports/components -> circuit -> layout/connectivity
       -> promoted full wave -> robustness -> evidence package
       -> test readiness -> raw integrity -> calibration
       -> correlation -> compact-model recalibration
```

Claims use the actual evidence level: analytic/reduced, circuit, layout concept,
PDK/DRC checked, 2D EIM, 3D subassembly, full-device 3D, measured, calibrated,
correlated, or recalibrated. These labels are not interchangeable.

Backend adoption status is an operational readiness decision only. It never
implies solver convergence, physical correctness, foundry signoff, or any
G0-G8/M0-M4 result.

## Near-term priorities

1. Introduce typed application use cases shared by CLI, MCP, and legacy shims,
   then split the monolithic Click module without changing its snapshot.
2. Add tested per-run and per-adoption-record locks or generation/CAS
   mechanisms before queues or multiple writers.
3. Keep MCP thin and remove remaining duplicated orchestration logic.
4. Close MATLAB wrapper, inventory, absent-capability, and injection tests
   before any real execution claim.
5. Add optional adapters only through the versioned SPI, explicit project
   allowlist, bounded fixture, and backend adoption gate.

## No-fake boundary

No phase may be marked complete because files or placeholders exist. Mock PDKs,
synthetic measurements, dry-run plans, adapter descriptors, and unexecuted
commercial integrations remain clearly labeled. Missing solver convergence,
PDK signoff, calibration, uncertainty, or parity leaves the associated claim
and gate `blocked`.
