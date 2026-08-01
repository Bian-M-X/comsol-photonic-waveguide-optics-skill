# Frequency-Domain Source Sweeps

Use this reference when COMSOL numeric ports must produce a complete complex
S matrix, especially when phase, reciprocity, passivity, or group delay will be
claimed. Treat each item below as a fail-closed evidence requirement.

## Contents

- [Freeze The Port Basis Before Solving](#freeze-the-port-basis-before-solving)
- [Audit The Study Without Solving](#audit-the-study-without-solving)
- [Parse Source-Conditioned Columns Correctly](#parse-source-conditioned-columns-correctly)
- [Close Power For Every Input](#close-power-for-every-input)
- [Preserve The Expensive Solved State](#preserve-the-expensive-solved-state)
- [Build Fail-Closed Machine Evidence](#build-fail-closed-machine-evidence)
- [Keep The Claim Boundary Closed](#keep-the-claim-boundary-closed)

## Freeze The Port Basis Before Solving

1. Keep all port excitations in one model instance. Do not rebuild geometry,
   materials, mesh, or boundary modes independently for each source column.
2. Give ports stable numeric names and bind each Numeric Port to its intended
   Boundary Mode Analysis step.
3. Perform a multi-eigenpair census before selecting a branch. Then use a
   separate one-eigenpair selected-mode step per port and record its port name,
   mode index, effective index, selection, orientation, and reference plane.
4. Fix one power normalization for every source, normally 1 W power waves.
5. Fix the arbitrary complex phase of every port mode. In COMSOL 6.4, a Numeric
   Port exposes the mode-phase property `Thetap`; verify the property through
   local version-matched documentation or API readback before relying on it.
6. Align opposite-facing ports only after applying the correct polar/axial
   field reflection. Record electric- and magnetic-field overlaps and the
   applied phase. Do not reuse a phase value from a different geometry,
   wavelength, mesh, or mode branch.

Without this basis contract, retain only gauge-invariant per-column powers.
Do not compute complex reciprocity, singular values, phase continuity, group
delay, or a reusable compact-model matrix from raw ungauged columns.

## Audit The Study Without Solving

Create a dedicated non-solving configuration stage and read back:

- study and step tags;
- exact study-step type;
- source port names and order;
- selected Boundary Mode Analysis bindings;
- source powers, reference planes, orientations, and mode phases;
- absence of mesh, boundary-mode, and driven-solve execution.

For COMSOL 6.4 Java API models, the Frequency Domain Source Sweep study-step
type is `FrequencyDomainSourceSweep`. Do not assume the plausible but invalid
name `FrequencySourceSweep`. Treat this as version-specific knowledge: verify
the local API before porting it to another release.

Run the expensive solve only after this configuration gate passes. Retain
failed API attempts as diagnostic history instead of silently replacing them.

## Parse Source-Conditioned Columns Correctly

A source-sweep dataset may define each `Sij` only at the solution index for
source `j`. For a two-port model, read S11/S21 from source 1 and S12/S22 from
source 2. Generalize the same rule to larger matrices.

- Require every physical `(row, column)` entry exactly once.
- Require `source_solution_index == column`.
- Reject nonfinite values at the physical positions.
- Do not require an entry to be finite under unrelated source indices.
- Do not replace undefined unrelated positions with zero.
- Recompute `abs(Sij)^2` from the printed real and imaginary parts.

This mapping is part of the evidence contract, not a postprocessing detail.

## Close Power For Every Input

For source column `j`, define a documented sign convention and recompute:

```text
modal_fraction_j = sum_i abs(Sij)^2
accounted_fraction_j = modal_fraction_j
  + (signed_nonport_exterior_flux_j + material_absorption_j) / Pin_j
closure_residual_j = 1 - accounted_fraction_j
```

Integrate signed Poynting flux only over finalized non-port exterior faces and
absorption over the intended material domains. Audit operator dimensions,
entity sets, and zero port overlap before the solve. Inside a COMSOL coupling
operator, local `nx`, `ny`, and `nz` may be valid where component-qualified
normal variables are not; verify the expression in its actual operator scope.

Keep a scattering feature's outgoing-power value as an independent crosscheck;
do not substitute it for the signed exterior integral unless equality has been
demonstrated. Treat tiny negative absorption within a declared numerical
tolerance as numerical zero, not physical gain.

## Preserve The Expensive Solved State

- Save a solver-owned model checkpoint immediately after the driven solve and
  before derived-value evaluation. A postprocessor failure must not erase a
  valid high-cost solution.
- If iterative convergence has already failed with Inf/NaN for the same frozen
  system, a preselected direct solver can be a controlled diagnostic route.
  Record factorization count, out-of-core use, peak memory, and source order.
- Confirm whether one factorization is reused for multiple right-hand sides;
  never infer reuse merely from the study name.
- Treat a native class-status sidecar as acceptance evidence only if its
  semantics are proven. Prefer zero process exit, explicit terminal markers,
  fresh exact artifacts, and independent parsing.

## Build Fail-Closed Machine Evidence

Require and hash the exact source, rendered run configuration, model, solver
console, batch log, selected-mode prerequisite, and parser. Record run ID,
source commit, solver version, study type, mesh/DOF census, source order, and
artifact containment.

Independently recompute:

- complex power identities;
- per-input power closure;
- expected reciprocity error;
- largest singular value for passive systems;
- an optional unitarity residual when loss is expected to be negligible.

Test rejection paths for missing completion markers, wrong source-column
mapping, nonfinite values, power mismatch, closure drift, reciprocity drift,
singular-value drift, and incomplete solver-sequence evidence. Prefer explicit
machine markers for critical facts; localized solver logs require tested,
version-tolerant parsing.

## Keep The Claim Boundary Closed

A same-model, common-basis result at one wavelength and one mesh is only a
nominal diagnostic. It does not establish converged insertion loss, reflection
floor, broadband phase, group delay, or reusable component performance.

Before promotion, require tracked mode identity across the declared band,
qualified material dispersion, wavelength checkpoints, PML/boundary evidence,
mesh/domain/substrate/port/length convergence, phase continuity, and a complete
error budget. Keep the governing gate `blocked` until those families pass.
