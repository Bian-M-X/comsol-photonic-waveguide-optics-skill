# Budgeted device optimization

Read this for an expensive candidate search, not for a simple physics question.
This route shares the main skill's task modes and project-specific prerequisites.

## Choose the representation before the optimizer

| Problem | Start with | Escalate when |
|---|---|---|
| A few meaningful dimensions, bends, coupler lengths/gaps | analytic sensitivity, a small space-filling pilot, bounded local search or GP-EI | measured improvement beats numerical uncertainty |
| Tens of shape variables | shape derivatives with a checked adjoint; otherwise local BO/DFO | pilot shows stable geometry, modes and objectives |
| Hundreds to millions of density variables | filtered/projected density and adjoint + MMA or bounded gradient updates | full forward/adjoint chain passes directional checks |
| Discrete topology/library choices | enumerate a small admissible set, then optimize continuous dimensions | more alternatives have a justified expected benefit |
| Repeated design family with reusable data | calibrated surrogate or feasible latent representation | held-out full-wave evaluations and training amortization justify it |

These are decision guides, not universal dimensional cutoffs. A large population
GA/PSO/NSGA or SPSA is not a default for expensive, smooth, high-dimensional Maxwell
problems. SPSA uses two perturbed objective evaluations per sampled direction;
its variance and constraint handling still need a pilot. BO overhead can exceed
cheap analytic evaluations. Prefer ordinary local optimization in that case.

## Freeze a cost contract

Record objective and constraint definitions, units/scales, input modes, target
band, parameter bounds and fabrication assumptions. Count **failed attempts**, mode
solves, forward/adjoint solves, retries, remeshing, startup, data generation and
validation. Preserve a final validation reserve before search begins. A practical
initial split might allocate 10–20% to pilots and 20–30% to validation; fit the split
to actual costs, rather than treating these percentages as requirements.

For a frequency-domain density iteration, estimate

`cost ≈ Σ_(frequency,corner) [assembly + factorization + (N_forward + N_adjoint)·RHS_cost]`.

The often quoted "two simulations" is per compatible state/objective setup, not
per entire multi-frequency, multi-input, multi-corner campaign. Changes to the
operator require refactorization. Same-operator right-hand sides may reuse it;
see [source sweeps](frequency-domain-source-sweeps.md).

