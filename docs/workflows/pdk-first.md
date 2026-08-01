# PDK-First Workflow

Status: workflow contract; execution depends on registered local capabilities

## Use when

Use this profile when a licensed or public PDK defines the technology stack,
PCell library, compact models, and signoff decks. Register a `PdkManifest`
alias, version, access class, and fingerprint before selecting components.

## Flow

1. Freeze design intent, ports, band, modes, metrics, tolerances, and intended
   claim.
2. Bind the technology stack, cross-sections, process corners, model library,
   and DRC/LVS deck aliases by stable ID.
3. Create a logical netlist from qualified components.
4. Bind model cards and run pre-layout circuit simulation.
5. Generate layout from the same instances and named ports.
6. Extract connectivity and physical path lengths; compare with the logical
   netlist.
7. Backannotate a simulation netlist and run post-layout analysis.
8. Run authorized DRC/LVS and promote high-risk subassemblies.
9. Evaluate corners, packaging, and test readiness before tapeout freeze.

Every transition creates a new manifest revision and provenance. PDK files and
NDA content remain outside the repository.

## Gates and claim boundary

- G0: complete intent and explicit PDK or surrogate stack.
- G1-G2: qualified port basis and PDK/corner-specific components.
- G3-G4: valid model bindings and pre-layout circuit behavior.
- G5: port-aware layout and extracted connectivity remain the core gate.
  Claims scoped as `PDK/DRC checked` or tapeout add actual selected-PDK DRC/LVS
  acceptance criteria and evidence.
- G6: promoted full-wave evidence for critical interactions.
- G7: declared PDK corners and robustness.
- G8: reproducible evidence package, PDK fingerprint, and limitations.

Before G5, the strongest layout claim is `layout concept`. Passing DRC/LVS does
not prove optical performance, and a circuit pass is not full-wave evidence.

## Capability and phases

- **Phase A:** PDK/design/netlist/model/layout contracts, mock PDK, NumPy
  circuit path, capability descriptors, dry-run plans, and comparison APIs.
- **Phase B:** local layout and numerical fixtures with authorized tools and
  non-confidential test data.
- **Phase C:** real PDK adapters, deck execution, extracted backannotation,
  foundry corners, and tapeout integration.

Unavailable or incompatible PDK, layout, DRC, LVS, or solver capabilities leave
the corresponding step and gate `blocked`; the workflow does not substitute a
different tool silently.

## No-fake boundary

A mock PDK, generated GDS, declared deck alias, or installed layout tool is not
foundry evidence. Do not copy NDA content, invent distributions, interpret
unknown rules, or label a design tapeout-ready without authorized G5 and
tapeout checks.
