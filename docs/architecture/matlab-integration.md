# MATLAB Integration

Status: Phase A architecture contract

## Role

MATLAB is an optional numerical, legacy-layout, optimization, data-processing,
measurement, and co-simulation backend. Python contracts and the `photonic` CLI
remain the workflow authority. MATLAB does not own project state or bypass the
run, artifact, provenance, and gate systems.

## Execution models

### Batch

`matlab -batch` is the default controlled execution model. It becomes a trusted
local route only after the Phase B smoke, cleanup, result inspection, and
parity checks pass. A `MatlabRunSpec` identifies a registered entrypoint ID,
input RunSpec JSON, result JSON, isolated runtime directory, temporary MATLAB
paths, toolbox requirements, timeout, and expected artifacts. The controlled
wrapper maps that ID to an internal fixed function handle. The adapter emits an
argument array and never concatenates user text into MATLAB code.

The Phase A schema uses `entrypoint_id`. The loader maps only the exact legacy
`entry_function: "photonic.entry"` value to the registered
`photonic.environment.validate.v1` ID and removes the function-shaped field;
every other legacy function value is rejected before planning. Callers never
supply a MATLAB function name.

### Engine

MATLAB Engine is optional for local interactive or low-latency work. Phase A
only probes importability, release compatibility, and shared-session presence.
Connecting to a session requires an explicitly approved identity fingerprint
and an allowlisted function.

### Data exchange

- JSON: control and metadata;
- CSV: tables, curves, and the canonical long-form optical S data;
- MAT v7.3/HDF5: large typed arrays;
- Touchstone: network interchange with explicit optical metadata sidecar;
- GDSII plus `LayoutManifest`: legacy layout output.

Every array exchange records shape, dtype, complex representation, units, axis
order, port/mode order, normalization, reference planes, time convention,
producer version, and SHA-256. Large arrays do not live only in a workspace.

## Adapter family

Phase A defines descriptors for:

- `MatlabRuntimeAdapter`;
- MATLAB Engine;
- GDS/legacy layout;
- FDFD;
- COMSOL LiveLink;
- Lumerical API;
- instrument/measurement;
- Simulink.

RF/S-parameter and optimization contracts are present, but dedicated adapters
remain Phase B and Phase C targets respectively until they are registered and
tested. In Phase A,
the runtime adapter has a factory for `check()` and safe `plan()`, and the
Engine adapter has a probe-only factory. Other descriptors have no runtime
factory. A descriptor does not imply local availability or verified execution.

## Gates and claim boundary

MATLAB output can contribute to a gate only after its result manifest and
artifacts pass independent inspection. MATLAB-generated GDS does not pass G5;
MATLAB FDFD does not establish 3D G6 evidence; optimizer completion does not
pass G7; instrument connectivity does not pass M1-M4. G8 records release,
toolbox, wrapper, input, result, and artifact fingerprints.

## Phase delivery

- **Phase A:** contracts, check/plan, dry-run wrapper, Engine capability probe,
  product/toolbox inventory, mock results, descriptors, and security tests.
- **Phase B:** licensed local batch smoke, `matlab.unittest`, JSON/MAT/HDF5 and
  complex round trips, layout/FDFD/RF fixtures, RF adapter registration, and
  Python parity comparisons.
- **Phase C:** authorized LiveLink, Lumerical, instrument, Simulink, large
  optimization and its adapter, Compiler, or remote/HPC execution.

## No-fake boundary

When MATLAB is absent, checks return `unavailable` rather than fabricated
inventory. Untested local APIs remain `unverified`. MATLAB Runtime is not
reported as full MATLAB, and community toolbox discovery is not proof of
license, compatibility, numerical correctness, or tapeout readiness.
