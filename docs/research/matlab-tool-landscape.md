# MATLAB Tool Landscape

Research snapshot: 2026-07-29

## Scope and evidence labels

This survey records documented MATLAB execution and integration options. It
does not assert that MATLAB, a toolbox, a solver link, a compiler, a hardware
driver, or a commercial entitlement is available locally.

- `DOC-VERIFIED`: the linked MathWorks, solver-vendor, or project source was
  checked.
- `LOCAL-UNVERIFIED`: installation, release compatibility, licenses, drivers,
  hardware, APIs, and headless behavior have not been demonstrated locally.
- `PHYSICS-UNVERIFIED`: a successful MATLAB call does not validate the
  underlying optical, circuit, full-wave, multiphysics, or measurement result.

All adapters must accept a bounded machine-readable RunSpec and write a
machine-readable Result plus declared artifacts. They must not execute
user-supplied MATLAB statements, function names, Lumerical scripts, Python
code, shell commands, or SCPI strings.

## Landscape

| Tool and primary sources | Provenance and maintenance | License, commercial access, and extra entitlements | Platform and headless access | Interfaces and machine formats | Recommended role and claim boundary |
| --- | --- | --- | --- | --- | --- |
| [`matlab -batch` startup option](https://www.mathworks.com/help/matlab/matlab_env/startup-options.html), [Windows](https://www.mathworks.com/help/matlab/ref/matlabwindows.html), [Linux](https://www.mathworks.com/help/matlab/ref/matlablinux.html), [macOS](https://www.mathworks.com/help/matlab/ref/matlabmacos.html) | Official MathWorks documentation; current supported interface | Commercial MATLAB license | Windows/Linux/macOS; documented non-interactive mode, stdout/stderr logging, automatic exit, and zero/nonzero exit status | Fixed package entry point; repository RunSpec/Result JSON; MAT/CSV/HDF5 artifacts produced by controlled code | **Default controlled MATLAB executor candidate.** It becomes locally trusted only after the fixed wrapper, failure modes, cleanup, and result parity pass Phase B; never interpolate an untrusted statement |
| [MATLAB Engine API for Python](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html), [installation and version compatibility](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html), [limitations](https://www.mathworks.com/help/matlab/matlab_external/limitations-to-the-matlab-engine-for-python.html) | Official MathWorks API; compatibility changes by MATLAB/Python release | Requires a full installed/licensed MATLAB; MATLAB Runtime is insufficient | Same-machine start/find/connect workflows; not a remote engine; documented 2 GB limit for exchanged data | Python engine calls and MATLAB values; use MAT v7.3/HDF5 or declared files for large data | **Optional low-latency executor.** Probe without starting a session first; it is not the default isolated path |
| [Pass data between MATLAB and Python](https://www.mathworks.com/help/matlab/matlab_external/pass-data-between-matlab-and-python-from-python.html), [configure Python called from MATLAB](https://www.mathworks.com/help/matlab/matlab_external/install-supported-python-implementation.html) | Official MathWorks interoperability documentation | MATLAB license; Python environment and binary compatibility are separate prerequisites | Supported platforms/releases vary; callable from controlled batch or engine workflows | MATLAB arrays/structs/cells and documented NumPy/Pandas conversions; MAT/HDF5 for large or durable interchange | **Interop contract.** Test dtype, shape, complex values, sparse values, strings, NaN/Inf, and row/column ordering; do not guess release-specific conversions |
| [MATLAB Unit Testing Framework](https://www.mathworks.com/help/matlab/matlab-unit-test-framework.html) | Official MathWorks framework; part of MATLAB | MATLAB license; feature-specific tests can require their products | Scriptable and suitable for controlled batch execution | Script/function/class tests, fixtures, parameterization, mocks, performance results and reports | **Core MATLAB test layer.** Cover batch exit status, schema validation, array round trips, deterministic known answers, and explicit skips for missing entitlements |
| [Optimization Toolbox](https://www.mathworks.com/products/optimization.html) | Official MathWorks commercial product; actively maintained | Additional Optimization Toolbox entitlement | Supported MATLAB platforms; scriptable/headless through controlled MATLAB execution | Numeric arrays, problem structures, solver result structures/tables; LP/MILP/QP/SOCP/NLP/least-squares families | **Optional local optimizer.** Solver success does not establish global optimality or physics validity |
| [Global Optimization Toolbox](https://www.mathworks.com/products/global-optimization.html), [requirements](https://www.mathworks.com/support/requirements/global-optimization-toolbox.html) | Official MathWorks commercial product; actively maintained | Additional Global Optimization Toolbox and Optimization Toolbox; Parallel Computing Toolbox is recommended for supported parallel workflows | Windows/Linux/macOS as listed for the selected release; scriptable/headless | GlobalSearch, MultiStart, pattern search, genetic algorithm, particle swarm, simulated annealing and surrogate workflows; arrays/tables/results | **Optional expensive/black-box optimizer.** Record budget, seeds, repeats and stopping reason; never claim a proved global optimum from a heuristic run |
| [Statistics and Machine Learning Toolbox](https://www.mathworks.com/products/statistics.html), [DOE documentation](https://www.mathworks.com/help/stats/index.html) | Official MathWorks commercial product; actively maintained | Additional toolbox entitlement | Supported MATLAB platforms; scriptable/headless | DOE, Monte Carlo, regression/classification, probability models, tables and MAT/CSV results | **Optional DOE, corner, and statistical-model layer.** Preserve the design matrix, seeds, corner provenance, assumptions, confidence/uncertainty, and applicability domain |
| [Parallel Computing Toolbox](https://www.mathworks.com/products/parallel-computing.html), [requirements](https://www.mathworks.com/support/requirements/parallel-computing-toolbox.html) | Official MathWorks commercial product; actively maintained | Additional toolbox entitlement; cluster/cloud scaling can require MATLAB Parallel Server | Multicore/GPU/cluster workflows on supported platforms; interactive and batch APIs | Pools, futures, parallel loops, GPU arrays and batch jobs | **Optional scheduler/evaluator.** Commercial solvers and shared sessions remain concurrency one until license, isolation, memory and cleanup probes pass |
| [RF Toolbox](https://www.mathworks.com/products/rftoolbox.html), [data import](https://www.mathworks.com/help/rf/data-import.html), [`sparameters`](https://www.mathworks.com/help/rf/ref/sparameters.html) | Official MathWorks commercial product; actively maintained | Additional RF Toolbox entitlement | Windows/Linux/macOS for supported releases; scriptable/headless | Touchstone 1.1 read/write and 2.0 read support; S/Z/Y/H/G/T/ABCD conversions, de-embedding, passivity and rational fitting | **Optional network-data adapter.** The documented default reference impedance is 50 ohms; optical modal power-wave normalization, modes, port order, and reference planes must be explicit |
| [Instrument Control Toolbox](https://www.mathworks.com/help/instrument/index.html), [protocol/platform matrix](https://www.mathworks.com/help/instrument/supported-protocols-and-interfaces-by-platform.html) | Official MathWorks commercial product; actively maintained | Additional toolbox entitlement; VISA implementation, vendor drivers, support packages, firmware and hardware may add terms/dependencies | Platform and driver dependent; scripted/headless operation is possible only for compatible instruments/drivers | VISA, GPIB, TCP/IP, UDP, serial, SCPI, IVI/VXI; binary/text traces and controlled MAT/CSV artifacts | **Optional measurement backend.** Record instrument identity, firmware, driver, calibration, settings and raw trace; never accept arbitrary SCPI from a RunSpec |
| [Simulink documentation](https://www.mathworks.com/help/simulink/index.html) | Official MathWorks commercial product; actively maintained | Separate Simulink entitlement; blocks and code-generation/testing features can require additional products | Programmatic simulation is available on supported platforms; headless behavior is model- and block-dependent | `.slx`, parameters, SimulationData, MAT files, logs and generated reports | **Optional system/control and hardware co-simulation layer.** A Simulink run is not PIC circuit or electromagnetic full-wave evidence |
| [COMSOL LiveLink for MATLAB](https://www.comsol.com/livelink-for-matlab), [batch documentation](https://doc.comsol.com/6.4/doc/com.comsol.help.llmatlab/llmatlab_ug_functionality.7.21.html), [release compatibility](https://www.comsol.com/system-requirements/module) | Official COMSOL vendor product; commercially maintained | MATLAB, COMSOL, LiveLink for MATLAB, and every used COMSOL physics module require compatible commercial entitlements | Supported OS and exact MATLAB/COMSOL releases are version-locked; batch use is documented | MATLAB API to COMSOL model/geometry/mesh/study/solver/results; `.mph` and exported artifacts | **Optional legacy/optimization adapter.** Require same-model result/artifact parity with trusted native Java batch before promotion |
| [COMSOL LiveLink for Simulink](https://doc.comsol.com/6.4/doc/com.comsol.help.llsimulink/llsimulink_ug_intro.4.2.html), [co-simulation](https://doc.comsol.com/6.4/doc/com.comsol.help.llsimulink/llsimulink_ug_cosimulation.6.01.html), [release compatibility](https://www.comsol.com/system-requirements/module) | Official COMSOL vendor product; commercially maintained | Compatible COMSOL, Simulink, LiveLink, and relevant physics-product entitlements | Release/OS compatibility is explicit and version-sensitive; intended for controlled co-simulation/model export | COMSOL-Simulink co-simulation and reduced/state-space model exchange | **Optional system co-simulation.** A reduced-order or co-simulation result cannot be promoted to driven 3D full-wave evidence |
| [Ansys Lumerical MATLAB integration](https://optics.ansys.com/hc/en-us/articles/360026142074-MATLAB-script-integration-configuration-guide) | Official Ansys vendor documentation; commercial integration; compatibility is release-sensitive | MATLAB plus each used Lumerical product/license; no solver is bundled with MATLAB | Supported OS/release combinations have documented limitations and require a local probe | MATLAB-to-Lumerical API functions, Lumerical sessions/scripts and transferred data objects/files | **Optional legacy commercial adapter.** Only allow fixed operations; never expose arbitrary Lumerical script evaluation |
| [MatlabGDSPhotonicsToolbox repository](https://github.com/nicolasayotte/MatlabGDSPhotonicsToolbox), [MathWorks File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/46827-nicolasayotte-matlabgdsphotonicstoolbox) | Community project; public release is from 2017 and should be treated as legacy | MIT; MATLAB and a compatible C/MEX compiler are separate prerequisites | File Exchange lists Windows/Linux/macOS; scripted, but MEX/toolchain compatibility requires a probe | MATLAB photonic layout/routing/layer maps and GDS output | **Legacy-compatible layout adapter/reference.** Register a user-local path rather than vendoring by default; inspect all output with KLayout |
| [GDSII Toolbox author page](https://sites.google.com/site/ulfgri/numerical/gdsii-toolbox), [repository](https://github.com/ulfgri/gdsii-toolbox) | Community MATLAB/Octave project; legacy maintenance profile | Most functions state public-domain status, but bundled Clipper, Datamatrix and floating-point conversion code use Boost-1.0, GPL-2.0 and GPL-3.0 respectively; distribution requires a component license audit | MATLAB/Octave with platform-specific MEX/build tooling; headless scripts after a successful build | GDSII read/create/modify operations and MEX-backed data conversion | **Legacy format adapter only.** Mixed licensing blocks unreviewed vendoring or redistribution |
| [Photonic FDFD Toolbox repository](https://github.com/optical-imaging/photonic-fdfd-toolbox), [MathWorks File Exchange](https://www.mathworks.com/matlabcentral/fileexchange/180365-photonic-fdfd-toolbox) | Community research project; a public release was posted in 2026; small maintainer footprint | MIT; MATLAB and documented dependencies such as GDS import tooling are separate | File Exchange lists Windows/Linux/macOS; MATLAB scripts/headless after dependency probe | MATLAB arrays; 2D scattering/eigenmode and 2.5D variational FDFD; GDS import dependency | **Experimental 2D/2.5D solver.** Record dimensionality prominently and never label its output as 3D full-wave validation |

## Architectural disposition

1. Use `matlab -batch` as the default isolated MATLAB runtime, with a generated
   controlled wrapper and fixed package entry point.
2. Treat MATLAB Engine as optional low-latency integration. Discovery must not
   start a session, consume a license, or mutate user configuration.
3. Every MathWorks toolbox, COMSOL LiveLink product, Ansys Lumerical product,
   compiler, driver, and hardware interface has its own capability and
   entitlement record.
4. Register legacy/community MATLAB packages by user-controlled local path.
   Do not silently download, vendor, compile, or add them to a persistent
   MATLAB path.
5. Use MAT v7.3/HDF5 or declared artifact files for large data. Always record
   dtype, shape, complex encoding, units, wavelength/frequency axis, port/mode
   order, normalization, and reference planes.

## Minimum promotion test

Promotion from `LOCAL-UNVERIFIED` requires, in order:

1. executable/release discovery and `ver`/license/dependency inspection;
2. `matlab -batch` JSON echo and deterministic exit-code canary;
3. Engine import/version and small complex-array round trip, if Engine is used;
4. toolbox or external-product known-answer tests with declared artifacts;
5. separate solver-physics or measurement acceptance gates.

Configuration, product listing, license discovery, compilation, or API return
success is not physics evidence. Until these tests run locally, every entry
remains `LOCAL-UNVERIFIED` and `PHYSICS-UNVERIFIED`.
