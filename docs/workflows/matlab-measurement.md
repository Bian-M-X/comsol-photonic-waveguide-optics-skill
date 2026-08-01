# MATLAB Measurement Workflow

Status: Phase C physical-execution route; Phase A is contract and dry-run only

## Use when

Use this workflow when an authorized MATLAB instrument driver or analysis
pipeline is required for post-fabrication tests. Instrument control is a
physical-safety boundary and is never enabled merely because a resource is
discoverable.

## Preconditions

Freeze a `TestPlan` with:

- vetted instrument aliases and driver IDs;
- wiring and calibration;
- sweep variable, range, dwell, averaging, and compliance;
- maximum optical power, electrical voltage/current, temperature, and motion
  bounds as applicable;
- raw-data destination, uncertainty metadata, cleanup, emergency stop, and safe
  shutdown.

Drivers, protocols, VISA vendor, product/toolbox/license, and platform support
are capability probes. Resource addresses are redacted from ordinary output.

## Flow

1. Pass M0 only after the setup, limits, calibration plan, and cleanup are
   explicit.
2. Review a default dry-run containing no raw SCPI strings.
3. Execute one device session at a time on explicit authorization.
4. Capture immutable raw data and setup metadata before processing.
5. Validate raw hashes and completeness for M1.
6. Apply versioned calibration and uncertainty processing for M2.
7. Link processed data to design/model revisions for M3 and M4 workflows.

## Gates and claim boundary

The optical G0-G8 design track remains intact. M0-M4 are a separate measurement
track. Instrument connection or identity does not pass M0; process success does
not pass M1; plotted processed data does not pass M2 without calibration and
uncertainty. G8 may package the measurement links but does not collapse the two
tracks.

## Capability and phases

- **Phase A:** `TestPlan`/`MeasurementManifest` contracts, MATLAB instrument and
  measurement descriptors, safety validation, redacted dry-run plans, and mock
  result tests.
- **Phase B:** instrument dry-run may be tested on an authorized setup; no real
  output is assumed by core CI.
- **Phase C:** explicit real-device control, cleanup/timeout tests, calibrated
  acquisition, uncertainty, and correlation.

## No-fake boundary

Never invent a safety limit, calibration, identity, or uncertainty. Never send
arbitrary SCPI text. Mock instruments and synthetic data cannot pass M0-M4 or
support claims about a fabricated device.
