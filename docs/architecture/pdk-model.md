# PDK Model

Status: Phase A architecture contract

## Purpose

`PdkManifest` is a local index of process capabilities and compatibility, not a
copy of a foundry PDK. It lets workflows bind stable aliases and fingerprints
to technology, PCells, compact models, decks, corners, packaging guidance, and
adapters while keeping licensed or NDA content outside the repository.

## Manifest structure

The manifest records:

- foundry/process alias and PDK version;
- access class, local path alias, and content fingerprint;
- `TechnologyStack`, `LayerDefinition`, and `CrossSection` references;
- PCell and compact-model stable IDs;
- DRC/LVS deck aliases;
- deterministic process-corner IDs;
- backend compatibility and MATLAB support declarations.

Paths in public records are aliases. Private files stay under an approved local
root. A fingerprint proves which local PDK revision was used without exposing
its contents.

`StatisticalVariationModel` is separate from deterministic corners. Distribution
parameters and correlations require foundry or explicitly supplied evidence;
the runtime never infers them from nominal dimensions.

## Lifecycle rules

1. Register an alias and access policy.
2. Probe only metadata permitted by the license.
3. Record version/fingerprint and backend compatibility.
4. Bind component contracts, model cards, layer maps, and decks by stable ID.
5. Freeze the exact PDK fingerprint in each run and tapeout manifest.
6. Create a new revision when the PDK changes; never mutate historical evidence.

## Gates and claim boundary

- G0 requires an explicit process stack or a declared surrogate.
- G2 binds qualified components to a PDK/corner or states that they are generic.
- G5 requires extracted connectivity and real PDK DRC/LVS evidence for a
  `PDK/DRC checked` claim.
- G7 evaluates declared corners or variation models.
- G8 records the PDK alias, version, fingerprint, access boundary, and missing
  signoff evidence.

A mock PDK supports schema and workflow tests only. It cannot pass foundry DRC,
LVS, yield, tapeout, or process-qualified model gates.

## Capability and phases

- **Phase A:** manifest contracts, alias/fingerprint policy, mock PDK, safe
  capability descriptors, and no-PDK/surrogate claim labels.
- **Phase B:** local round-trip and layout checks with user-provided, licensed
  tool installations and non-confidential fixtures.
- **Phase C:** authorized foundry adapters, real decks, statistical models, and
  tapeout integration.

Each backend reports availability and compatibility separately from the
manifest's validity.

## No-fake boundary

Do not vendor, summarize, or reconstruct NDA layers, rules, models, or decks.
Do not interpret unknown rules. Do not call a surrogate or mock PDK
foundry-ready, and do not call successful GDS generation a DRC/LVS or tapeout
pass.
