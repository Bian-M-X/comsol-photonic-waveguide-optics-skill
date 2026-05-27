# Optimization and Reporting

Use this reference for parameter sweeps, inverse-design workflows, energy diagnostics, and reporting.

## Energy Diagnostics

When output is low, evaluate:

```text
T21 = abs(S21)^2
R11 = abs(S11)^2
Ssum = T21 + R11
radiation_or_uncollected = 1 - Ssum
```

Interpretation:

- Correct FSR plus low peak T21 usually means interference exists but coupling, ports, boundaries, bend loss, or mesh need work.
- High S11 suggests reflection, port mismatch, or poor round-trip coupler matching.
- Low Ssum suggests radiation, boundary absorption, bend loss, or uncollected power.
- A single wavelength cannot determine whether an interferometer is correct.

## Parameter Sweep Strategy

Start small:

1. single wavelength
2. coarse local wavelength sweep
3. peak/valley refinement
4. local geometry sweep
5. joint sweep

For MZI/LT-aMZI, useful sweep dimensions include:

- `gap_dc`
- `Lc`
- bend radius
- port straight length
- background margin
- mesh size
- boundary type

Do not optimize only `max(T21)`. Penalize:

- high `S11`
- peak nonuniformity
- strong/weak peak alternation
- large uncollected power

Example:

```text
score = max(T21) - penalty(peak_nonuniformity) - penalty(S11_at_peak) - penalty(uncollected_power)
```

## External Optimization

For design-region or pixel-based optimization:

1. Build one forward model for each input condition.
2. Keep the design region as a dedicated selection.
3. Keep fixed waveguide arms in a separate selection.
4. Do not let fixed material accidentally cover the design region.
5. Let Python orchestrate candidate generation, source patching, compilation, batch solve, metric parsing, and optimizer update.

For expensive noisy objectives, simple SPSA or small NSGA searches may be useful. Preserve best vectors and logs between stages.

## Resolution Refinement

When increasing parameter-grid resolution:

- back up the previous best vector
- try nearest-neighbor and bilinear lifting
- evaluate both before optimizing
- do not assume interpolation improves performance

## Multi-Input Metrics

If a metric aggregates multiple independent input excitations, totals above 1 may not violate single-input energy conservation.

Example:

```text
trans_total = sumA + sumB
```

Interpret per-input split ratios separately, such as `T_aa:T_ab` and `T_ba:T_bb`.

## Reporting Package

Deliver:

- model files
- build/run scripts
- logs
- sweep CSV/TXT
- field maps
- spectrum plots
- model audit
- parameter table
- paper/theory comparison
- limitations and next steps

Label conclusions carefully:

- full-wave verified
- reduced-model verified
- preliminary optimization candidate
- requires 3D validation
- requires experimental validation
