# Compact Model Lifecycle

Status: Phase A architecture contract

## Purpose

Compact models connect qualified component evidence to scalable circuit and
post-layout simulation. A `ModelCard` records its producer, model source,
artifacts, fidelity, parameter axes, validity envelope, and uncertainty.
Tool/version detail is linked through provenance.
`PromotionDecision.answerable_questions` records what the selected fidelity can
answer. A model card is not merely a path to an S-parameter file.

## Lifecycle

This is the target release lifecycle. Phase A implements the contracts,
long-form data validation, and NumPy composition; fitting, cross-tool comparison,
and controlled release become Phase B/C capability only after their adapters
and fixtures pass.

1. **Ingest:** register analytic, reduced, modal, 2D, 3D, multiphysics, or
   measured source artifacts and hashes. A hybrid construction is provenance,
   not an additional `FidelityLevel`; the released card still declares one
   supported fidelity.
2. **Normalize:** preserve port/mode order, wavelength or frequency axis,
   normalization, time convention, reference planes, and complex representation.
3. **Validate:** check completeness, finite values, passivity, reciprocity when
   expected, energy closure, sampling, and declared source evidence.
4. **Fit or transform:** record every interpolation, extrapolation, reference
   plane shift, de-embedding, rational fit, or format conversion.
5. **Compare:** evaluate against the source model and, where available, an
   independent tool or measurement over the declared envelope.
6. **Release:** freeze artifacts and the model card under a new revision; link
   producer versions, error metrics, and compatibility evidence through
   provenance and release artifacts.
7. **Recalibrate:** create a new revision linked to measurement; never rewrite
   the released model in place.

The existing long-form complex CSV remains the reference S-parameter
representation. Touchstone impedance fields may be file-compatibility metadata;
they are never silently treated as optical power-wave normalization.

## Promotion

`PromotionDecision` records the current and target fidelity, answerable
questions, risks, comparison metrics, tolerances, and calibration requirements.
A cheaper model is promoted only when it cannot answer the question or fails a
comparison. A selected optimization sample must be re-evaluated at the target
validated fidelity.

## Gates and claim boundary

- G1 establishes the port basis inherited by source models.
- G2 qualifies the reusable component and its complete complex multiport data.
- G3 validates model bindings and circuit conventions.
- G4 evaluates circuit behavior without becoming full-wave evidence.
- G6 compares promoted subassemblies at common reference planes.
- G7 covers robustness and high-fidelity re-evaluation.
- M3 compares simulation and calibrated measurement; M4 records a released
  recalibrated model.

Legacy CSV without complete sidecar evidence remains usable for compatibility
but is `unverified` and cannot by itself pass G2 or M4.

## Capability and phases

- **Phase A:** model-card and S-parameter contracts, NumPy validation/composition,
  provenance, legacy CSV/assembly compatibility, and mock release fixtures.
- **Phase B:** MATLAB/Python numeric round trips, RF/Touchstone fixtures, and
  selected local fitting or cross-tool comparisons.
- **Phase C:** commercial CML/INTERCONNECT integration, measured recalibration,
  and PDK-controlled release.

## No-fake boundary

No fit is valid without stored residuals, bandwidth, stability, and source
hashes. No extrapolation is implicit. A circuit model, MATLAB FDFD example, or
single-mesh source sweep is not promoted to converged 3D, process-qualified, or
measurement-calibrated evidence.
