# Device-Family Workflows

Use this reference when the target is not specifically an MZI/LT-aMZI, or when the user needs a general integrated-photonics simulation route.

## First Question: What Device Family Is This?

Before building a model, classify the device:

- straight/rib/strip waveguide
- bend, crossing, or transition
- taper or mode converter
- Y-branch, MMI, directional coupler, or splitter
- ring resonator, disk resonator, or coupled resonator
- Bragg grating, photonic crystal, or periodic reflector
- grating coupler or free-space coupling structure
- MZI/aMZI/LT-aMZI or other interferometer
- sensor or modulator
- inverse-design region or topology-optimized splitter

Then choose the smallest validation model that proves the core physics.

## Universal Validation Ladder

1. Straight waveguide: material, port, mode, mesh, and boundary sanity.
2. Elementary unit: bend, taper, coupler, resonator cell, grating period, or splitter unit.
3. Functional block: complete splitter, ring with bus, Bragg section, MZI, or sensor baseline.
4. Full device: routed and parameterized final topology.
5. Sweep: wavelength, geometry, material perturbation, or drive variable.
6. Audit: energy balance, reflection, loss channel, mesh sensitivity, and boundary sensitivity.

## Waveguide, Bend, And Taper

Straight waveguide:

- validate `S21`, `S11`, mode shape, and phase
- compare against expected effective index when possible
- use this as the first smoke test for every project

Bend:

- compare to a straight reference of comparable length
- sweep bend radius
- refine bend mesh
- inspect radiation into background
- check reflection at bend entry/exit

Taper or transition:

- define input/output widths and target modes
- sweep taper length
- check mode conversion and reflection
- compare field shape before and after taper

## Splitters And Couplers

Applies to directional couplers, Y-branches, MMI splitters, and custom splitters.

Build standalone before system integration.

Metrics:

```text
T_i1 = abs(Si1)^2
T_sum = sum(T_i1 over intended outputs)
R11 = abs(S11)^2
split_ratio_i = T_i1 / T_sum
imbalance = max(split_ratio_i) - min(split_ratio_i)
uncollected = 1 - T_sum - R11
```

Typical sweeps:

- coupling length
- gap
- MMI width/length
- Y-branch opening angle
- taper length
- bend radius
- wavelength

Acceptance is target-dependent. A 3 dB directional coupler is not the only valid splitter target.

## Resonators

Applies to ring resonators, disk resonators, add-drop filters, and coupled resonator systems.

Core checks:

- bus-ring gap or coupling region
- round-trip loss
- resonance wavelength
- FSR
- extinction ratio
- loaded Q and intrinsic Q when extractable
- through and drop spectra

Use fine wavelength steps around resonances. A coarse sweep can miss narrow resonances entirely.

## Bragg, Periodic, And Photonic Crystal Devices

Core checks:

- period
- duty cycle or corrugation depth
- number of periods
- effective index and Bragg condition
- stopband center
- stopband width
- reflection/transmission spectra
- termination reflections

Start with a short periodic section, then sweep period count and apodization/chirp if relevant.

## Grating Couplers

Grating couplers can require 2D cross-section, 2.5D approximations, or 3D validation depending on the claim.

Core checks:

- coupling efficiency
- bandwidth
- back-reflection
- radiation angle
- polarization sensitivity
- substrate/cladding/PML influence
- fiber or free-space mode overlap, if modeled

Do not claim final coupling efficiency from a simplified 2D approximation unless the limitation is explicit.

## Sensors And Modulators

First build a passive baseline. Then add perturbation or drive.

Possible perturbations:

- analyte or cladding index change
- temperature change
- carrier-induced index/loss change
- electro-optic index change
- mechanical displacement
- geometry variation

Metrics:

- resonance shift
- phase shift
- sensitivity
- insertion loss
- extinction ratio
- bandwidth
- figure of merit

Separate optical-only assumptions from coupled thermal/electrical/mechanical physics.

## Inverse-Design Regions

Use strict selection discipline:

- fixed waveguides are not design variables
- ports are not design variables
- background is not accidentally overwritten
- design region has its own material/selection
- exported masks are previews unless they pass fabrication checks

Useful artifacts:

- density preview
- binary preview
- SVG/PNG layout preview
- CSV mask
- manifest of resolution, threshold, and objective

## Evidence By Device Family

| Device | Minimum evidence |
|---|---|
| straight waveguide | field map, S21/S11, mode profile |
| bend | bend loss vs radius, field leakage check |
| taper | transmission/reflection vs length, output mode check |
| splitter/coupler | split table, excess loss, wavelength tolerance |
| ring | spectrum, resonance extraction, Q/FSR/ER |
| Bragg | reflection/transmission spectrum, stopband extraction |
| grating coupler | coupling efficiency, bandwidth, radiation/PML audit |
| interferometer | field map, sweep fringes, FSR, ER/IL |
| sensor/modulator | baseline, perturbation sweep, sensitivity or phase shift |
| inverse design | objective history, best candidate, robustness and preview |

## General Failure Patterns

- field plot looks plausible but no quantitative sweep exists
- port mode is wrong or evaluated on the wrong dataset
- material selections are lost after geometry rebuild
- boundary or PML absorbs guided power unintentionally
- mesh is too coarse in gap, bend, grating, or resonance region
- wavelength step misses narrow resonance or interference peaks
- optimized structure is not compared against a simple baseline
- 2D approximation is reported as if it were final 3D validation
