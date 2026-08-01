# MATLAB Legacy Layout Workflow

Status: experimental legacy-compatibility workflow

## Use when

Use this profile to take custody of an existing MATLAB GDS project,
MatlabGDSPhotonicsToolbox project, GDSII Toolbox project, or audited local
PCell library. MATLAB is a controlled producer; Python contracts remain the
design-state authority.

## Flow

1. Freeze design intent and register the legacy source revision and hash.
2. Probe MATLAB, release, batch support, required toolboxes, local toolbox path
   aliases, MEX fingerprints, and the registered entrypoint ID.
3. Create a `MatlabRunSpec` and review the default dry-run plan.
4. On an authorized machine, run the fixed wrapper in an isolated runtime
   directory and capture `MatlabResultManifest`.
5. Validate the GDS artifact, cell list, bounding box, layer summary, polygon
   count, ports, and waveguide-length sidecars.
6. Normalize/import into a `LayoutManifest`.
7. Inspect with KLayout/GDSFactory, extract a netlist, and compare with design
   intent.
8. Run real PDK DRC/LVS only when authorized.

The workflow never executes an unknown `startup.m`, edits `pathdef.m`, or
compiles an unknown MEX.

## Gates and claim boundary

G0 must exist before interpreting legacy code. Successful MATLAB execution is
only run evidence. G5 requires normalized port-aware layout, extracted
connectivity, and separately recorded DRC/LVS. G6 may be required where legacy
geometry introduces optical interactions. G8 records source, wrapper, toolbox,
MATLAB, GDS, normalization, and inspection fingerprints.

MATLAB-generated GDS is not foundry-ready, and geometric agreement does not
prove optical equivalence.

## Capability and phases

- **Phase A:** MATLAB environment/inventory contracts, safe check/plan,
  controlled wrapper, layout adapter descriptor, mock result and layout
  fixtures, and security tests.
- **Phase B:** licensed MATLAB batch smoke, toolbox capability test, minimal
  non-tapeout GDS, and local KLayout comparison.
- **Phase C:** authorized PDK PCells, real DRC/LVS, backannotation, and tapeout.

Missing MATLAB, toolbox, MEX, layout checker, or PDK capability is returned as
`unavailable`, `incompatible`, or `unverified`; no substitute is assumed.

## No-fake boundary

Do not report a toolbox merely because a directory exists, and do not report a
license from an unexecuted plan. Mock GDS and mock MATLAB results test only the
contract. Unknown layers, ports, or rules remain blocked.
