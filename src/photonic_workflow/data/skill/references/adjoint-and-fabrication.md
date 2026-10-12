# Adjoint gradients and fabrication-aware design

Use for high-dimensional inverse design or for auditing a claimed gradient.
Read the [budget route](low-cost-optimization.md) first only if optimizer choice
or compute allocation is still unresolved. Preserve a paper-faithful baseline.

## State and derivative convention

For a linear discretized state `A(rho) x = b(rho)` and real objective `J`, define
`q = ∂J/∂x*` by `dJ = 2 Re(qᴴ dx) + (∂J/∂rho)_x d rho`. Then

`Aᴴ lambda = q`,

`dJ/d rho_j = (∂J/∂rho_j)_x + 2 Re[lambdaᴴ (∂b/∂rho_j - ∂A/∂rho_j x)]`.

This convention covers complex fields without relying on reciprocity. A
transpose rather than conjugate transpose may appear under another explicitly
derived convention; do not mix them. A complex-symmetric Maxwell matrix is not
generally Hermitian. For nonlinear systems use the Jacobian of the full coupled
residual, including conjugate-field dependence; the simple linear formula is
insufficient. Keep phase/reference planes, modal normalization and objective
weights fixed within a gradient check.

One scalar aggregation can combine several adjoint sources **for the same state
operator**. Different wavelengths, process geometries and incompatible input
states still require their corresponding solves/RHSs. An AD gradient of a compact
circuit is not a gradient of its underlying Maxwell model. Neither this runtime's
GP proposer nor its numerical utilities expose a native COMSOL adjoint backend.

COMSOL's Optimization Module and density-based topology interface are a preferred
licensed route when available; the current vendor metalens tutorial is an adoption
fixture, not a ready-made PIC port/gauge contract. Verify installed products,
version, discretization and gradient support locally before calling the route
available. Meep's adjoint interface is another candidate after separate backend
adoption; do not install a second solver merely to duplicate a working workflow.

## Gradient checks before expensive optimization

Compare `g·v` against `(J(rho+h v)-J(rho-h v))/(2h)` for several real directions
and logarithmically spaced steps, scaled in normalized design coordinates.
Include directions touching the design boundary and fabrication filters. Keep
perturbations feasible and freeze mesh topology, state definitions, modes and
material convention where required. Seek a stable error plateau or expected
Taylor behavior before roundoff/noise dominates. Near a stationary point use
absolute as well as relative tolerances. Remeshing and modal crossings can make
the objective nonsmooth; diagnose rather than shrinking `h` indefinitely.

`optimization.numerics.directional_gradient_check` reports all samples and actual
evaluation count and requires at least two passing step sizes. It does not launch
a solver itself, select physically valid directions, or prove a full adjoint.
Its objective callback may be expensive; include its cost in the pilot budget.

## Continuous-to-fabricable chain

With solid density `rho=1`, a consistent density chain is

`rho -> filter H1 -> projection P(beta1,eta1) -> filter H2 -> P(beta2,eta_corner) -> epsilon`.

The tutorial's Helmholtz filter is
`-(r_f/(2 sqrt(3)))² ∇² rho_filtered + rho_filtered = rho`, with specified boundary
conditions. Its length parameter is not interchangeable with the support radius
of a conic convolution. Projection is

`P(u)=[tanh(beta eta)+tanh(beta(u-eta))]/[tanh(beta eta)+tanh(beta(1-eta))]`.

Differentiate the **entire chain in reverse order**. For a row-normalized conic
filter `H=D⁻¹W`, reverse accumulation is `WᵀD⁻¹g`, not `D⁻¹Wg` at edges.
The NumPy `ConicFilter` and `tanh_projection` implement these specific operations;
the conic filter is a portable reference implementation, not the paper's PDE
filter. Pixel radius must be converted from physical length using the declared
grid spacing. Its boundary convention truncates and renormalizes the kernel.
Explicitly include fixed-material padding when interfaces require it; do not let
filtering redesign ports, PML, access arms or protected material regions.

Continue projection sharpness only when the current stage has stabilized. Record
beta, thresholds, grid, move limits and the exact density mapping. When moving to
a finer mesh, preserve physical filter length and reevaluate gradients. Large
beta does not repair a wrong derivative or guarantee geometric compliance.

