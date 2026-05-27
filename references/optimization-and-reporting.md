# Optimization and Reporting

Use this reference for parameter sweeps, inverse-design workflows, energy diagnostics, model comparison, 2D-to-3D progression, and reproducible reporting.

## Sweep Strategy

Start small and increase cost only after each layer is validated:

1. single wavelength
2. short coarse wavelength sweep
3. local peak/valley refinement
4. one-parameter geometry sweep
5. two-parameter joint sweep
6. mesh or boundary sensitivity check
7. final reporting sweep

For MZI/LT-aMZI, useful sweep dimensions include:

- `gap_dc`
- `Lc`
- bend radius
- port straight length
- background margin
- boundary type
- mesh level
- `n_wg_eff` or `n_g` assumption

Record each sweep with a manifest:

```text
run_id
date/time
model source
parameter ranges
mesh strategy
boundary strategy
physics tag
dataset used
output files
key metrics
known issues
```

## Objective Functions

Do not optimize only peak transmission. Include physical penalties.

For an LT-aMZI:

```text
score = max(T21)
        - penalty(peak_nonuniformity)
        - penalty(S11_at_peak)
        - penalty(radiation_or_uncollected)
        - penalty(FSR_error)
```

Possible metrics:

- `max(T21)`
- `min(T21)`
- extinction ratio
- insertion loss
- FSR mean and standard deviation
- `S11` at peaks
- `T21 + S11`
- peak-to-peak nonuniformity

Correct FSR with low peak transmission usually means the topology and phase are working, but coupling, return matching, boundary loss, bend loss, or mesh still need optimization.

## Energy Diagnostics

For a low-loss two-port reflected-output model:

```text
T21 = abs(S21)^2
R11 = abs(S11)^2
Ssum = T21 + R11
radiation_or_uncollected = 1 - Ssum
```

Interpretation:

- high `R11`: reflection, port mismatch, or poor round-trip coupler matching
- low `Ssum`: radiation, boundary absorption, bend loss, or uncollected channels
- correct FSR but low T21: optimize couplers and losses, do not rebuild topology first
- no fringes: check `DeltaL`, couplers, ports, and sweep range

## External Optimization Loop

For parameter sweeps or inverse design:

1. Python/PowerShell creates candidate parameters.
2. Candidate parameters are embedded into generated Java source or passed through a safe patching step.
3. Java source is compiled with the solver-bundled `javac.exe`.
4. Batch solver runs one candidate.
5. Metrics are exported to stdout or CSV/TXT.
6. Python aggregates, ranks, plots, and chooses next candidates.
7. Best candidates and summaries are saved for restartability.

For expensive or noisy objectives:

- start with coarse sweeps
- then local refinement
- use SPSA or small NSGA only after the objective is stable
- limit parallelism unless runtime directories and license behavior are well understood
- treat foreground timeouts as inconclusive until logs and output folders are checked

## Design-Region Discipline

When using a design region or pixelized material distribution:

- design region has its own selection
- fixed waveguide arms have their own selection
- background has its own selection
- fixed-core material does not cover the design region
- design-region material does not overwrite fixed waveguides
- ports and boundary regions are not optimization variables

This selection discipline also applies to non-pixelized circuits. Directional couplers, arms, loop reflector, bends, background, and ports should be auditable as separate geometry or selection groups.

## Resolution Refinement

When moving from lower to higher resolution:

- back up the previous best vector
- record source and target resolution
- try nearest-neighbor lifting
- try bilinear or smooth lifting
- evaluate both before continuing optimization
- do not assume smoother interpolation is better

Always compare post-lift performance before claiming improvement.

## Multi-Input Metric Interpretation

For devices evaluated with multiple independent input excitations, aggregated transmission can exceed 1 without violating single-input energy conservation.

Example:

```text
trans_total = sumA + sumB
```

Interpret each input separately:

- `T_aa:T_ab`
- `T_ba:T_bb`
- per-input reflection
- per-input uncollected power

For MZI/LT-aMZI single-input sweeps, focus on:

- `abs(S21)^2`
- `abs(S11)^2`
- `S11 + T21`
- peak and valley wavelengths
- FSR
- peak uniformity

## 2D To 3D Progression

Use 2D EIM for:

- topology checks
- FSR and phase trends
- fast coupler sweeps
- bend-radius screening
- candidate ranking

Use 3D for:

- true SOI cross-section mode
- vertical field confinement
- sidewall and etch-depth effects
- bend and coupler loss with realistic thickness
- final engineering validation

Recommended 3D progression:

1. straight 3D waveguide with ports
2. cross-section mode analysis for `n_eff(lambda)` and `n_g(lambda)`
3. short bend or coupler submodel
4. compact 3D substructure
5. full 3D device only if computationally feasible

Do not present an unconverged coarse 3D run as final validation.

## Visible Artifacts Before Manufacturing Claims

Before claiming manufacturability, export visible intermediate artifacts:

- field plots
- spectrum plots
- layout preview
- binary/density preview for design regions
- CSV mask
- SVG or PNG layout sketch
- parameter manifest

These are not substitutes for PDK-checked GDS, DRC/LVS, or experimental validation.

## Reporting Package

A complete report should include:

- paper or design target summary
- implemented assumptions
- geometry and material audit
- port and boundary setup
- mesh strategy
- validation ladder results
- field maps
- wavelength spectra
- extracted metrics
- energy budget
- comparison with theory or paper data
- limitations
- next engineering steps

Artifacts to deliver when allowed:

- model files
- build/run scripts
- sweep scripts
- batch logs
- CSV/TXT tables
- figures
- model-quality audit
- slides or report document

## Claim Labels

Use precise labels:

- `full-wave verified`
- `2D effective-index verified`
- `reduced-model verified`
- `preliminary optimization candidate`
- `requires 3D validation`
- `requires experimental validation`

Avoid overclaiming:

- do not call 2D EIM a final 3D design
- do not call a local sweep winner a global optimum
- do not use a pretty field plot as sole proof
- do not ignore `S11`, uncollected power, or boundary losses
