# COMSOL Field-Plot Physical Audit

Use this reference whenever a COMSOL mode or driven-field image is used to
debug, validate, compare, or report a photonic model. Image review is a required
diagnostic gate, not a substitute for selections, convergence, S parameters,
or power accounting.

## Freeze The Plot Contract First

Before judging the image, record and visibly confirm:

- model and solution/run identity;
- wavelength or frequency and input source;
- dataset: boundary-mode solution for a port-mode plot, final driven solution
  for a device field plot;
- plotted expression, component/physics tag, units, and whether the scale is
  linear, logarithmic, normalized, clipped, or manually ranged;
- geometry/material overlay, full computational exterior, port locations, and
  PML regions when present;
- phase/time convention for real-part or phase plots.

Reject a cropped or rescaled image as `blocked` when the crop or color range can
hide the background, ports, PML, or leakage channel under review. Inspect at
least one linear intensity map and one logarithmic or deliberately extended
dynamic-range map for confinement and weak radiation.

## Expected Guided-Wave Physics

For a high-index-contrast SOI strip or its documented 2D effective-index
surrogate, the intended guided mode should have its strongest energy density in
the silicon/effective-core region with evanescent tails in the cladding. Exact
component signs and lobe shapes depend on polarization and phase; confinement
does not mean the exterior field must be exactly zero.

For a splitter or interferometer driven from one input, the image should also
be compatible with the declared topology: energy follows connected guides,
coupling occurs in the intended interaction region, outputs are populated in a
way consistent with the numerical port powers, and any radiation leaves through
declared open boundaries or PML.

## Fail-Closed Visual Red Flags

Mark the field-image audit `fail` and return to geometry/selections/physics if
any unexplained item is visible:

- high-amplitude field appears launched across an arbitrary full exterior side
  instead of the intended local waveguide cross-section;
- the guided field is mainly in bulk background while the intended core is weak;
- a mode is concentrated in an unrelated guide, material, boundary, or PML;
- nonphysical discontinuity occurs away from a material, geometry, source, or
  phase discontinuity;
- a geometrically symmetric device shows unexplained large output asymmetry;
- a disconnected region carries guided power;
- strong standing waves fill the exterior without an accounted reflector;
- the image and reported port powers, source column, polarization, or material
  selections are mutually inconsistent.

A vision model or human reviewer must explicitly check these physical red flags.
Do not accept an image merely because it is smooth, colorful, symmetric, or
visually similar to a reference. Colormap saturation, normalization, phase
snapshots, interpolation, crop, and aspect ratio can all conceal errors.

## Required Numeric Crosschecks

Pair image review with:

1. port-mode plots and port-selection entity IDs;
2. exact exterior partition audit: ports are mutually disjoint, ports do not
   overlap open-boundary selections, and ports plus open boundaries cover the
   complete exterior with no extra internal boundary;
3. modal output/reflection powers for the active source;
4. signed non-port exterior flux and material absorption;
5. mesh and open-boundary/PML sensitivity;
6. when practical, integrated core-versus-background energy or a mode-overlap
   measure at representative cross-sections.

The visual and numeric evidence must agree. A plausible image with bad power
closure is not a pass; good-looking S values with a physically impossible field
map are also not a pass.

## Review Record

Record one of `pass`, `fail`, or `blocked` plus:

```text
plot_artifact:
run_and_dataset:
source_and_wavelength:
expression_scale_units:
geometry_ports_pml_visible:
expected_guided_regions:
observed_confinement_and_leakage:
visual_red_flags:
numeric_crosschecks:
decision_and_next_action:
```

This record supports diagnostic confidence only. Device acceptance still
requires the applicable G1-G8 evidence.
