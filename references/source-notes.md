# Source Notes For Future Refresh

Use this as a source index, not as a substitute for reading the original material when precision matters.

## Hierarchical Photonic Design And Circuit Composition

- COMSOL 6.4 Port: `https://doc.comsol.com/6.4/doc/com.comsol.help.woptics/woptics_ug_optics.6.20.html`
  - Numeric ports require Boundary Mode Analysis; port sweeps calculate the S matrix and can export Touchstone data.
- COMSOL 6.4 S-Parameter Variables: `https://doc.comsol.com/6.4/doc/com.comsol.help.woptics/woptics_ug_modeling.5.33.html`
  - Defines port-derived complex S variables and power quantities.
- COMSOL 6.4 Geometry Parts: `https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_ref_definitions.21.004.html`
  - Parameterized parts can be instantiated and return geometry objects and selections.
- COMSOL Part Libraries: `https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_geometry.23.024.html`
  - Part models contain geometry parts and optional global functions, not materials, mesh, or physics.
- COMSOL Java API PartInstance: `https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_api_geom.48.118.html`
  - Java API entry point for reusable parameterized geometry instances.
- GDSFactory netlist extraction: `https://gdsfactory.github.io/gdsfactory/_autosummary/gdsfactory.get_netlist.get_netlist.html`
  - Extracts a netlist from component port connectivity.
- SAX circuit simulator: `https://gdsfactory.github.io/sax/`
  - Connects component S-parameter models in circuit netlists and supports optimization.
- SAX circuit from YAML: `https://gdsfactory.github.io/sax/nbs/examples/03_circuit_from_yaml/`
  - Demonstrates GDSFactory-compatible instance/connection/port netlists.
- Ansys INTERCONNECT Compound Element: `https://optics.ansys.com/hc/en-us/articles/360036109554-Compound-Element-COMPOUND-`
  - Supports hierarchical compound circuits and equivalent scattering-data analysis.
- Ansys CML compound element: `https://optics.ansys.com/hc/en-us/articles/4408249975059-compound-element-CML-Compiler-Model`
  - Packages advanced compound elements from compact-model or primitive building blocks.

These sources support the layered workflow in `hierarchical-device-workflow.md`. Refresh them before adding version-specific APIs or claiming interoperability with a current release.

## COMSOL Java API Geometry

- Circle geometry command: `https://doc.comsol.com/6.2/doc/com.comsol.help.comsol/comsol_api_geom.46.061.html`
  - Useful for analytic disk/sector primitives; properties include `angle`, `rot`, `r`, `pos`, and `type`.
- Boolean operations: `https://doc.comsol.com/6.2/doc/com.comsol.help.comsol/comsol_api_geom.46.066.html`
  - Useful for `Union`, `Intersection`, and `Difference`; `Difference` subtracts `input2` from `input`.
- Parametric curve: `https://doc.comsol.com/6.2/doc/com.comsol.help.comsol/comsol_api_geom.46.112.html`
  - Useful for diagnostic or reference curves; it is not by itself a solid waveguide domain.
- Fillet: `https://doc.comsol.com/6.2/doc/com.comsol.help.comsol/comsol_api_geom.46.085.html`
  - Useful for 2D rounded corners when vertex selections are reliable.

## MCP

- MCP tools: `https://modelcontextprotocol.io/specification/2025-06-18/server/tools`
- MCP resources: `https://modelcontextprotocol.io/specification/2025-06-18/server/resources`

Use MCP as an integration design option. A COMSOL bridge must be narrow, allowlisted, and audited before it replaces Java batch.

## Quantum Photonics Entry Points

- Wang, Sciarrino, Laing, Thompson, "Integrated Photonic Quantum Technologies": `https://arxiv.org/abs/2005.01948`
- Moody et al., "Roadmap on Integrated Quantum Photonics": `https://arxiv.org/abs/2102.03323`
- Clements et al., "An Optimal Design for Universal Multiport Interferometers": `https://arxiv.org/abs/1603.08788`
- Crespi et al., "Integrated photonic quantum gates for polarization qubits": `https://arxiv.org/abs/1105.1454`
- Zeuner et al., "Integrated-optics heralded controlled-NOT gate for polarization-encoded qubits": `https://arxiv.org/abs/1708.06778`
- Piasetzky et al., "High fidelity CNOT gates in photonic integrated circuits using composite segmented directional couplers": `https://arxiv.org/abs/2509.25505`
- Kwon et al., "Quantum Circuit Mapping for Universal and Scalable Computing in MZI-based Integrated Photonics": `https://arxiv.org/abs/2401.16875`

Refresh this list before starting a new publication-grade quantum-gate or large-scale processor design phase.
