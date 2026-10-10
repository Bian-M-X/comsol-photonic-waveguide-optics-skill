# Native COMSOL Hadamard inverse design

This example starts from a uniform control field, optimizes a compact four-arm
device with native adjoint/MMA, builds a **binary silicon/cladding geometry**, and
independently solves every source. It needs this repository, Python, and local
COMSOL with Wave Optics and Optimization licenses. No MATLAB, LiveLink, cloud
solver, training dataset, downloaded optimized geometry, or GPU is required.

The executable backend is original Java in `HadamardNative.java`. The public MCP
solver adapter remains plan-only; `run.py --execute` is the local execution route.
Currently the runner supports Windows and was exercised on COMSOL 6.4.0.293.

For a wheel-only installation, copy the packaged example to a new writable
directory using `importlib.resources`. Install the matching
`photonic-workflow[inverse-design]` runtime, then run:

```python
from importlib.resources import as_file, files
from pathlib import Path
import shutil

resource = files("photonic_workflow").joinpath("data/skill/examples/comsol-hadamard-inverse")
with as_file(resource) as source:
    shutil.copytree(source, Path("hadamard-example-new"))
```

The target must not already exist. After
extraction, run `python YOUR_EXTRACTED_DIRECTORY/campaign.py --output NEW_RUN_DIRECTORY`;
the checkout-relative commands below apply to a complete source tree. The campaign
prepends its sibling `src` directory to its child processes' import path; wheel-only
extraction uses the matching installed runtime. Standalone analyzer/plot commands
use the runtime selected by their Python environment. For an independent snapshot
test, check the resolved `photonic_workflow.optimization.hadamard.__file__` in the
same environment as the analysis subprocess and verify its hash. An unrelated
editable installation must not silently supply the runtime for a frozen-source claim.

The selected binary design is qualified within the declared **2D bulk-index
surrogate** scope as of 2026-10-10. The
[qualified showcase](../../docs/showcases/hadamard-2d/README.md) records all
nineteen locked checks and thirteen convergence comparisons, plus an independent
completion audit recomputing the metrics from raw 8×8 outgoing/incoming matrices
and signed flux. Across the nineteen checks, minimum all-input target throughput
is at least 0.9246576286 and six-state conditional fidelity is at least
0.9995299555. Seven discrete wavelengths do not establish continuous-band
performance, a 3D stack or fabrication acceptance. Six-state fidelity and the
paper's measured Hadamard fidelity are different metrics.

GPT-6.1-sol independently authored the reproduction drivers and produced the
uniform-start design lineage, continuation checkpoints and bounded threshold
calibration. The final nineteen-check driver was frozen before execution. The
root agent launched that exact unchanged driver after the initial subagent
authorization review lacked direct user quotations, then the independent agent
audited completion. This qualifies the selected lineage and locked mask, rather
than asserting a new uninterrupted run of the revised default campaign. Cost
figures for this lineage exclude earlier research and debugging attempts.

An earlier four-channel binary calculation gave approximately 94.7% fundamental
throughput, but omitted the propagating odd-mode termination. Rechecking the
same mask with two modes per face reduced fundamental throughput to about 75%,
with about 15% in higher modes. The earlier single-point result is invalid as
final acceptance or a performance showcase. Adding missing ports changes the
boundary problem; merely measuring extra output channels afterward is insufficient.

## Reproduce from a uniform initial design

Install the optional scientific dependencies with your chosen Python interpreter:

```powershell
python -m pip install -e ".[inverse-design]"
$env:PHOTONIC_SOLVER_ROOT = 'YOUR_COMSOL_MULTIPHYSICS_DIRECTORY'
python examples/comsol-hadamard-inverse/campaign.py --solver-root $env:PHOTONIC_SOLVER_ROOT --output D:\PhotonicRuns\hadamard-new
python examples/comsol-hadamard-inverse/campaign.py --solver-root $env:PHOTONIC_SOLVER_ROOT --output D:\PhotonicRuns\hadamard-new --execute
```

Replace the solver and output paths with local paths. The first invocation shows
the plan and does not create a run or consume a license. The second uses one
licensed worker, eight CPU threads by default, bounded native jobs, and a fresh
output directory. Do not start another licensed campaign concurrently. A failed
solve keeps its logs and checkpoint; it never becomes a successful receipt merely
because COMSOL returns exit code zero.