If a fixed-beta stage oscillates, first compare smaller move limits from the
same saved controls, with equal evaluation budgets. A published starting point
uses one fifth of the projection's 10–90% transition width; for eta=0.5 this is
`2 atanh(0.8 tanh(beta/2))/(5 beta)`, optionally capped by the previous limit.
This is a candidate heuristic, not a qualified photonic speedup. Very small
limits can obstruct topology changes. See
[Dunning & Wein, Sec. 2.4](https://doi.org/10.1007/s00158-025-03968-2).
Changing beta simultaneously would confound that comparison. GCMMA is a separate
alternative whose inner evaluations must be counted. The native runner exposes
these tuning controls, but the frozen default campaign does not adapt them.

For solid=1, lower eta gives dilation, higher eta erosion. Three projection
thresholds are a process surrogate; `eta +/- 0.2` is not universally a particular
etch bias in nm. Calibrate against signed-distance offsets/process data and check
topology changes. The 2021 tutorial's approximate +/-8 nm pertains to its specific
double-filter settings, not to arbitrary grids or foundries.

Artificial imaginary permittivity can penalize gray material in suitable
transmission objectives. Its sign must match the time convention (passive loss
has negative Im(epsilon) for `exp(+iwt)`). It is a numerical continuation aid, not
measured absorption. Remove it and repeat physical validation on the exported
binary geometry. In absorption objectives it can create the wrong incentive.

### Diagnose a persistent gray-to-binary performance gap

Increasing beta alone does not force an optimized field to become binary. For
the symmetric tanh projection, choose `u_beta = 0.5 + c/beta`; as beta grows,
`P_beta(u_beta)` approaches `(1+tanh(c))/2`, which is strictly between zero and
one for finite c. This elementary counterexample distinguishes a fixed-field
projection limit from a sequence of reoptimized fields.

Measure grayness on the **physical projected density**, using area/volume
weights: `G = mean_w[4*rho*(1-rho)]`. A mean over nonuniform FE nodes is not an
area mean. For `0 <= rho <= 1` and exact thresholding at rho=0.5, the normalized
material discrepancy satisfies
`G/4 <= mean_w[abs(rho-binary(rho))] <= G/2`; this follows pointwise by splitting
at rho=0.5. It is a material-field bound, not a scattering-matrix or fidelity
bound. Interpolation, contour approximation and changed meshes add separate
errors. Compare the same saved field and unchanged phase/port conventions.
The solver-independent helper
`optimization.numerics.density_binarization_metrics(rho, weights=cell_areas)`
reports these statistics and bounds. Without weights it explicitly reports
uniform sample weighting; the caller must supply physical projected densities
and valid quadrature weights or a documented equal-area reconstruction.

If grayness stalls while optical performance improves, consider a controlled
gray penalty, an explicit binarization constraint, or binary shape refinement.
[Ballew et al.](https://doi.org/10.1021/acsphotonics.2c00862)
([author derivation](https://arxiv.org/pdf/2107.09468)) constrain each local
permittivity update to increase a binarization measure with little optimization
overhead. That result concerns their update variables and feasible subproblem;
it is not a guarantee for this example's Helmholtz-filtered control variables
and native MMA. An adoption must include the full mapping derivative and check
the actual post-update binarization and optical objective. A penalty alone also
does not guarantee a binary endpoint. Keep the existing independent binary
geometry solve as the decision test; do not spend the final validation reserve
on a known failing center-point candidate.

## Robust and phase-sensitive objectives

Normalize objective terms and constraint residuals before aggregation. For
corner/frequency losses `l_k` minimize `tau log Σ exp(l_k/tau)`, with shifted
evaluation to prevent overflow. It lies between `max(l_k)` and
`max(l_k)+tau log(N)`; changing sample count changes this offset. Report the actual
worst-case sample, not only the smooth value. The helper `smooth_worst_case`
returns the weights needed for the derivative. Discrete corners do not establish
statistical yield, and narrow resonances require an independent band search.

For a desired transmission block `T`, use complex fields in a fixed basis. A
useful shape score is `|Tr(Tᴴ S)|²/(||T||F² ||S||F²)`, but it is invariant to total
attenuation. `complex_target_metrics` also returns column powers and an
amplitude-sensitive error after removing **one global phase only**. Fit per-port
phases only when real compensators are part of the declared design and include
their losses, calibration and footprint. Report leakage/reflection from the full
S matrix separately.
Include every propagating port mode in the forward boundary problem, even when
the objective uses only a fundamental-mode logical block. Missing terminations
can reflect unwanted modes back into the design and produce a false high score;
adding leakage readout afterward cannot repair that forward solution. The native
Hadamard fixture's default material-index slab needs TM0 and TM1 on each face.
Its analytic coverage check is specific to that fixed slab, not general modal
qualification. Convergence must refine radiating/cladding regions as well as
the design region, and close signed flux for every modal excitation.
For broadband phase/group-delay or circuit interference targets, retain the
physical spectral phase: independently removing a global phase at each frequency
can hide a wrong common delay. Choose the permitted phase alignment from the task.

Classical splitting ratios do not prove quantum-gate fidelity. For indistinguishable
photons in distinct modes, an unnormalized two-photon transition amplitude is
`S_ca S_db + S_cb S_da`. Include occupation normalization for repeated modes,
all declared herald/postselection modes, input distinguishability and loss.
Report conditional process/state fidelity separately from success probability
and collection/detection efficiency. Single-photon intensity propagation through
cascaded postselected CNOT blocks cannot establish deterministic quantum computing.

## Fabrication validation after optimization

Check minimum **solid width and void gap separately**, radius of curvature,
connectivity, minimum area, etch/layer rules and mask discretization on the actual
exported geometry. Curvature bounds alone leave arbitrarily narrow straight
bridges/gaps; filtering plus projection alone can leave tiny features. Re-solve
after contour extraction, polygon snapping, cleanup and binary conversion.
Double filtering is a robustness model, not foundry DRC.

Use a feasible geometry generator or a calibrated fabrication model when repeated
fabrication justifies the setup cost. Straight-through estimators and learned
latent gradients can be biased and need full-wave holdouts. A learned manifold
may exclude better designs. Never call synthetic process corners measured yield.
For process-to-optics gradients, axial sampling with interaction checks,
per-corner loss aggregation and sensitivity-guided mask correction, use
[fabrication-aware robust design](fabrication-aware-robust-design.md). Its
portable helpers do not implement a calibrated process model or replace the
native Hadamard acceptance suite.
See [evidence and current sources](inverse-design-evidence.md) for the four supplied
papers and the 2025–2026 methods motivating these distinctions.
