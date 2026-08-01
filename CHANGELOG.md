# Changelog

All notable changes are recorded here. Versions follow Semantic Versioning;
recipe schema and recipe semantic versions are maintained independently from
the host package version.

## [Unreleased]

No changes yet.

## [0.4.0] - 2026-08-01

### Added

- Installable `photonic-workflow` package, `photonic` CLI, bounded MCP server,
  adapter SPI, project/run stores, versioned contracts, adoption gates, and
  solver-independent workflow profiles.
- Six deterministic modeling recipes distilled by reviewed behavioral and
  public-formula reimplementation from two read-only LT-aMZI projects: circular and
  symmetric-Euler geometry, segmented port windows, Li silicon and Malitson
  fused-silica bulk dispersion, and common-basis two-port diagnostics.
- Strict recipe request schemas, exact recipe versions, parameter contracts,
  packaged provenance hashes, canonical JSON output, and allowlisted fixed
  numeric COMSOL Java fragments for geometry/port setup only.
- MATLAB Phase A contracts and probes, external-backend adoption ledgers,
  package resource mirrors, artifact audits, and multi-context GitHub Actions
  validation.
- Python 3.11-3.14 compatibility lanes, checked-in skill/UI metadata schema
  validation, SHA-pinned Actions, split release permissions, SHA-256 release
  inventories, and GitHub build-provenance attestations.

### Changed

- Legacy Python and PowerShell entry points now delegate to package services
  while retaining regression-tested compatibility contracts.
- The legacy analytic-bend helper no longer writes arbitrary `--output` paths;
  bounded fragment creation is provided by `photonic recipe render`.
- MCP resource counts are derived from one registry and verified against source,
  packaged, and installed-wheel resources instead of duplicated magic numbers.
- The minimal third-party adapter example now declares host compatibility
  `photonic-workflow>=0.4,<0.5`.

### Evidence boundaries

- Recipe evaluation and rendering do not execute COMSOL or establish full-wave
  validation, convergence, fabrication readiness, or device acceptance.
- MATLAB Phase B remains blocked by the recorded native startup crash in the
  required normal interactive Windows context. LiveLink, Lumerical, instruments,
  and real PDK/DRC/LVS integrations remain separate Phase C adoption gates.

[Unreleased]: https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Bian-M-X/comsol-photonic-waveguide-optics-skill/releases/tag/v0.4.0