The campaign performs six full-chain directional gradient checks: one at each
training wavelength and a second spatial direction at 1550 nm. Its coherent
continuation recipe preserves the independently exercised restart boundaries:

| Job | Beta | Maximum outer iterations | Restart source | Core mesh |
|---|---|---:|---|---|
| `warmup` | 2 | 8 | Fresh uniform control field | 45 nm |
| `coarse` | 2 | 32 | `warmup/final.mph` | 45 nm |
| `projection` | 4, 8 | 40 each | `coarse/final.mph` | 45 nm |
| `sharpen` | 16 | 40 | `projection/final.mph` | 45 nm |
| `fine` | 32 | 40 | `sharpen/final.mph` | 25 nm |

Eight iterations followed by a restarted thirty-two are distinct from an
uninterrupted forty-iteration MMA run: the optimizer's history is reset.
The `coarse` restart explicitly sets `reconfigure_restart: true`, regenerating
the optimization solver from the saved control field as in the exercised
lineage. The remaining continuation restarts retain the checked solver setup.
The native per-stage evaluation stop thresholds are respectively 9, 33, 41,
41 and 41; observed evaluation counts are checked before further jobs proceed.
The control-change criterion can stop a stage earlier.
The physical Helmholtz filter radius is 50 nm throughout. These mesh values
are size settings; inspect the actual native mesh/DOF in each log.
The coupled filter/Maxwell solve uses full Newton steps and a fresh Jacobian
on every iteration, with **solution-error termination**. A small primal residual
alone can leave the sensitivity solver reusing the preceding field's material
Jacobian. A controlled PML diagnostic exposed that failure and passed both
finite-difference step sizes after tightening this termination criterion; the
startup checks verify it again for the actual campaign.
All optimization stages use the minimum objective over 1520, 1536.61, 1550,
1565 and 1580 nm, two guided modes per physical face, a 3.15 μm port reference
distance, a 1.5 μm port half-window and a 100 nm cladding mesh. The campaign uses
`objective_profile: "coherent"`, `fidelity_weight: 10`, MMA with move limit 0.05,
and `boundary_model: "slit_pml"`. Binary validation explicitly retains the
`state_floor` profile to require the measured mirror-symmetry check as well as
the actual two-input throughput floor. The standalone runner retains a separate legacy
diagnostic default; copy the campaign's generated configuration when running
an individual stage. Gradient diagnostics use individual frequencies; the MMA
minimum aggregation is separately checked by native configuration readback and
recorded per-frequency objective values.

Binary geometry is the threshold contour of the **filtered field** `theta_f`,
sampled on a 5 nm contour grid. A bounded scalar correction of the contour
threshold uses new COMSOL solves to balance the two outputs. This is a second
optimization stage with its own recorded evaluations, not postprocessing the S
matrix or fitting port phases. Every threshold changes the physical geometry.
No small islands, holes, or bridges are silently removed.
The six-candidate budget starts at thresholds 0.5, 0.495 and 0.505. Subsequent
secant proposals use observed imbalance values, a maximum step of 0.02 from
the best observed finite imbalance, and bounds [0.44, 0.53]. A sign bracket
takes priority and confines interpolation to that bracket. These are search
parameters; acceptance thresholds remain fixed. Stop early only when full
acceptance passes and the absolute logarithmic imbalance is at most 0.02.

After selecting a passing geometry, the campaign freezes its mask. Nineteen
reserved runs check seven discrete wavelengths (five training points and
holdouts 1543.3/1572.3 nm), core/cladding mesh refinement, a larger domain and
port window, stronger/thicker PML, and a second modal-measurement plane. The
exact configurations and comparison pairs are in the solver-free plan.
The maximum is **36 native jobs**: six gradients, five optimization jobs, up to
six binary calibrations, and nineteen reserved validations. Each continuation
job contains multiple MMA iterations and frequency solves; job count is not a
Maxwell-solve count.

