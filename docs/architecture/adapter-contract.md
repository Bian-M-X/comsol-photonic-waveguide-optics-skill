# Adapter Contract

Status: Phase A architecture contract

## Purpose

Adapters connect the workflow runtime to external tools without turning the
runtime into a replacement for those tools. An adapter translates versioned
contracts into a bounded plan, probes the local capability, and normalizes
result metadata. It does not own design intent, gate policy, or tool-specific
physics.

## Contract

The target adapter lifecycle is:

1. The registry returns its `AdapterDescriptor` without importing an optional
   SDK or launching a process; a concrete adapter exposes the same descriptor.
2. `check()` returns a `CapabilityReport` based on an explicit probe.
3. `plan()` validates a `RunSpec` and returns an argument-array execution plan,
   expected artifacts, timeout, runtime directory, and redacted command shape.
4. The base `execute()` fails as unavailable; only an implemented and locally
   authorized backend may override it.
5. `inspect()` converts fixed result files into versioned result contracts.
6. `cleanup()` may remove only the current run's transient runtime files.

The Phase A Python interface currently guarantees the descriptor attribute,
`check()`, `plan()`, and a fail-closed base `execute()`. `inspect()` and
`cleanup()` are lifecycle targets, not callable capability, until their methods
and backend-specific tests exist.

`AdapterDescriptor.implementation` and `CapabilityReport.availability` are
separate axes:

- implementation: `implemented`, `experimental`, `planned`, or `unverified`;
- availability: `available`, `unavailable`, `incompatible`, or `unverified`.

An installed executable does not make an experimental adapter implemented, and
an implemented adapter is not available when its licensed dependency is
missing or incompatible.

## Registry and SPI evolution

`AdapterRegistration` binds one descriptor to its optional built-in factory.
Registration is atomic across a provider batch and requires adapter SPI `1.0`;
the descriptor must declare the same SPI and the exact current version of each
named input/output contract. A new SPI version is therefore an explicit
compatibility change rather than a duck-typed import.

Third-party providers publish under the
`photonic_workflow.adapters` Python entry-point group. Third-party SPI `1.0`
is descriptor-only and rejects provider factories; the open-ended internal
`**kwargs` factory is not a published third-party ABI. The default registry
never discovers or imports providers. A project may name reviewed providers in
`adapter_entrypoint_allowlist`, but the CLI loads them only with
`doctor --load-configured-adapters`. Missing, duplicate, malformed, or
incompatible registrations fail the whole provider load without exposing a
partial registry.

The provider batch is atomic at registry commit. Importing the entry-point
module and calling provider code may already have process side effects and is
not rollbackable or sandboxed. See
`docs/providers/authoring-third-party-adapter.md` for literal versioning,
packaging, contract-suite, and release requirements.

## Safety invariants

- Commands are argument arrays and run with `shell=False`.
- No adapter accepts arbitrary shell, Python, MATLAB, Lumerical, or SCPI text.
- Requests carry an audited entrypoint ID; the adapter maps it internally to a
  fixed function handle or script. User-provided function names are not input.
- All inputs and outputs resolve beneath configured allowed roots.
- Commercial execution defaults to dry-run and concurrency one.
- Local paths, user names, license settings, credentials, and instrument
  addresses are redacted from ordinary output.
- Optional dependencies are imported lazily after capability checks.
- A failed operation is recorded once; an adapter never silently retries it.

## Gates and claim boundary

Adapter planning is runtime evidence, not physics evidence. It can support G0
contract preparation and provenance at G8, but it cannot pass G1-G7 by itself.
A successful external process may produce evidence for a gate only after its
artifacts are inspected and the declared acceptance criteria pass. Missing or
unreadable evidence leaves the gate `blocked`.

Backend adoption uses a separate operational-readiness contract:
`BackendAdoptionGateRecord`. It is not a `GateRecord`, does not contain a
`GateName`, and cannot advance G0-G8 or M0-M4. Canonical definitions currently
cover:

- Phase B: `matlab-runtime`;
- Phase C: `matlab-comsol-livelink`, `matlab-lumerical`,
  `matlab-instrument`, `matlab-simulink`, `lumerical`, and
  `real-pdk-drc-lvs`.

Create records with `new_backend_adoption_gate()` or
`new_backend_adoption_gates()`. Each record starts `blocked` with every
canonical required check materialized as its own
`BackendAdoptionCheckRecord`. Record one result at a time with
`record_backend_adoption_check()` and then call
`evaluate_backend_adoption_gate()`. Updating any result resets the decision to
`blocked`; evaluation returns `pass` only when every canonical check is present
exactly once, is `pass`, and carries explicit evidence. A failed check also
requires evidence and produces a failed gate. Required checks cannot be marked
`not_applicable`.

The canonical required-check sets are part of the public compatibility
snapshot. Extend them deliberately and review the resulting snapshot diff;
never remove checks in a persisted record to manufacture a pass.

The supported persistent route is `photonic gate adoption
init|list|inspect|record|evaluate`. Each target has one record at
`verification/adoption/<target>.json`. Initialization uses atomic no-clobber
creation; record and evaluation updates use same-directory atomic replacement;
all derived paths are rechecked against the project roots. Dry-run operations
return the proposed record without changing disk. The Phase-A store is
single-writer per target; serialize callers until a tested lock or
generation/CAS mechanism is added.

For CLI/store updates, pass/fail evidence must name a readable,
project-relative file and the reason must be nonblank. Low-level model helpers
validate structure and nonblank references but cannot establish the semantic
truth of an artifact. Evidence inspection and acceptance remain the caller's
responsibility; manually editing a record is not an adoption test.

## Phase delivery

- **Phase A:** base descriptor/report contracts, registry, bounded check/plan,
  MATLAB and COMSOL planning, mock probes, and descriptors for all named
  optional backends. It also supplies the fail-closed adoption-gate record
  kernel, not backend adoption evidence.
- **Phase B:** backend-specific `inspect()`/`cleanup()` implementations, locally
  licensed smoke tests, and parity fixtures for MATLAB batch, Engine, layout,
  FDFD, RF data exchange, and related tools.
- **Phase C:** narrowly authorized LiveLink, Lumerical, instrument, Simulink,
  optimization, remote, or HPC execution after backend-specific adoption gates.

## No-fake boundary

A descriptor may describe an intended adapter even when no implementation or
local dependency exists. Such an adapter must return `planned` or
`unverified`, never synthetic success. Mock results test contracts only and
must carry a mock source and may not be promoted to physical gate evidence or
backend adoption evidence.
