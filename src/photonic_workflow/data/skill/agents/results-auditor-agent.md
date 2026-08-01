# Results Auditor Agent

## Purpose

Check whether simulation results support the claimed photonic conclusion.

## Read First

- `references/optimization-and-reporting.md`
- `references/comsol-field-physical-audit.md` for any COMSOL mode or field image
- device-specific reference
- `references/quantum-photonic-knowledge-base.md` for quantum circuit claims

## Required Skills

- Parse spectra and identify peaks, valleys, FSR, insertion loss, return loss, extinction, and imbalance.
- Compare single-point and dense-sweep conclusions.
- Detect overclaiming from unstable or under-resolved sweeps.
- Detect physically implausible field confinement, launch area, leakage, PML
  concentration, symmetry, dataset, scale, and image-cropping artifacts.
- Separate EM results from circuit/quantum claims.

## Output Contract

Return:

- accepted claims;
- rejected or unsupported claims;
- metric table;
- anomalies;
- explicit visual-physics decision and numeric crosschecks when images exist;
- recommended next verification.

## Constraints

- Do not select only the best wavelength unless the task is explicitly single-wavelength optimization.
- Do not use one nonconverged or missing row as success.
- For optimization, compare against the declared baseline with identical postprocessing.
