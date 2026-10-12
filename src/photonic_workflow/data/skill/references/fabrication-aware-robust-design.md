# Fabrication-aware robust inverse design

Use this route when numerical performance survives mesh checks but process
variation, mask correction, or optimizer stagnation becomes the limiting issue.
It extends the [adjoint](adjoint-and-fabrication.md) and
[budget](low-cost-optimization.md) routes; it does not change the frozen native
Hadamard campaign or certify a fabrication process.

## Select the adoption level from available evidence

| Available inputs | Useful next step | Supported conclusion |
|---|---|---|
| Geometry and an EM solver, no process data | Explicit geometric/temperature stress scenarios; low-cost axial screening plus interaction probes | Sensitivity under assumed perturbations |
| Paired masks and measured wafer contours from a stated process | Calibrate a small physics-based process model; test forward predictions and derivatives on held-out devices | Model validity within the calibrated process and geometry domain |
| A qualified process model and repeated design demand | Optimize the mask through that model; compare against direct robust topology/shape optimization | Simulated process-aware performance, followed by independent physical validation |
| Independent fabricated-device samples and a sampling model | Measure pass rates with uncertainty and distribution-shift checks | Statistical yield within that population |

The current 2D Hadamard example is at the first level. Its 19 locked numerical
checks concern wavelength and numerical settings, not 19 fabrication samples.
Its threshold calibration chooses a nominal geometry; it is not etch calibration.
Keep process/model uncertainty separate from mesh/PML/port convergence.

## Form the process-to-optics chain explicitly

Distinguish design controls, the written mask, the developed/etched shape and
the optical material model:

`z -> mask M(z) -> process Phi(M; u) -> geometry/material epsilon(u) -> Maxwell -> J`.

Freeze the units, pixel pitch, orientation, padding, reference planes, protected
access guides and each uncertainty coordinate `u`. A projection threshold is
dimensionless; an etch displacement is a length. Their relationship requires
calibration and is not generally constant along a nonuniform boundary.

For the **smoothed differentiable surrogate**, backpropagate through every map.
Check directional derivatives at both nominal masks and masks reached during
optimization. Straight-through derivatives at hard thresholding are biased
estimators, not derivatives of an exactly binary map. They need separate
evaluation of exported binary candidates. A COMSOL control-field gradient is
not automatically a wafer-pixel gradient: account for interpolation, filtering,
projection and quadrature before transferring a sensitivity map.

The calibrated process map may restrict the search to shapes it predicts are
printable. That restriction is conditional on model validity; it does not prove
foundry DRC, mask-rule compliance or actual fabrication yield.

## Spend the corner budget where it can discriminate

BOSON's axial sampling suggests an inexpensive screening set for `d` declared
normalized uncertainty coordinates:

`A = {0, +e_1, -e_1, ..., +e_d, -e_d}`.

This has `2d+1` scenarios instead of the `3^d` full three-level Cartesian grid.
It is a count of scenarios, not EM solves or a speedup measurement. Each scenario
can require several wavelengths, input states, adjoints and material updates.
The helper `optimization.robustness.axial_scenarios(d)` constructs only this
normalized set; the caller supplies a physically valid mapping to process units.
It neither estimates probabilities nor implements BOSON's adaptive optimizer.

**Interaction counterexample.** For `l(u)=u_1*u_2`, every axial sample has loss
zero, while the joint corner `(1,1)` has loss one. Axial screening therefore
cannot establish the worst case even for this simple smooth function.

A practical extension for our expensive solver is:

1. Freeze the process ranges, admissible correlations, scenario identifiers,
   metric scales, search budget and independent validation reserve.
2. Run nominal and axial probes at the same candidate and fidelity. Map through
   a joint model if coordinates are correlated; reject inadmissible combinations.
3. Add physically plausible mixed-sign pairs and joint perturbations for the
   most sensitive coordinates. Include targeted symmetry-breaking perturbations
   when the nominal design used mirror symmetry.
4. Keep observed violating scenarios in an active training set. Reevaluate them
   on the current geometry; a previously bad corner need not remain the worst.
   Periodically search outside that set and retain the cost of that search.
5. Freeze the winner before independent mixed-scenario/random-field checks and
   target-fidelity validation. A held-out violation triggers a new design cycle
   and a new holdout, not silent tuning against the old holdout.

This active-set policy is an engineering extension, not a BOSON reproduction or
a bound on unsampled cases. Do not replace an existing frozen acceptance suite
with it. Expected loss, worst sampled loss and a distribution tail objective
answer different questions; state which is optimized. Equal axial weights do
not reproduce a physical process distribution. Spatially varying etch needs a
declared covariance/correlation length and random-field truncation check, not
independent pixel noise or uniform dilation alone.

## Preserve corner identity through the objective

PRISM uses a sensitivity-weighted pattern loss and averages predicted corner
images in its stated ILT algorithm. Keep that paper-faithful expression distinct
from the following robustness adaptation.

Suppose `W_+ = W_target + delta` and `W_- = W_target - delta`, with all pixel
values in `[0,1]`. The error of the mean image vanishes, but each image has a
nonzero error. For convex `L`, Jensen gives

`L(mean W) <= mean L(W)`.

Thus a small loss on an averaged geometry is not an upper bound on per-corner
error. Exact opposite-error cancellation in this example requires an interior
gray target. If the target is strictly binary and predictions lie in `[0,1]`,
each pixel's errors have the same sign, so exact cancellation to zero cannot
occur. Underweighting a bad corner still can: for target `0` and three predictions
`0,0,1`, unit-weight fourth-power loss of the mean is `1/81`, mean loss is `1/3`
and worst loss is `1`. This is dilution of a localized scenario failure, not
exact cancellation. Maxwell response
is also nonlinear in geometry; solving an averaged material distribution is
not averaging the responses of separate fabricated devices.

