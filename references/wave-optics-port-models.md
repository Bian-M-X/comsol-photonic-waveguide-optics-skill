# Wave-Optics Port Models

Use this reference for 2D effective-index models, material selections, numeric ports, boundary mode analysis, mesh, datasets, and postprocessing.

## 2D Effective-Index Model

2D top-view models represent vertical waveguide confinement through an effective refractive index. They are useful for:

- planar topology validation
- coupling trends
- MZI/aMZI/LT-aMZI FSR checks
- fast parameter sweeps

They are not final 3D fabrication sign-off models.

Common parameters:

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

If a paper uses a `500 nm x 220 nm` SOI strip waveguide, ideally perform a separate mode analysis to extract `n_eff(lambda)` and `n_g(lambda)`, then use those values in the 2D model.

## Material Selections

Keep at least two explicit material domains:

- background/cladding material, such as `mat_bg`
- waveguide effective-core material, such as `mat_wg`

After geometry booleans or rebuilds, audit that each waveguide still belongs to the waveguide material selection.

## Numeric Port Setup

For port-based frequency-domain models:

1. Put ports on exterior computational boundaries.
2. Make port boundaries perpendicular to local straight waveguide direction.
3. Include at least `5-10 um` of straight waveguide before each port.
4. Create one boundary mode analysis step per numeric port.
5. Bind each port to its matching mode-analysis step.
6. Run the final frequency-domain or wavelength-domain study after the port modes are available.

## Boundary Conditions

Scattering/radiation boundaries are good first-pass boundaries, but engineering models should compare them with PML or larger background margins.

Critical rule: do not include port boundaries in the scattering/radiation boundary selection.

If port variables are undefined, flat zero, or physically meaningless, check:

- port boundary selection
- scattering boundary selection
- boundary-mode step binding
- final solution dataset

## Mesh Strategy

Start with a robust predefined mesh if custom mesh settings prevent meshing or solving. Then add local refinement:

- waveguide core: enough elements across waveguide width
- directional-coupler gap: enough elements across the gap
- bend region: same or finer than core mesh
- far background: coarse mesh to reduce cost

For 2D effective-index waveguide starts:

```text
waveguide max element: 0.05-0.08 um
coupler gap max element: 0.02-0.04 um
bend max element: 0.05-0.08 um
far background max element: 0.2-0.4 um
```

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
```

Always verify that the selected dataset is the final driven solution, not a boundary-mode dataset.
