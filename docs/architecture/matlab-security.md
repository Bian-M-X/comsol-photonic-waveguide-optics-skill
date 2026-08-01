# MATLAB Security

Status: Phase A security contract

## Threat model

MATLAB integration handles executable code, local toolboxes, optional MEX
binaries, commercial APIs, shared sessions, large artifacts, and potentially
physical instruments. Inputs may therefore attempt statement injection, path
escape, startup-hook execution, session substitution, secret disclosure, or
unsafe device control.

## Mandatory controls

- Accept a registered entrypoint ID and map it inside the wrapper to a fixed
  function handle; never accept a user-provided MATLAB function name, `eval`,
  arbitrary statement, anonymous function, or script text.
- Invoke MATLAB with an argument array and `shell=False`.
- Use a generated wrapper whose source is fixed and auditable. Pass paths and
  data through validated environment values and JSON files, not interpolated
  MATLAB statements.
- Resolve RunSpec, result, runtime, toolbox, and artifact paths beneath allowed
  roots.
- Add paths process-locally and remove them at cleanup. Never edit `pathdef.m`
  or automatically run an unknown `startup.m`.
- Do not compile or execute a MEX file without an approved source/fingerprint.
- Probe Engine sessions without attaching; attachment requires an approved
  session-identity fingerprint.
- Redact user paths, license settings, secrets, API paths, and instrument
  resource addresses from ordinary output.
- Default external execution to dry-run, enforce timeout, capture stdout and
  stderr, and terminate the owned process tree on timeout.
- Require explicit physical safety limits and vetted driver commands before
  real instrument access. Raw SCPI strings are not accepted.

## Result trust

The wrapper writes a strict `MatlabResultManifest`. Before a result becomes
trusted, the runtime must validate its run ID, schema, exit code, tool versions,
declared artifacts, containment, size, and hashes. The Phase A result parser
currently validates schema, run ID, execution/exit consistency, relative paths,
and duplicate artifact IDs; artifact file containment, size, and hash checks
remain a Phase B trust-promotion target. Until those checks exist, inspection
is partial and cannot produce trusted execution evidence. A zero process exit
without a valid result manifest is execution failure. A valid result may still
be physically rejected.

## Gates and claim boundary

Security checks are prerequisites, not physics gates. A blocked security check
prevents execution and therefore leaves dependent G or M gates `blocked`.
Passing injection, redaction, or wrapper tests does not pass G1-G7 or M0-M4.
G8 may cite the security audit as part of reproducibility and release hygiene.

## Capability and phases

- **Phase A:** validators, allowlists, fixed wrapper plan, path containment,
  redaction, MEX/session/concurrency policy, mock result inspection, and
  injection tests.
- **Phase B:** local batch and Engine smoke tests on authorized machines, with
  process cleanup and result parity.
- **Phase C:** backend-specific controls for LiveLink, Lumerical, instruments,
  Simulink, remote workers, and compiled applications.

## No-fake boundary

An untested wrapper, installed toolbox, detected license, or discovered session
is not a trusted execution capability. Unknown MEX binaries remain blocked.
Mock instruments never justify real safety limits, and sanitized dry-run plans
must not be described as completed MATLAB runs.
