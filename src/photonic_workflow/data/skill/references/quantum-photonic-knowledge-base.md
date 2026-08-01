# Quantum Photonic Simulation Knowledge Base

Use this reference when a task moves beyond passive waveguide components into large-scale on-chip quantum photonic circuits, quantum gates, or programmable interferometer meshes.

## Modeling Layers

1. **Electromagnetic layer**: waveguide modes, loss, couplers, phase shifters, bends, crossings, resonators.
2. **Circuit scattering layer**: S-matrices or transfer matrices for each component.
3. **Quantum optical layer**: creation operators, Fock states, path/polarization/time-bin/frequency encoding, indistinguishability, post-selection.
4. **System layer**: source brightness, detector efficiency, loss budget, thermal/electrical tuning, calibration, and stability.

Do not jump from a 2D EIM field solve directly to a quantum-gate fidelity claim. First extract a credible component S-matrix/loss model, then propagate it through the quantum circuit model.

## Common Building Blocks

| Component | EM validation | Circuit/quantum validation |
|---|---|---|
| Straight waveguide | `S21`, `S11`, mode profile, propagation phase | loss and phase per length |
| Bend | bend excess loss, radiation, reflection | accumulated loss and phase error |
| Directional coupler | split ratio, excess loss, wavelength tolerance | beam-splitter matrix and imbalance |
| MMI/Y splitter | split ratio, phase relation, excess loss | beam splitter or multiport matrix |
| Phase shifter | phase shift vs drive proxy, insertion loss | single-mode phase gate `exp(i phi)` |
| MZI | FSR, extinction, tunable splitting | reconfigurable 2x2 unitary block |
| Ring/resonator | resonance, FSR, Q, extinction | filters, sources, delay, nonlinear enhancement |
| Source region | nonlinear overlap or emitter coupling | brightness, purity, heralding efficiency |
| Detector interface | coupling and absorption proxy | detection efficiency, dark count, timing model |

## Gate And Matrix Targets

Hadamard gate, path-encoded:

```text
H = (1/sqrt(2)) [[1, 1],
                 [1,-1]]
```

A directional coupler or balanced MZI can implement a Hadamard-equivalent operation up to phase conventions. Always state the chosen beam-splitter convention before comparing matrices.

CNOT gate:

```text
CNOT = [[1,0,0,0],
        [0,1,0,0],
        [0,0,0,1],
        [0,0,1,0]]
```

In linear optics, deterministic two-photon entangling gates usually need measurement, ancilla, feed-forward, nonlinear resources, or post-selection/heralding. For integrated photonic simulations, separate:

- classical EM component fidelity;
- reconstructed circuit matrix fidelity;
- quantum process fidelity;
- post-selection success probability;
- loss and indistinguishability limits.

## MZI Meshes And Large-Scale Simulation

Universal linear optical processors can be represented as meshes of 2x2 interferometers and phase shifters. Common references include triangular Reck-style decompositions and rectangular Clements-style decompositions. For large devices:

- build a component library first;
- attach measured/simulated loss and phase error to each component;
- compose the circuit in matrix form;
- only run full EM solves for small tiles, bends/crossings, or high-risk subcircuits;
- use reduced-order models for full-chip exploration.

## Recommended Validation Metrics

### EM/component

- `abs(Sij)^2`, insertion loss, return loss, crosstalk;
- phase error and group delay;
- wavelength tolerance;
- fabrication sensitivity to gap, width, etch, and bend radius;
- energy budget: reflected, transmitted, radiated/uncollected.

### Quantum/circuit

- unitary or subunitary transfer matrix error;
- process fidelity or truth-table fidelity when appropriate;
- Hong-Ou-Mandel visibility for two-photon interference;
- post-selection/heralding success probability;
- loss imbalance and distinguishability sensitivity.

## Literature Entry Points

- Wang, Sciarrino, Laing, Thompson, "Integrated Photonic Quantum Technologies" (review).
- Moody et al., "Roadmap on Integrated Quantum Photonics".
- Clements et al., "An Optimal Design for Universal Multiport Interferometers".
- Crespi et al., "Integrated photonic quantum gates for polarization qubits".
- Zeuner et al., "Integrated-optics heralded controlled-NOT gate for polarization-encoded qubits".
- Recent work on CNOT gates with composite segmented directional couplers and MZI-based LOQC mapping should be treated as current literature to re-check when starting a gate-design phase.
