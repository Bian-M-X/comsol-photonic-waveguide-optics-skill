# Tapeout Workflow

Status: contract and freeze policy; foundry signoff is Phase C

## Preconditions

Tapeout assembles already qualified evidence; it is not a shortcut around
missing gates. The Phase A `TapeoutManifest` directly references exact
revisions of the layout manifest, PDK manifest, test plan, and packaging
constraint. Design intent, variants, logical/extracted/simulation netlists,
model releases, signoff reports, promoted evidence, risks, waivers, and owners
remain linked through those manifests, provenance, and the G8 evidence package
until dedicated fields are added.

## Flow

1. Audit G0-G8 and require explicit reasons for every `not_applicable` gate.
2. Verify layout hierarchy, ports, layer map, die/reticle coordinates, coupling
   interfaces, pads, keep-outs, dicing streets, marks, and test structures.
3. Verify authorized DRC/LVS and extracted/logical agreement.
4. Verify process corners, packaging, test readiness, and release artifact hashes.
5. Audit for secrets, NDA leakage, blocked binaries, local paths, and stale
   provenance.
6. Freeze the manifest and artifacts under a new immutable revision.
7. Any later change creates a new candidate; a frozen manifest is never edited
   in place.

## Gates and claim boundary

Tapeout review consumes G0-G8; it does not manufacture passes. G5 is required
for real layout signoff, G6 for identified critical interactions, G7 for the
declared robustness scope, and G8 for the final evidence package. M0 records
test readiness but M1-M4 occur after fabrication.

`tapeout candidate`, `internally reviewed`, and `foundry accepted` are distinct
claims. Only the foundry can supply foundry acceptance.

## Capability and phases

- **Phase A:** `TapeoutManifest`, packaging/test contracts, freeze policy and
  mutation guard, mock fixtures, and audit policy. End-to-end immutability is
  not claimed until service-level tests cover every write path.
- **Phase B:** non-tapeout layout/package/test fixtures on locally available
  tools.
- **Phase C:** authorized PDK decks, real signoff, foundry exchange, packaging,
  and tapeout coordination.

Capability descriptors for GDS generation, DRC, LVS, packaging, or upload do
not constitute completion.

## No-fake boundary

MATLAB-generated GDS, mock PDK, surrogate DRC, or complete-looking metadata is
not tapeout signoff. Do not include NDA content or claim foundry acceptance.
Never modify a frozen tapeout revision in place.
