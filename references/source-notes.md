# Source Notes For Future Refresh

Use this as a source index, not as a substitute for reading the original material when precision matters.

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