For engineering robustness, compute each `L_c` and each optical response before
aggregation. Use stated probabilities for an expected loss, or a maximum/smooth
maximum for sampled worst-case optimization. The existing `smooth_worst_case`
helper provides log-sum-exp and derivative weights; report actual worst sampled
metrics alongside it. Independent per-corner full-wave acceptance remains needed.

## Use optical sensitivity as a local correction guide

PRISM emphasizes mask regions with large adjoint sensitivity through a weighted
fourth-power pattern error. Our solver-independent helper
`optimization.robustness.weighted_pattern_loss` implements a documented
adaptation for a **single** scenario:

`Gamma_i = 0.5 + |g_i| / max_j |g_j|`, with `Gamma=1` if all sensitivities vanish;

`L = sum_i a_i [Gamma_i (W_i - W_target,i)]^4 / sum_i a_i`.

The returned wafer derivative is
`4 (a_i / sum a) Gamma_i^4 (W_i-W_target,i)^3`, holding the reference sensitivity
fixed. Supply physical area/volume quadrature weights on nonuniform grids;
omitting them means a uniform sample average. The helper uses a weighted mean
rather than the paper's unnormalized sum and states its own normalization rule.
It is not the complete PRISM implementation. In particular, placing `Gamma`
inside the fourth power is different from multiplying an unweighted fourth
power by `Gamma`.

Use sensitivities of the intended optical objective and all relevant input
states/wavelengths. The absolute map loses sign and interference information;
it is a prioritization heuristic, not an optical-error bound. Near a stationary
design, small first derivatives can coexist with large second-order sensitivity.
Refresh or abandon the map when fresh EM checks reverse rankings, topology or
mode identity changes, or mask updates leave the validated neighborhood. Include
those adjoint refreshes in the cost ledger. Pattern similarity cannot replace the
gate's complex transmission, throughput, leakage and phase checks.

Run `python examples/optimization/fabrication_robustness.py` from a configured
checkout for the interaction and corner-cancellation counterexamples. It runs
NumPy only, also covers binary-target dilution, and supplies no native optical
or process validation.

## Calibrate a process model without training-data leakage

PRISM motivates three complementary calibration families: interpretable probes
(width/gap/curvature), controlled spatial-frequency patterns, and target-device
crops. Choose them to expose process parameters and deployment geometry under
the actual metrology budget. Many nearly identical patches do not constitute
many independent calibration devices.

Split train/validation by original mask/device and fabrication run **before**
cropping or augmentation. Overlapping patches from one mask must not cross the
split. Include optimized/corrected masks in a separate test set: optimization can
exploit forward-model errors outside the training distribution. Use sufficiently
large context halos and score only valid interiors; test seams after stitching.
Rotation/flip augmentation is valid only for symmetries of the calibrated process
(anisotropic etch or illumination can break them).

Start with a small identifiable physics-based model when data are scarce. Check
parameter identifiability, forward errors, gradient directions and held-out
optical response, not only image MSE/IoU. A synthetic virtual foundry is useful
for controlled ablations but cannot certify another foundry. No fabrication
digital twin is trained or installed by this skill update.

## Treat loss shaping and relaxed search as controlled experiments

BOSON combines auxiliary violated-constraint penalties, informed initialization
and a temporary mixture of ideal and process-aware objectives. For our gate,
retain throughput and fixed-basis complex amplitude/phase objectives; a good
ratio or normalized fidelity can otherwise reward a nearly dark device.
Additional physical flux/reflection monitors may help only when their derivative
and source/normalization contracts have been verified. A ratio between different
selected channels in a reciprocal structure does not establish an optical
isolator or break reciprocity.

If a verified optimizer stalls, compare a bounded relaxed stage from the same
checkpoint against ordinary continuation under equal total solve budgets.
For `J_p = p J_process + (1-p) J_ideal`, return to `p=1` before selecting a
process-aware winner. Both branches need solves and the correct derivative;
mixing objectives is not a zero-cost optimizer improvement. Changed projection,
controls, mesh or objective weights can invalidate MMA history or gradient
checks. Reevaluate the strict binary/process-aware endpoint independently.
No automatic relaxation, new initialization or process model is inserted into
the qualified Hadamard default by this update.

## Literature and evidence status

- Ma et al., BOSON, [DATE DOI](https://doi.org/10.23919/DATE64628.2025.10993227),
  [author manuscript](https://arxiv.org/abs/2411.08210): process-aware subspace,
  auxiliary objectives, relaxation and axial/adversarial sampling. Their reported
  gains and manufacturability claims remain specific to their models/benchmarks.
- Zhou et al., PRISM, [DOI](https://doi.org/10.1145/3831710),
  [author version](https://arxiv.org/abs/2602.15762): calibration, differentiable
  process modeling and sensitivity-guided ILT. A process model, DRC and optical
  qualification are separate requirements.
- Schul et al., [Inverse design for scalable photonic systems](https://doi.org/10.1038/s41578-026-00915-5):
  select model dimension, representation and fabrication interfaces for the
  physical task. A review's examples are not local adoption evidence. Quantum
  objectives may require Hamiltonians, drives, dissipation and density matrices;
  nonlinear devices need appropriate nonlinear state equations or justified
  coupling/overlap models. A linear classical scattering target is insufficient
  for every such task.

Full-text assessment and project-specific adoption decisions:
[October 2026 review](../docs/research/literature-methods-2026-10.md).
The numerical helpers are software-tested; the process-aware workflow is
guidance pending a declared process model and separate native adoption tests.