The 1536.61 nm result exposed a defect in an earlier three-point campaign and
is now explicitly a training point. It is no longer an untouched holdout.
Reserved checks do not tune the locked mask. A failure requires a separately
recorded design iteration. Seven sampled wavelengths and selected convergence
comparisons do not prove continuous-band performance. Read `campaign.json`,
each `verification.json`, and the native receipts.

## Run or recover individual stages

`run.py` accepts a JSON configuration. For individual stages, use the complete
configuration emitted by `campaign.py`; a minimal optimization example is:

```json
{"mode":"optimize","iterations":40,"stages":2,"beta":4,"mesh_um":0.045,"training_band":"five","fidelity_weight":10,"objective_profile":"coherent","boundary_model":"slit_pml","optimizer":"mma","move_limit":0.05,"evaluation_limit":41}
```

```json
{"mode":"optimize","iterations":40,"stages":1,"beta":16,"mesh_um":0.045,"training_band":"five","fidelity_weight":10,"objective_profile":"coherent","boundary_model":"slit_pml","optimizer":"mma","move_limit":0.05,"evaluation_limit":41}
```

These illustrate adjacent stages, not a complete fresh campaign: the first
requires the completed beta-2 coarse checkpoint; the second uses
`--restart FIRST_RUN/final.mph`. Use the plan for every required setting and
restart. A restart checks
frequency, materials, filter length, geometry and control-field identity before
transferring the field. The study's `topo.optobj` is a StringMatrix
`[[expression]]`; the generated Optimization solver's `optobj` is the String
scalar `all_obj_contrib`. Check solver `objcontrib=all`, `control=topo` and
aggregation (`min` for a frequency set, `auto` for single). Maximization is
checked on the study's `objectivetype`, not on the generated solver. Preserve
the source checkpoint and physical profile; incompatible checkpoints fail closed.
For a separately recorded optimizer comparison, the runner accepts `optimizer`
(`mma`, the default, or `gcmma`), `move_limit` (default 0.05, range 0.0001–0.2),
and `evaluation_limit` (default 1000, range 2–5000). This sets the native
per-stage `nsolvemax` **stop threshold**, not a strict evaluation cap: COMSOL can
finish an inner loop before stopping. The local 2026-10-04 GCMMA discriminator
requested/read back 20 and finished at `nEval=26`, outer iteration 5, with
accepted `nEval` history `1,3,7,14,19,26` and `Inner` history `-,2,4,7,5,7`.
The same-seed reduced-move MMA run used 11 evaluations for 10 outer iterations.
`nEval` includes the initial evaluation and rejected inner-loop evaluations;
outer iterations alone do not measure the evaluation cost.

The runner records `optimization_cost` from the `batch.log` optimization table
`Iter Inner nEval Error Objective MaxInfeas`, separately from Newton tables.
It retains each stage's accepted rows, rounded printed objective, actual
evaluations, outer iterations and summed `Inner` counters. Counts reset at
continuation stages. An interrupted stage's last accepted `nEval` is a lower
bound; work after that row may be unreported. The total observed band evaluation
count and nominal training frequency-state count (`nEval` summed across stages
times the training frequency count, one training source per frequency) exclude
the later eight-source 1550 nm validation and do **not** count all adjoint,
Newton or linear solves.

Verified trace counts are accumulated before execution or physical acceptance,
including failed attempts. An interrupted job is marked `partial_lower_bound`;
an interruption before the next stage's first row preserves the completed prefix.
Missing receipts, changed artifact hashes, or inconsistent traces give an
explicit `unknown_optimization_jobs` count instead of an assumed zero cost.
Aggregates containing incomplete or unknown attempts are marked as lower bounds.

Each newly generated optimization stage also emits the complex target-mode
amplitudes as `TRAINING_MODAL` rows, before configuring validation sources.
The campaign binds these rows to the receipt and frequency grid, recomputes
throughput, coherent and state-floor objectives, and checks agreement with the
native training objective. This enables fair common-objective comparisons
without opening an MPH in another licensed batch. Legacy logs lacking these
amplitudes explicitly report unavailable components. The derived mirror
all-input throughput is a symmetry surrogate; the independent full matrix
analysis remains the physical acceptance test.

