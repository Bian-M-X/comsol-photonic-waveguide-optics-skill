# Wave-Optics Port Models

Use this reference for 2D effective-index models, materials, geometry selections, numeric ports, boundary mode analysis, scattering/PML boundaries, mesh strategy, datasets, S-parameter expressions, and energy diagnostics.

## Model Scope Decision

Before building geometry, state the model class:

- `2D EIM`: top-view effective-index approximation for topology, coupling trends, phase, FSR, and fast sweeps.
- `3D submodel`: straight waveguide, bend, directional coupler, or short cell validation.
- `full 3D`: expensive final validation, not the default first step.

2D EIM is not a final fabrication sign-off. It is useful for fast physical reasoning and parameter ranking.

## Common Global Parameters

```text
lambda0 = 1.55[um]
freq0 = c_const/lambda0
w = 0.5[um]
n_bg = 1.444
n_wg_eff = <mode-solver-or-paper-value>
epsr_bg = n_bg^2
epsr_wg = n_wg_eff^2
mu_r = 1
sigma = 0
```

For a paper using a `500 nm x 220 nm` SOI strip waveguide, prefer a separate cross-section mode analysis to extract:

- `n_eff(lambda)`
- `n_g(lambda)`
- single-mode or multimode behavior
- wavelength dispersion
- approximate mode-field extent for port sizing

If mode analysis is not available, use paper values or an engineering estimate, and label the result as an approximation.

## Material Selection Audit

Keep explicit selections:

- `sel_bg`: all background/cladding domains.
- `sel_wg`: all waveguide effective-core domains.
- optional `sel_dc_gap`: coupler-gap refinement region.
- optional `sel_bends`: bend refinement regions.
- optional `sel_ports`: port boundaries.

Assign materials:

- `mat_bg`: `epsilonr = epsr_bg`, `mur = 1`, `sigma = 0`.
- `mat_wg`: `epsilonr = epsr_wg`, `mur = 1`, `sigma = 0`.

Audit after every geometry rebuild:

- no waveguide domain is left in background material
- no background island is assigned waveguide material
- booleans did not destroy selections
- design-region material does not overwrite fixed waveguides

## Geometry Rules

Build from centerlines when possible:

- centerline length defines phase and `DeltaL`
- waveguide width is applied from `w`
- bend radius is measured at centerline
- do not use x-coordinate distance as a path-length proxy

For bends and transitions:

- avoid sharp 90-degree corners
- use arcs, S-bends, fillets, or rounded polylines
- keep `R_bend >= 5[um]` as a cautious 2D EIM starting point for 500 nm-class SOI strips
- sweep `R_bend = 5, 7.5, 10[um]` when bend loss matters
- keep non-port waveguides at least several microns away from outer boundaries

For port approach sections:

- local guide must be straight
- port boundary must be perpendicular to propagation direction
- keep `5-10 um` straight section before the port

## Numeric Port Setup

For port-based frequency-domain simulations:

1. Put ports on exterior computational boundaries.
2. Make each port boundary perpendicular to a local straight waveguide.
3. Ensure the port boundary cuts through the full waveguide and enough surrounding background for the mode.
4. Create one boundary mode analysis step per numeric port when numeric ports are used.
5. Bind each port to the correct boundary mode analysis result.
6. Run final frequency-domain or wavelength-domain study after port modes are available.

Port mistakes are common. Check:

- selected boundary id is correct
- port orientation is correct
- excitation is enabled only on the intended input port
- non-excited output ports are terminated, not excited
- scattering/radiation boundary does not include port boundaries
- final study uses the port mode solution, not a stale or missing mode

## Boundary Conditions

Start with scattering/radiation boundaries for quick models. For engineering claims, compare:

- larger background margin
- PML
- scattering boundary
- mesh refinement near boundaries

Critical rule: do not include port boundaries in scattering/radiation selections.

If S parameters are undefined, zero, or flat:

1. Confirm physics tag, for example `emw` or `ewfd`.
2. Confirm final solution dataset.
3. Confirm port boundaries are excluded from scattering/PML selections.
4. Confirm boundary mode analysis completed.
5. Confirm port feature references the correct mode step.

## Mesh Strategy

Start with a robust predefined mesh if custom mesh prevents meshing or solving. After the first successful solve, add local mesh controls.

Rules of thumb:

- waveguide core: at least `8-10` elements across width
- DC gap: at least `5` elements across the gap
- bend region: same or finer than waveguide core
- far background: coarse mesh to save memory
- port boundaries: enough resolution to represent the port mode

2D EIM starting values:

```text
waveguide max element: 0.05-0.08 um
coupler gap max element: 0.02-0.04 um
bend max element: 0.05-0.08 um
far background max element: 0.2-0.4 um
```

Mesh refinement order:

1. predefined mesh to get a working solve
2. local waveguide refinement
3. local coupler-gap refinement
4. local bend refinement
5. convergence check on key metrics

## Postprocessing Expressions

Use component prefixes when required:

```text
comp1.emw.normE^2
abs(comp1.emw.S21)^2
10*log10(abs(comp1.emw.S21)^2)
abs(comp1.emw.S11)^2
```

If the physics tag is `ewfd`, use:

```text
comp1.ewfd.normE^2
abs(comp1.ewfd.S21)^2
10*log10(abs(comp1.ewfd.S21)^2)
abs(comp1.ewfd.S11)^2
```

Do not mix `emw` and `ewfd`; inspect the model's actual physics tag first.

## Dataset Rules

Choose the correct dataset:

- field plot: final driven frequency-domain solution
- sweep plot: final parametric or wavelength sweep solution
- S-parameter table: final driven solution
- mode profile: boundary mode analysis dataset

Do not evaluate final S parameters on a boundary-mode dataset.

Debug order for plotting:

1. Add `comp1.` prefix.
2. Verify physics tag.
3. Select final solution dataset.
4. Evaluate one expression at a time.
5. Only then build derived plots or reports.

## Energy Diagnostics

For a two-port reflected-output model:

```text
T21 = abs(S21)^2
R11 = abs(S11)^2
Ssum = T21 + R11
radiation_or_uncollected = 1 - Ssum
```

Interpretation:

- correct FSR and low peak T21: interference exists, but coupling/ports/boundaries/bends/mesh may be poor
- high S11: reflection, port mismatch, or round-trip coupler mismatch
- low Ssum: radiation, boundary absorption, bend loss, or uncollected output
- single-wavelength T21 is insufficient for interferometer validation

## Straight Waveguide Smoke Test

Before building a complex device:

1. Build one straight waveguide with two numeric ports.
2. Assign `mat_wg` and `mat_bg`.
3. Run boundary mode analysis and frequency-domain solve at `lambda0`.
4. Confirm high `abs(S21)^2`.
5. Confirm low `abs(S11)^2`.
6. Plot `comp1.<tag>.normE^2`.

Only proceed to couplers and MZI devices after this passes.
