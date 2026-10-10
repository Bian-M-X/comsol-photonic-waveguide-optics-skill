# COMSOL performance with bounded resources

Use for reducing solve cost or choosing hardware/solver settings. Performance
settings do not relax optical verification. Recheck official version-specific
documentation when deploying on another COMSOL release.

## Optimize the work before optimizing the machine

1. Use a model level that retains the required physics. Remove redundant geometry
   detail outside the relevant optical region; preserve ports/PML and material
   interfaces. Use symmetry only with a matching excitation and objective.
2. Use modal/circuit models for repeated assembly and target the 3D substructures
   responsible for uncertainty. A large layout need not be one full-device FEM.
3. Reuse geometry, selections and source basis within a candidate. For identical
   operators, reuse factorizations across right-hand sides using the source-sweep
   route. Frequency/material/geometry changes usually change the operator;
   unchanged sparsity permits symbolic reuse, not arbitrary reuse of a numeric LU.
4. Compile once and batch a reviewed sequence when startup dominates. Every
   candidate still needs explicit parameters, reset/invalidation rules, failure
   handling and attributed artifacts. Keep source columns of one S matrix in the
   same common basis. Persistent sessions are an optimization to qualify, not an
   excuse to reuse stale fields or mode solutions.
5. Keep summaries for every trial and full fields at declared checkpoints and
   promoted candidates. Avoid rendering plots or exporting entire fields on every
   optimizer iteration. Save restart state without claiming discarded fields exist.

## CPU, memory and GPU selection

Measure total wall time (startup, BMA, meshing, assembly, factorization, RHS,
export), peak physical memory and result differences. On a hybrid laptop, nominal
core count does not predict the fastest setting; compare a few bounded `-np`
values on the same model. The PowerShell runner accepts optional `-Processors`;
zero preserves COMSOL's existing default. Avoid persistent OS affinity, priority,
proxy or power-policy changes just to run a benchmark.

Commercial concurrency stays one unless separately authorized and isolated.
Leave RAM and VRAM headroom for the desktop and solver workspace. As an initial
local policy, cap projected use around 60–70% of currently available RAM and
70–80% of free VRAM; tune from observed peaks. These are conservative planning
heuristics, not enforced allocator limits. Abort/rescope a pilot that exceeds its
declared resource budget. Mesh DOF alone does not predict sparse factor memory.

For a moderate model that fits RAM, compare PARDISO and MUMPS. COMSOL 6.4 adds
NVIDIA cuDSS (`linsolver="cudss"`), with `cudssprecision="double"` as the baseline.
Actual GPU use must appear in the solve log; a GPU in the machine or a property
set in Java does not prove acceleration. Laptop RTX FP64 throughput, transfer and
initialization costs can erase any advantage on small optical systems. Choose
based on measured end-to-end cost and numerical agreement, not CUDA core count.

Use the cuDSS libraries bundled with the qualified COMSOL version, not an arbitrary
CUDA/cuDSS update. COMSOL 6.4 documentation lists bundled cuDSS 0.7.1 and CUDA
12.x compatibility. Check the live requirements before installing anything.

Out-of-core direct solves trade RAM for disk traffic and can dominate optimization
cost. First reduce the state size or use a qualified iterative/preconditioned
route. Helmholtz/Maxwell operators are indefinite; generic AMG/CG is not a safe
default. Validate complex outputs and residuals for each preconditioner. Single
precision, mixed precision or low-rank compression are experimental until phase,
loss, gradients and final metrics match a double-precision reference over the
relevant ill-conditioned/resonant cases.

## Repeatable local benchmark

`scripts/benchmark_comsol_solvers.py` loads an existing reviewed MPH, changes only
the named stationary direct solver and its coupled-solver binding, clears old
solution data, reruns the configured solution sequence, evaluates specified real
metrics, and saves fresh outputs in a **new** directory. It is serial, dry-run by
default, and bounds each native process by a timeout. Inspect solution/dataset
tags before running; it does not guess them or configure optical physics.

```powershell
py -3.13 scripts/benchmark_comsol_solvers.py `
  --solver-root $env:PHOTONIC_SOLVER_ROOT --model C:\Private\reviewed.mph `
  --output C:\Private\benchmark-new --solution sol1 --stationary s1 `
  --direct d1 --coupled fc1 --dataset dset1 `
  --metric 'real(ewfd.S21)' --metric 'imag(ewfd.S21)' `
  --solvers pardiso mumps cudss --repeats 2 --processors 8 --timeout 180
```

Review the printed plan, then add `--execute` under the existing task authorization.
The script is a trusted development helper, not an MCP execution tool. It does
not claim peak-memory enforcement or solve accuracy. Timeout kills only its owned
process tree on Windows; failed logs remain, and that solver is not automatically
retried. Repeats reverse solver ordering to expose warm-up effects. COMSOL may
also save a named-model copy at batch exit; account for that disk/startup overhead.

For an official example, keep vendor MPH/source files local and unmodified;
publish a compact receipt and model hash instead of redistributing vendor assets.
Compare complex outputs before interpreting timings. Separate per-run solver
agreement from mesh/PML/material convergence, which requires different evidence.

## Local pilot, 2026-09-29

A 64-GB-class i9-13980HX laptop with an RTX 5000 Ada Laptop GPU (16 GB) ran the
COMSOL 6.4 build-293 two-dimensional `waveguide_with_scatterer` example at 1550 nm.
It includes four numerical modal channels, absorption and a PML. At 25,153 driven
DOFs, six fresh processes (two per solver, 8 processors) agreed on the recorded
complex S21 and power metrics to rounding precision. GPU execution was confirmed
in the log. Study-sequence times were approximately 6.0–6.6 s; fresh batch wall
times approximately 16.3–17.0 s, plus compilation. This pilot provides **no GPU
speedup evidence** and no 3D design qualification. Reuse its method, not its timing
as a prediction for a new device. See the dated upgrade report for raw-receipt
hashes and any additional scale tests.

Primary sources: [solver selection](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_ref_solver.36.144.html),
[6.4 GPU release](https://www.comsol.com/release/6.4/studies-and-solvers),
[GPU selection](https://www.comsol.com/support/learning-center/article/gpu-selection-guidelines-for-comsol-computing-131452),
[system requirements](https://www.comsol.com/system-requirements/64/general),
[core-count tuning](https://www.comsol.com/support/knowledgebase/1324).