The campaign checks the hashed batch log against the receipt trace, requires
all requested stages to finish, and checks the final rounded objective against
the independent training minimum. If actual per-stage `nEval` exceeds the
requested threshold, it retains the completed execution receipt and physical
analysis, records `cost_overrun` (CLI exit 3), and stops further native jobs.
It does not turn a cost overrun into a physical failure. This check is after
execution and cannot prevent the overshoot within that job. Wall timeout and
outer-iteration limits remain independent bounds; no hard evaluation cap is
claimed. These options are read back after initial setup
and restart, and bound to the campaign's requested settings. They do not change
the physical acceptance criteria. The default campaign keeps its original MMA
settings; alternate settings require a new, budgeted comparison with the same seed.

If export fails
after optimization, `mode: "frozen"` with the checkpoint's exact beta, mesh and
physical parameters recreates eight-source validation without running MMA again.
Frozen export evaluates 1550 nm; it does not certify all trained wavelengths.

If a process stops during continuation, first check that no old solver remains.
Keep the interrupted directory unchanged. Match a saved `stageN.mph` to its
completed `TRAINING_MINIMUM` record, and record the checkpoint, source, plan and
log hashes in a separate recovery manifest. A progress percentage alone does not
identify a completed stage. Start a **new** run directory with `--restart`, the
next beta, remaining stage count and unchanged physical/training settings. For
example, recovery after the completed beta-8 stage uses beta 16 and one stage
before the ordinary fine-mesh job. This transfers the control field and restarts
MMA; it does not restore its internal iteration history or promise a bitwise
identical trajectory.

The campaign CLI has no automatic resume flag. An explicit recovery driver can
reuse the example's `Campaign.native` and `Campaign.qualify_binary` methods;
retain verified prior gradient receipts and the original uniform-start lineage.
Count the interrupted attempt and replacement job in a revised, declared recovery
budget. Do not manufacture a completed receipt for the interrupted job or discard
its elapsed cost. Every selected binary mask still requires the unchanged locked
validation suite. If solver physics, objectives or gradient implementation change,
previous gradient checks do not qualify the changed model.

```powershell
python examples/comsol-hadamard-inverse/run.py --config stage.json --output D:\PhotonicRuns\stage-new --execute
python examples/comsol-hadamard-inverse/extract_mask.py D:\PhotonicRuns\stage-new\density.txt --threshold 0.5 --output D:\PhotonicRuns\mask-new
python examples/comsol-hadamard-inverse/run.py --config binary.json --mask D:\PhotonicRuns\mask-new\mask.json --output D:\PhotonicRuns\binary-new --execute
python examples/comsol-hadamard-inverse/analyze.py D:\PhotonicRuns\binary-new
python examples/comsol-hadamard-inverse/plot_results.py --run D:\PhotonicRuns\binary-new --mask D:\PhotonicRuns\mask-new\mask.json --output D:\PhotonicRuns\figures-new
```

Here `binary.json` contains
`{"mode":"binary","mesh_um":0.025,"boundary_model":"slit_pml","objective_profile":"state_floor","fidelity_weight":10}`.
A field image
is a source-1, peak-normalized visualization, not a substitute for port power.
The plot checks the solved-domain bounds, crops PML/backing regions at the slit
planes, and normalizes only the retained physical window. Its displayed PASS/FAIL
belongs to that single run; campaign qualification requires all locked checks.
The verifier checks receipt hashes, source-conditioned complex S, signed outward
flux, source normalization, and native boundary/PML configuration. Keep MPH, class files and raw
logs outside the source tree. Only compact original summaries/masks/figures should
be considered for publication after inspecting their contents.

## Optical problem and acceptance

The design region is 1.3 × 1.3 μm²; 400 nm access guides attach to left, bottom,
top and right, in that port order. Ports 1/2 are inputs and 3/4 are outputs.
In-plane electric fields and out-of-plane magnetic fields use nondispersive
relative permittivities 12.1 and 2.1. This is a **2D material-index surrogate**,
not a calibrated effective-index or full 220 nm SOI model.

