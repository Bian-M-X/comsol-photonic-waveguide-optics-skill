# MATLAB-Assisted Optimization Workflow

Status: Phase A planning contract; real optimization is not core-CI evidence

## Use when

Use this specialization of the `matlab-assisted-design` profile when an
approved MATLAB optimizer, DOE routine, or statistical workflow should call the
unified evaluation API. MATLAB proposes trials; it does not bypass RunSpec,
acceptance, checkpoints, or fidelity promotion.

## Flow

1. Freeze variables, bounds, units, discrete/continuous types, objectives,
   constraints, fidelity, evaluation budget, timeout, seed, failure penalty,
   acceptance criterion, promotion rule, and process corners.
2. Preserve a baseline before search.
3. Probe the requested MATLAB products and optimization method.
4. Render a dry-run for a registered entrypoint ID that the wrapper maps to a
   fixed internal function handle.
5. Create one independent Run for each evaluation and retain every trial.
6. Record solver failures as failed trials, never as valid low-performance
   points.
7. Checkpoint optimizer state and seed for pause/resume.
8. Compare candidates with the baseline and declared constraints.
9. Re-evaluate winners at higher validated fidelity and relevant corners.

Commercial solver evaluations remain serial unless the user explicitly
authorizes isolated concurrency.

## Gates and claim boundary

G0 supplies objectives and physical constraints. G2-G4 establish the validated
evaluation model. G7 requires baseline preservation, solver-noise control,
corner evaluation, and high-fidelity promotion. G8 records all trials,
failures, seed, optimizer/tool versions, and acceptance.

Optimizer termination is not physical acceptance. The best sampled candidate
is not called globally optimal without proof, and nominal success is not
robust/corner-qualified success.

## Capability and phases

- **Phase A:** `OptimizationSpec`/trial/promotion contracts, MATLAB optimizer
  descriptors, capability check, dry-run planning, mock trials, checkpoints,
  and failure semantics.
- **Phase B:** licensed small MATLAB optimization/DOE fixtures and
  Python/MATLAB numeric comparisons.
- **Phase C:** large local, parallel, commercial-solver, multiobjective, or
  remote/HPC campaigns after concurrency and resume validation.

The capability report names the method and required products; a generic MATLAB
installation does not imply that method is available.

## No-fake boundary

Do not fabricate distributions, constraints, objective values, convergence, or
licenses. A mock Pareto front, planned command, or successfully restored
checkpoint is not an optimized device claim.
