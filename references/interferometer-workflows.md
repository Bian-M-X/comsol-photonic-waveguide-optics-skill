# Interferometer Workflows

Use this reference for directional couplers, conventional MZI, asymmetric MZI, loop-terminated asymmetric MZI, FSR checks, and topology-specific debugging.

## Workflow Ladder

Build in this order:

1. straight waveguide validation
2. standalone directional coupler
3. conventional MZI or asymmetric MZI
4. final LT-aMZI topology
5. wavelength sweep and FSR extraction
6. local optimization of couplers, bends, and ports

Do not debug a full LT-aMZI before the straight guide and standalone coupler pass.

## Directional Coupler Calibration

Standalone 2x2 coupler requirements:

- two parallel waveguides with width `w`
- edge-to-edge gap `gap_dc`
- center-to-center spacing `w + gap_dc`
- coupling length `Lc`
- smooth fan-in/fan-out matching final circuit style
- four ports on straight exterior boundaries

Sweep:

- `gap_dc`
- `Lc`
- fan-in/fan-out length or bend geometry when relevant
- mesh in the coupling gap

Evaluate:

```text
abs(comp1.emw.S31)^2
abs(comp1.emw.S41)^2
throughput_right = abs(S31)^2 + abs(S41)^2
split_error = abs(abs(S31)^2 - abs(S41)^2)
```

Selection criteria:

- small split error
- high total transmitted power
- low reflection
- robust behavior near target wavelength
- same geometry style as final device

Important: a coupler calibrated in a simplified geometry may not transfer exactly to a rounded-polyline or tightly routed main circuit. Calibrate with the same fan-in/fan-out style used in the final model.

## Conventional MZI

Topology:

```text
input splitter -> upper/lower arms -> output combiner -> output ports
```

Acceptance:

- upper and lower arms have identical width and material
- `DeltaL = L2 - L1` is measured along centerlines
- bends are smooth and sufficiently far from boundaries
- wavelength sweep gives periodic fringes
- FSR is consistent with:

```text
FSR_MZI = lambda^2/(n_g*DeltaL)
```

Use a conventional MZI as an intermediate validation before closing the loop in an LT-aMZI.

## LT-aMZI Topology

Target topology:

```text
DC1 -> unequal arms L1/L2 -> DC2 -> single loop reflector -> reflected return -> output at DC1
```

Strict acceptance checklist:

- DC1 is a 2x2 directional coupler.
- DC2 is a 2x2 directional coupler.
- DC1 east top connects to upper arm L1.
- DC1 east bottom connects to lower arm L2.
- DC2 west top connects from L1.
- DC2 west bottom connects from L2.
- DC2 east top and east bottom are connected by exactly one continuous loop reflector.
- The loop is not an independent ring resonator.
- No final right-side output port exists.
- Input and output ports are both on the left side near DC1.
- Output is measured from the reflected return through DC1.

Field evidence should show:

1. input from left upper port
2. splitting at DC1
3. propagation through both arms
4. recombination/splitting at DC2
5. entry into the right loop reflector
6. return through DC2 and arms
7. output at the left lower port through DC1

## LT-aMZI FSR

Use:

```text
FSR_LT = lambda^2/(2*n_g*DeltaL)
```

The loop reflector causes a reflected pass, so the effective arm phase difference is doubled relative to a one-way asymmetric MZI. For the same `DeltaL`, LT-aMZI FSR is approximately half the conventional aMZI FSR.

Example design targets often used for a `500 nm` SOI strip waveguide family:

| Design | `DeltaL` | Expected FSR |
|---|---:|---:|
| Design 1 | `44.7 um` | about `6.4 nm` |
| Design 2 | `89.4 um` | about `3.2 nm` |
| Design 3 | `178.8 um` | about `1.6 nm` |
| Design 4 | `357.6 um` | about `0.8 nm` |

These are target checks, not universal constants. Deviations can come from `n_g`, centerline length errors, topology mistakes, or coupler/boundary issues.

## Wavelength Sweep

Recommended procedure:

1. single wavelength at `lambda0`
2. coarse sweep to locate fringes
3. finer sweep around peaks/valleys
4. extract adjacent peak or valley spacing
5. compare with FSR formula
6. inspect `T21`, `R11`, and energy balance

Typical quantities:

```text
T21 = abs(comp1.emw.S21)^2
T21_dB = 10*log10(abs(comp1.emw.S21)^2)
R11 = abs(comp1.emw.S11)^2
```

Use the `ewfd` tag instead of `emw` when that is the model's physics tag.

## LT-aMZI Failure Modes

| Failure | Symptom | Fix |
|---|---|---|
| single snake-like waveguide | no true DC1-arms-DC2-loop topology | rebuild as two couplers plus two arms plus loop |
| right-side output remains | model behaves like conventional aMZI | remove right output ports in final LT-aMZI |
| loop connects only one waveguide | weak or no return path | connect DC2 east top to east bottom continuously |
| output measured on wrong side | wrong S-parameter interpretation | measure left lower output near DC1 |
| coordinate-based `DeltaL` | FSR wrong | compute centerline path lengths |
| sharp bends | radiation into background | use larger radius and refined bend mesh |
| material selection lost | field not guided | audit `mat_wg` and `mat_bg` selections |
| isolated 3 dB DC but low LT peak | round-trip mismatch | sweep `gap_dc`, `Lc`, and fan-in/fan-out geometry |

## Coupler Re-Optimization For LT-aMZI

If FSR is correct but peak `T21` is low:

1. confirm wavelength sampling did not miss the peak
2. evaluate `S11` at the peak
3. evaluate `T21 + S11`
4. sweep `Lc`
5. sweep `gap_dc`
6. run a joint `gap_dc x Lc` sweep
7. compare field plots at high and low transmission points

Do not optimize only `max(T21)`. Penalize:

- high `S11`
- nonuniform peaks
- strong/weak peak alternation
- radiation or uncollected power

## Evidence Standard

A credible interferometer reproduction needs:

- geometry screenshot or exported layout showing topology
- field map at representative wavelength
- wavelength sweep plot
- extracted FSR table
- comparison with theory or paper target
- energy diagnostic summary
- limitations, especially 2D EIM vs 3D

A field plot alone is not enough. A single-wavelength T21 value is not enough.