All analytical fundamental-mode port profiles have positive real centre amplitude
and zero phase offset, fixed before optimization. The target is
`B=[[1,i],[i,1]]/sqrt(2)`, equivalent to the Hadamard under the fixed known phase
plates `D=diag(1,-i)`, `D B D = H`. No independently fitted input/output phases are
allowed. Two guided modes per face give eight modal ports, ordered TM0
left/bottom/top/right followed by TM1 left/bottom/top/right. Eight-source
validation exports the full 8×8 S matrix in one model. The logical block still
uses fundamental inputs 1/2 and outputs 3/4; higher modes remain observed leakage.
For the mirror-symmetric logical matrix `T=[[a,b],[b,a]]`, all-input minimum
throughput is `eta-2*abs(real(conj(a)*b))`, where `eta=abs(a)^2+abs(b)^2`.
The `state_floor` objective uses the conservative smooth expression
`eta-sqrt(4*real(conj(a)*b)^2+1e-8)-10*orthogonal_power`.
This penalizes unequal losses for coherent inputs as well as the wrong gate
phase. Validation recomputes the smallest singular value squared of the actual
two-column matrix and checks the mirror assumption; it does not infer the second
column from the first. This is an application of standard singular-value
analysis, not a new mathematical theorem.

## Radiation termination and modal readout

The campaign uses internal, domain-backed slit ports and a mapped Cartesian PML
ring. The access guides continue unchanged through the PML. The typical PML
wavelength is explicitly `c_const/freq/sqrt(eps_clad)`, spatially uniform across
core and cladding. An earlier default material-dependent stretch produced
unacceptable incoming-mode contamination; increasing its thickness alone did
not resolve that diagnostic. Each final design still needs the reserved PML and
domain-size checks.

The full eight-source matrix is measured on an independent source-free contour,
0.2 μm inside the slit planes. Power-normalized analytic TM modes and both electric
and magnetic fields separate incoming and outgoing amplitudes. Known propagation
phases restore the slit reference planes. The verifier retains the raw outgoing
matrix `A` and incoming matrix `B`, requiring `norm(B-I,2) <= 0.005` before treating
`A` as an approximate scattering matrix per nominal 1 W/m source. It never
substitutes `A @ inv(B)` to rescue a failing result. The 0.4 μm contour check tests
this readout independently of the optimizer. These formulas are specific to
lossless guides with real analytic modes; general lossy/leaky modes need a
different mode normalization and dual-basis treatment.

| Engineering check | Required value |
|---|---:|
| Worst conditional fidelity over six canonical single-photon states | ≥ 0.987 |
| Conditional normalized Choi overlap | ≥ 0.987 |
| Minimum target fundamental-mode throughput over every normalized logical input, `sigma_min(T)^2` | ≥ 0.90 |
| Top/right output power ratio, each input | 0.9–1.1 |
| Observed passivity/reciprocity tolerance | 0.005 |
| Signed closed-surface residual, each source | ≤ 0.005 of incident power |
| Incoming eight-mode matrix, `norm(B-I,2)` | ≤ 0.005 in complex amplitude |
| Mirror-matrix residual for `state_floor` | ≤ 0.005 in complex amplitude |
| Mesh/boundary stability: throughput / fidelity / split ratio | ≤ 0.005 / 0.002 / 0.02 absolute |

