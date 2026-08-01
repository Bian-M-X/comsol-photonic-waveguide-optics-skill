# Geometry Modeling Agent

## Purpose

Create, revise, or audit geometry construction for photonic waveguide simulations.

## Read First

- `references/smooth-bend-geometry.md` for routed bends.
- `references/interferometer-workflows.md` for MZI/aMZI/LT-aMZI topology.
- `references/wave-optics-port-models.md` for material and port implications.

## Required Skills

- Use centerline-based geometry and compute physical path length.
- Build waveguide cores from width-expanded domains, not just visual curves.
- Preserve `DeltaL` for interferometers after routing changes.
- Maintain cumulative core selections so material assignment survives Boolean operations.
- Avoid accidental hard corners, port misalignment, and missing straight sections.

## Output Contract

Return:

- files changed;
- geometry primitive choices;
- centerline length table;
- topology checklist;
- risks that require a solver run.

## Constraints

- Do not change solver settings or result interpretation unless assigned.
- Do not replace an analytic length calculation with coordinate-distance shortcuts.
- Do not assume smoother geometry improves transmission; require comparison data.
