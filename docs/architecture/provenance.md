# Provenance

Status: Phase A architecture contract

## Purpose

Provenance makes every accepted claim traceable to exact inputs, tools,
transformations, outputs, and acceptance decisions. It is stored as structured
records rather than reconstructed from a console transcript.

## Records

`ArtifactRecord` contains a project-relative path, media type, byte count,
SHA-256, immutability flag, and parent artifacts. `ProvenanceRecord` contains:

- activity and producing tool/version;
- redacted command shape;
- input and output artifact IDs;
- transformations and their parameters.

Adapter/execution-model identifiers, source/configuration revisions, and
permitted environment/capability fingerprints are represented as referenced
input artifacts or typed transformation entries until dedicated contract
fields are added. They must not be presented as first-class fields that the
current model does not contain.

Each run writes `run.json`, `inputs.json`, `artifacts.json`,
`provenance.json`, `events.jsonl`, `acceptance.json`, stdout/stderr, a
checkpoint, and an isolated `runtime/` directory. Structured records are
updated atomically; events are append-only.

## Transformations

The following always create explicit provenance:

- interpolation or extrapolation;
- fitting and error evaluation;
- S-parameter format or convention conversion;
- reference-plane movement or de-embedding;
- port or mode reordering;
- layout normalization and netlist extraction;
- calibration and uncertainty processing;
- simulation-to-measurement correlation;
- compact-model recalibration.

Derived data reference immutable raw parents and the analysis-code hash. Raw
measurement data is never overwritten.

## Trust and redaction

Ordinary records use project-relative paths or aliases. Secrets, license
settings, user names, complete commercial installation paths, PDK contents, and
instrument resource addresses are excluded or redacted. A private local record
may retain required operational detail under the approved root but is not a
public-release artifact.

## Gates and claim boundary

Evidence links and hashes are mandatory for a passing gate. Provenance
completeness supports G8 and all earlier gate audits, but provenance alone does
not prove physics. A succeeded run with failed acceptance remains succeeded and
rejected. Missing, stale, mismatched, or unhashed required artifacts keep the
dependent gate `blocked`.

M1 requires immutable raw-data provenance; M2 adds calibration lineage; M3
links matched simulation and measurement revisions; M4 links a new compact
model release to those records.

## Capability and phases

- **Phase A:** record contracts, hashing, atomic manifests, run lineage,
  transformation vocabulary, redaction, and mock recovery tests.
- **Phase B:** local MATLAB and cross-tool round-trip fingerprints and parity
  evidence.
- **Phase C:** signed releases, external artifact stores, PDK-controlled
  lineage, measurement campaigns, and remote/HPC provenance.

## No-fake boundary

Do not create hashes for artifacts that were not read, tool versions that were
not probed, or success events for work that did not run. A mock artifact must
say `mock`; an unverified capability remains unverified even when its planned
command and expected outputs are fully recorded.
