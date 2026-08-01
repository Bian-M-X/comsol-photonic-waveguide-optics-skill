# Measurement Correlation Workflow

Status: post-fabrication evidence contract; real data is Phase C

## Purpose

This workflow compares calibrated measurements with the exact simulation and
design revisions that produced the chip, then releases a new compact-model
revision when justified.

## Flow

1. **M0 test-ready:** freeze device/die identifiers, setup, limits, calibration
   plan, sweep, uncertainty plan, raw-data policy, and cleanup.
2. **M1 raw-data-integrity:** ingest immutable raw files, setup metadata,
   timestamps, instrument/adapter versions, and hashes.
3. **M2 calibrated-measurement:** apply versioned calibration and processing;
   retain raw parents, analysis-code hash, units, and uncertainty.
4. **M3 correlation:** align ports, modes, wavelength/frequency axes, reference
   planes, temperature/corner, normalization, and sampling with a linked
   simulation/model revision. Record residuals and uncertainty-aware metrics.
5. Diagnose disagreement before fitting: identification, setup, calibration,
   fabrication, packaging, model validity, and solver error are separate causes.
6. **M4 compact-model-recalibrated:** fit only within a declared envelope,
   validate on held-out data where possible, record errors/stability, and
   release a new model card without rewriting the original.

## Gates and claim boundary

M0-M4 are separate from G0-G8. The design gate ledger remains the record of
pre-fabrication evidence. M3 may compare against G2/G4/G6 artifacts; it does not
retroactively convert them into measurement evidence. G8 links the measurement
campaign and recalibrated release.

Measured, calibrated, correlated, and recalibrated are distinct claims.
Successful fitting is not proof of causal correctness or out-of-envelope
validity.

## Capability and phases

- **Phase A:** measurement/model/provenance contracts, M-gate semantics, mock
  data, immutable lineage, and comparison interfaces.
- **Phase B:** MATLAB/Python data round trips and synthetic correlation fixtures.
- **Phase C:** authorized acquisition, real calibration/uncertainty, correlation,
  compact-model fitting, validation, and release.

Capability reports distinguish acquisition, calibration, analysis, fitting, and
model release. Missing calibration or uncertainty leaves M2 and later gates
`blocked`.

## No-fake boundary

Never substitute synthetic or mock data for measurement, invent uncertainty,
discard inconvenient failed samples without provenance, or overwrite raw data.
Do not call an in-sample fit a validated measured model.
