# Interferometer Workflows

Use this reference for directional couplers, conventional MZI, asymmetric MZI, and loop-terminated asymmetric MZI workflows.

## Directional Coupler Calibration

Build a standalone 2x2 directional coupler before using it inside an interferometer.

Sweep:

- coupling length `Lc`
- edge-to-edge gap `gap_dc`
- fan-in/fan-out geometry if relevant

Evaluate:

```text
abs(comp1.emw.S31)^2
abs(comp1.emw.S41)^2
throughput_right = abs(S31)^2 + abs(S41)^2
split_error = abs(abs(S31)^2 - abs(S41)^2)
```

Select a length/gap that gives a small split error, high throughput, and low reflection.

Important: calibrate the coupler in the same geometry style used in the final model. A standalone smooth coupler calibration may not transfer to a rounded-polyline main circuit.

## Conventional MZI

Topology:

```text
input splitter -> upper/lower arms -> output combiner -> output ports
```

Acceptance:

- upper and lower arms have identical width/material
- path-length difference is computed along centerlines
- wavelength sweep gives periodic fringes
- FSR is consistent with `lambda^2/(n_g*DeltaL)`

## LT-aMZI

Loop-terminated asymmetric MZI topology:

```text
DC1 -> unequal arms L1/L2 -> DC2 -> single loop reflector -> return path -> output at DC1
```

Acceptance:

- DC1 is a 2x2 directional coupler.
- DC2 is a 2x2 directional coupler.
- DC1 east top connects to upper arm L1.
- DC1 east bottom connects to lower arm L2.
- DC2 east top and east bottom are joined by one continuous loop reflector.
- There is no right-side output port in the final LT-aMZI.
- Input and output ports are both on the left side near DC1.
- The output is taken from the reflected return through DC1.

LT-aMZI FSR:

```text
FSR_LT = lambda^2 / (2*n_g*DeltaL)
```

The loop reflector causes the arm phase difference to be experienced through a reflected pass, so the FSR is roughly half of the conventional aMZI FSR for the same `DeltaL`.

## Common Failure Modes

- The final geometry is a single snake-like waveguide rather than DC1-arms-DC2-loop.
- The loop is connected to only one waveguide.
- A right-side output port remains in the final LT-aMZI.
- Output is measured at the wrong side of the device.
- `DeltaL` is estimated from coordinates rather than centerline length.
- Bends are too sharp and radiate into the background.
- Waveguide material assignment is missing after geometry rebuild.
- The coupler is 3 dB in isolation but not optimal for reflected round-trip transmission.

## Field and Spectrum Evidence

Use both:

- field map: qualitative proof of propagation path
- wavelength sweep: quantitative proof of interference and FSR

A field plot alone is not enough. A single-wavelength `T21` value is not enough. Interferometers must be judged through sweep-derived peak/valley spacing.