Distinguish symbolic sparsity reuse from numerical factorization reuse. For a
coupled filter/Maxwell Newton system, the material-coupling Jacobian also depends
on the current field: a tiny primal residual does not prove the last factorization
is valid for sensitivities. Require a converged linearization and a gradient
check before relying on reuse. The [native example](comsol-adjoint-inverse-design.md)
records an actual failure and repair. The related
[FDFD caching study](https://arxiv.org/html/2307.05388v1) motivates measuring these
cost components separately; its speedups are not a COMSOL benchmark.

Run a small pilot to measure wall time and peak memory. Compare candidates at an
identical fidelity and compare optimizer baselines under identical total budgets,
starting sets and success criteria. Report variability across seeds when claiming
an algorithmic benefit. A single good winner does not establish superiority.

When process scenarios dominate cost, start with the
[fabrication-aware route](fabrication-aware-robust-design.md): `2d+1` axial points
can screen `d` normalized factors, but mixed interactions require additional
probes. Budget scenario discovery, process-model calibration and gradient refresh
separately. Neither equal axial weights nor one adversarial step certify a
distribution expectation, global worst case or manufacturing yield.

## Runnable low-dimensional proposer

`photonic optimize suggest SPEC --trials TRIAL_DIRECTORY --json` is a **read-only**
ask step. It never runs COMSOL, creates a trial, changes a gate or certifies an
optimum. Existing `optimize run/resume` remain plan-only. Python access:

```python
from photonic_workflow.optimization import spec_fingerprint, suggest_candidate
proposal = suggest_candidate(spec, trials, pool_size=1024, local_radius=0.25)
```

It reuses `OptimizationSpec` and `OptimizationTrial` schema 1.0. Its deliberately
narrow supported subset is:

- 1–20 continuous variables, each exactly `name`, `lower`, `upper`, `unit`;
- one objective, exactly `name` and `sense` (`minimize` or `maximize`);
- up to eight scalar constraints, each exactly `name`, `upper`, positive `scale`;
  an observation is feasible if **every measured value <= its upper bound**;
- an explicit integer seed and total `evaluation_budget` of 2–512 trials;
- `promotion_rule.validation_reserve`: positive integer below the total budget;
- no artificial `failure_penalty`.

Names are ASCII identifiers. Use `unit: "1"` for dimensionless variables. A lower
bound can be represented explicitly as a negated residual. The generic plan
service remains available for other specifications; unsupported suggest inputs
are rejected, not silently reinterpreted.

The proposer uses normalized coordinates, initial maximin Latin-hypercube
candidates, then a small Matérn-5/2 GP with expected improvement and modeled
feasibility. Three quarters of the candidate pool are local to the incumbent;
the rest remain global. A grid of four kernel length scales is selected by
marginal likelihood. A fixed numerical nugget prevents singular duplicate-data
fits; it is **not** a measured solver noise model. Uncertainty and feasibility
probabilities are heuristic and uncalibrated. This is not a TuRBO or qMFKG
implementation. Use a separately adopted BoTorch backend for those methods.

Initialization needs `max(4, 2*d+1)` successful observations. Receipts report this
target, remaining initialization and the possible model-guided slots if remaining
evaluations succeed. For eight variables, total budget 30 and reserve eight, 17
of 22 search slots are initialization and only five use the fitted model. Inspect
this split before spending; reduce meaningful dimension or choose a justified
alternative when the budget is too small. Do not silently spend the reserve.

The complete serialized spec, including fidelity and provenance, is hashed. Each
trial must contain `optimization-spec-sha256:<hash>` in `provenance`, a unique
`stable_id`, unique nonempty `run_id`, exact parameter names, and status
`planned`, `running`, `succeeded` or `failed`. A successful trial needs all declared
objective and constraint values; a failed trial needs a failure class. Invalid,
expired or out-of-envelope results cannot train the surrogate. Preserve the spec
file; recreating it with a new timestamp changes its fingerprint.

Trusted outer-loop sequence:

1. Read the proposal. If `evaluate_candidate`, record a **planned** trial before
   spending compute; single-writer ownership is required.
2. Run the reviewed evaluation using existing authorization, isolated runtime,
   bounded time/resources, and the exact frozen model/metric specification.
3. Complete the same trial with observed values or a failure class. Keep run
   artifact references and hashes; the hash marker alone does not prove truth.
4. Ask again. Pending trials block another proposal. Failures consume budget but
   never become fake high/low objective values. Three repeated identical failure
   classes stop suggestions for diagnosis. Reaching the reserve stops search.
5. Independently replay and qualify winners using the reserved budget.

No concurrent scheduler or persistent optimizer lock is implemented. Different
fidelities, mesh/material/gauge revisions and changed objectives use different
specs. The CLI reads only the specified directory's `*.json` trial files.

`examples/optimization/analytic_coupler.py` demonstrates complete ask/tell and a
matched-budget random baseline without a commercial solver. It is an analytic
software experiment, not a COMSOL device result.

## Stop spending when the decision is resolved

Stop or redirect the next evaluation when the target is achieved at the required
fidelity, improvement is below the numerical error floor, repeated failures need
diagnosis, or only final validation budget remains. A flat surrogate surface is
not proof that no better design exists.

Use [multifidelity and error budgets](multifidelity-and-error-budgets.md) to decide
between a new candidate and refining a nearly tied one. For high-dimensional
design read [adjoint and fabrication](adjoint-and-fabrication.md); for solve cost
read [COMSOL performance](comsol-performance.md). The source-to-decision record is
[inverse-design evidence](inverse-design-evidence.md).
