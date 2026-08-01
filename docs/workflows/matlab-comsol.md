# MATLAB-COMSOL Workflow

Status: Phase C execution route; Phase A provides contracts and descriptors

## Use when

Use this workflow only when an existing project genuinely requires LiveLink
for MATLAB, MATLAB-driven parameterization, or MATLAB postprocessing that
cannot be handled safely by the preferred native Java batch route.

## Route priority

1. `comsol-native-java-batch` is the trusted default.
2. `sim-cli-comsol` is an optional inspected route.
3. `matlab-comsol-livelink` is optional, commercial, version-sensitive, and
   unverified until local parity passes.

A project may choose a different order only with a recorded reason.

## Flow

1. Freeze model parameters, study/solver tags, ports, datasets, reference
   planes, metrics, tolerance, and expected artifacts.
2. Probe MATLAB, COMSOL, LiveLink, releases, platform, and license availability.
3. Render a default dry-run using a registered MATLAB entrypoint ID.
4. Execute only on an authorized machine, with isolated runtime and checkpoints.
5. Inspect result JSON, model/result hashes, logs, datasets, S parameters, and
   key metrics.
6. Run parity against the native Java batch route using the same model
   parameters, study, port order, datasets, and tolerance.
7. Retain LiveLink as optional until parity and failure-mode tests pass.

## Gates and claim boundary

The adapter probe and dry-run do not pass G1-G7. Full-wave evidence enters the
gate ledger only after a real solver run, source/port-basis audit, convergence,
artifact inspection, and acceptance. A successful LiveLink call with rejected
physics is `succeeded + rejected`. G8 records both MATLAB and COMSOL versions,
wrapper, model source, result hashes, and parity status.

## Capability and phases

- **Phase A:** contracts, `MatlabComsolLiveLinkAdapter` descriptor, capability
  fields, safe plan, and mock result parsing.
- **Phase B:** MATLAB and COMSOL may be tested separately; no LiveLink claim is
  made without the combined local license and parity fixture.
- **Phase C:** authorized LiveLink execution, checkpointing, Java-batch parity,
  failure/timeout cleanup, and adoption decision.

An installed MATLAB or COMSOL alone is not combined capability. Incompatible
releases return `incompatible`.

## No-fake boundary

Do not simulate LiveLink success with mock data, infer a license, accept old API
examples as current, or promote a dry-run/model-open operation to full-wave
evidence. Native Java batch remains primary until parity is demonstrated.