These are declared engineering criteria. He et al.'s
[Science Advances paper](https://doi.org/10.1126/sciadv.adg6685) reports experimental
Hadamard fidelity 0.987(3) with a different basis-state overlap definition; it does
not report a numerical Hadamard throughput floor. Its
[author manuscript and supplement](https://arxiv.org/pdf/2309.04895), especially
Fig. S2 and S1–S8, supply the cross geometry, material parameters and three design
wavelengths. This example makes a performance-target comparison, not an exact
reproduction of the experimental process.

The verifier checks analytic bound-mode coverage using normalized slab frequency
for the fixed 400 nm symmetric guide. It rejects a four-channel declaration for
the default material stack. This is not a general cross-section mode-completeness
proof. Signed flux is checked for all eight sources at 0.005 tolerance; unresolved
modal/flux differences are not automatically assigned to absorption or radiation.
Refining cladding from 220 to 100 nm reduced an observed maximum closure residual
from about 1.5% to 0.28%; core refinement alone is insufficient.
The example has no measured fabrication model, minimum-feature DRC,
3D vertical-radiation qualification, or experimental quantum tomography.

For adaptation, read [the native adjoint route](../../references/comsol-adjoint-inverse-design.md)
and [the method review](../../references/inverse-design-evidence.md). A new stack,
port family, physical filter, polarization or objective requires its own forward
and gradient checks; demonstrated API calls are not evidence of general validity.

## Symmetry-preserving binary extraction and bound previews

The native design uses the coordinate mirror `(min(x,y), max(x,y))`. An
unstructured `LinearNDInterpolator` of its exported samples can nevertheless
break that symmetry. The campaign therefore explicitly passes
`extract_mask.py --symmetry mirror_xy`: after interpolation it applies the
least-squares symmetric projection `(f(x,y)+f(y,x))/2`, then thresholds the
filtered `theta_f`. The standalone extractor defaults to `--symmetry none`
so that other geometries are not silently changed. The mask records the
pre/post mirror residual and maximum field change. This is a declared geometry
reconstruction, not an error bound or a correction to measured scattering data.
Every resulting mask needs its own native verification. Holes and bridges are
preserved; this does not establish fabrication rules or minimum features.

`plot_results.py` checks the supplied mask against the native plan, checks the
field against the execution receipt, and recomputes acceptance from the raw
matrix, flux and console data with `analyze.py`. It does not trust a previously
written `verification.json`. Its output includes the fresh verification and a
`preview-receipt.json` with source/evidence/figure hashes. Figure labels remain
single-run results, even when that individual run passes.

The locked qualification orders all training-wavelength and numerical checks
before the two holdouts. It stops on the first acceptance or convergence failure
and lists unspent checks; a partial suite never passes. This changes the order
and failed-candidate cost, not the nineteen required configurations or gates.

## Fixed-checkpoint discrete CVF gradient diagnostic

`check_discrete_gradient.py` and `CvfDiscreteGradientProbe.java` diagnose one
feasible discrete-control direction on the existing five-frequency beta8
checkpoint, evaluated at beta16. This is a fixed fixture, with weight10
`state_floor` objective and slit-PML ports. It does not add optimizer updates,
remeshing, clipping, or control-variable type changes. The checkpoint contract
is checked inside Java; any other checkpoint fails closed.

```powershell
python .\check_discrete_gradient.py --solver-root $env:PHOTONIC_SOLVER_ROOT `
  --restart C:\Private\beta8-checkpoint.mph --output C:\Private\fresh-gradient-run
```

The default validates paths and hashes and prints a plan without creating an
output directory or starting COMSOL. Add `--execute` only for an authorized
licensed local solve. Defaults are `--processors 8 --timeout 900`; the output
directory must be new. The official compiler and batch entrypoints run with
isolated prefs, configuration and tmp directories. Native data is stdout only:
no diagnostic model is saved, and the restart file is read without modification.

Each of 1580, 1565, 1550, 1536.61 and 1520 nm uses samples at 0, +0.001,
-0.001, +0.0005 and -0.0005. Java preserves the full-vector index and coordinate
map, validates every stored and freshly solved control vector, and requires
finite mapped `Fsens` with negligible imaginary part. The discrete contraction
uses no area factor. After copying solution data, both the `std1` association
and minimal `StudyStep` for `std1/freq` with `splitcomplex=true` are retained;
study association alone does not define the problem for `createSolution()`.

The Python parser requires all 25 observations, 10 comparisons, five wavelength
completion markers, one `MIN_ACTIVE`, two `MIN_FD`, and fresh control readbacks.
It recomputes both central-difference comparisons from the original observations
and the five-frequency minimum with tied-active one-sided adjoint derivatives.
Missing, duplicate, nonfinite or inconsistent rows fail closed. Scientific
relative tolerance is fixed at 0.002. `receipt.json` records `completed`
(native execution status) separately from `gradient_pass`, source/restart/plan
hashes and artifact hashes. Exit codes: 0 agreement, 1 execution or invalid-data
failure, 2 valid complete data with gradient disagreement.

Agreement supports this checkpoint, mesh, direction, objective and sample
steps. It does not establish all-direction gradient correctness, mesh/PML
convergence or device performance acceptance.
