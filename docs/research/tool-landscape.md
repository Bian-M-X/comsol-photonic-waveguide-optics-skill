# PIC Tool Landscape

Research snapshot: 2026-07-29

## Scope and evidence labels

This is a documentation and source-license survey, not a local capability
report. Sources are vendor documentation, project-maintained documentation and
repositories, and explicitly identified community projects.

- `DOC-VERIFIED`: the linked documentation, repository, or license was checked.
- `LOCAL-UNVERIFIED`: installation, import, version compatibility, entitlement,
  credentials, headless operation, and usable APIs have not been demonstrated
  on the current machine.
- `PHYSICS-UNVERIFIED`: no accepted mesh, boundary, PML, mode, normalization,
  convergence, or benchmark evidence exists merely because an interface is
  documented or callable.

Layout, circuit, eigenmode, 2D/2.5D, 3D full-wave, and multiphysics evidence are
not interchangeable. Foundry signoff also requires the controlled PDK and
runset accepted by that foundry.

## Landscape

| Tool and primary sources | Provenance and maintenance | License, commercial access, and extra entitlements | Platform and headless access | Interfaces and machine formats | Recommended role and claim boundary |
| --- | --- | --- | --- | --- | --- |
| [GDSFactory documentation](https://gdsfactory.github.io/gdsfactory/), [license](https://raw.githubusercontent.com/gdsfactory/gdsfactory/main/LICENSE) | Official project; actively maintained | MIT. Open source does not grant access to NDA- or subscription-controlled foundry PDKs | Python on supported desktop/server platforms; headless | Python and YAML design intent; GDSII, OASIS, STL, Gerber; YAML component settings/netlists | **Core layout/design-intent front end.** Export success is not DRC, manufacturability, or physics evidence |
| [KFactory documentation](https://gdsfactory.github.io/kfactory/dev/), [prerequisites](https://gdsfactory.github.io/kfactory/dev/getting_started/prerequisites/), [license](https://raw.githubusercontent.com/gdsfactory/kfactory/main/LICENSE) | Official project; actively maintained; based on the KLayout C++ engine | MIT | Python; KLayout GUI is optional for supported scripted workflows | Python PCells/routing and schematic-driven design; GDS/OASIS | **Core implementation layer or advanced optional backend.** Keep public contracts above version-sensitive implementation details |
| [gplugins documentation](https://gdsfactory.github.io/gplugins/), [changelog](https://gdsfactory.github.io/gplugins/changelog.html), [license](https://github.com/gdsfactory/gplugins/blob/main/LICENSE) | Official GDSFactory adapter project; active changelog | MIT for the adapter collection; every solver, PDK, cloud service, and plugin has separate terms | Python; backend-dependent. The documented Meep path on Windows uses WSL | Adapters for Meep, Tidy3D, Femwell, Lumerical, SAX, and others; backend-native inputs/results | **Optional adapter collection/reference.** Probe, license, budget, and verify every backend independently |
| [KLayout DRC](https://www.klayout.de/doc/manual/drc_basic.html), [LVS](https://www.klayout.de/doc/manual/lvs_overview.html), [LayoutToNetlist API](https://www.klayout.de/doc/code/class_LayoutToNetlist.html), [license](https://www.klayout.de/license.html) | Official project documentation; actively maintained | GPL-2.0-or-later; free for private and commercial use under its license | Windows, Linux, macOS; documented batch use with `-b -r` | GDS/OASIS; Ruby/Python/runsets; `.lyrdb` reports; layout-to-netlist database; SPICE/netlists | **Core open verification backend.** A generic DRC/LVS pass is not foundry signoff without the controlled PDK/runset |
| [SAX repository](https://github.com/gdsfactory/sax), [PyPI](https://pypi.org/project/sax/) | Official project; actively maintained | Apache-2.0 | Python/JAX; headless | Python netlists/models, standard S-dictionaries and complex arrays | **Core or optional differentiable circuit backend.** Port order, modes, power-wave normalization, phase convention, and reference planes must be explicit and tested |
| [scikit-rf documentation](https://scikit-rf.readthedocs.io/en/latest/), [Network API](https://scikit-rf.org/doc/dev/reference/generated/skrf.network.Network.html), [license](https://raw.githubusercontent.com/scikit-rf/scikit-rf/master/LICENSE.txt) | Official project; actively maintained | BSD-3-Clause | Python; cross-platform and headless | Touchstone and pickle; complex S/Z/Y and related network arrays; calibration, de-embedding, vector fitting | **Optional S-parameter I/O and analysis.** Never silently apply RF 50-ohm wave semantics to optically power-normalized modal S-parameters |
| [SiEPIC-Tools repository](https://github.com/SiEPIC/SiEPIC-Tools), [license](https://raw.githubusercontent.com/SiEPIC/SiEPIC-Tools/main/LICENSE.md) | Official repository of a community/academic project; substantial development history; pin a tested revision | MIT. KLayout, PDKs, compact models, and Lumerical products have separate terms | KLayout GUI plus Python scripting; actual headless coverage needs a local probe | GDS/layout database, connectivity verification, extracted SPICE-style netlists, Lumerical INTERCONNECT integration | **Optional legacy-compatible layout-first flow.** Project verification and compact-model simulation are not foundry signoff or full-wave evidence |
| [openEPDA overview](https://openepda.org/), [licensing policy](https://openepda.org/licensing_policy.html), [Python package](https://pypi.org/project/openepda/) | Standards organization documentation; Python reference package is beta and its latest public release is from 2022 | Specifications are CC BY-SA 4.0, open and royalty-free with attribution/share-alike terms. The published Python package metadata does not state a clear SPDX software license: redistribution remains **license-blocked** until resolved | Standards are implementation-neutral; reference Python package is OS-independent and headless | JSON Schema-based validation; openEPDA data, uPDK, CDF and MDF formats; readers/writers | **Reference/interchange standard, not a solver.** Some specifications remain under development; package staleness and license are separate risks |
| [Meep documentation](https://meep.readthedocs.io/en/latest/), [installation](https://meep.readthedocs.io/en/latest/Installation/), [license](https://meep.readthedocs.io/en/latest/License_and_Copyright/) | Official project; actively maintained | GPL-2.0-or-later; redistribution/linking obligations apply | Linux/macOS and documented Windows-via-WSL route; Python/Scheme; MPI/OpenMP; headless | Python/Scheme control; HDF5 fields/state; flux and S-parameters derived by controlled post-processing | **Optional open FDTD backend.** Full-wave claims require dimensionality, source/mode normalization, PML, discretization, and convergence evidence |
| [Femwell repository](https://github.com/HelgeGehring/femwell), [documentation](https://helgegehring.github.io/femwell/), [license](https://raw.githubusercontent.com/HelgeGehring/femwell/main/LICENSE) | Community/open research project; active codebase; project explicitly warns that documentation lags code | GPL-3.0 | Python; headless | FEM meshes and Python arrays/objects; photonic/periodic eigenmodes, thermal and electrostatic calculations | **Optional mode and lightweight multiphysics backend.** Eigenmode, thermal, or electrostatic results do not establish 3D driven full-wave validation |
| [Tidy3D documentation](https://docs.flexcompute.com/projects/tidy3d/en/latest/), [repository](https://github.com/flexcompute/tidy3d), [submission API](https://docs.flexcompute.com/projects/tidy3d/en/latest/api/submit_simulations.html), [billing](https://docs.flexcompute.com/projects/tidy3d/en/v2.8.1/faq/docs/faq/how-is-using-tidy3d-billed.html), [client license](https://raw.githubusercontent.com/flexcompute/tidy3d/develop/LICENSE) | Official Flexcompute project; actively maintained | Python client LGPL-2.1. Cloud FDTD service requires an account, API key, and paid credits; client openness does not make the server solver open source | Local Python client and GUI on supported platforms; cloud execution; local mode-solver features are distinct from cloud FDTD | Python simulation models; web Job/Batch APIs; cost estimates; HDF5 results | **Optional cloud full-wave backend.** Require credential redaction, data-governance approval, cost estimate, explicit submit authorization, and physics acceptance |
| [COMSOL Wave Optics guide](https://doc.comsol.com/6.3/doc/com.comsol.help.woptics/WaveOpticsModuleUsersGuide.pdf), [COMSOL API introduction](https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_api_intro.46.02.html), [system requirements](https://www.comsol.com/system-requirements) | Official vendor documentation; commercially maintained | Proprietary commercial COMSOL license plus Wave Optics and any other used modules; cluster and optimization features may add entitlements | Supported Windows/Linux/macOS combinations are release-specific; Java API and COMSOL batch provide the trusted headless route | `.mph`, Java API/source, solver logs, exported tables and Touchstone/S-parameter data | **Trusted commercial full-wave/multiphysics backend.** Native Java batch is the default route; documentation and model compilation do not prove entitlement, convergence, or accepted physics |
| [sim-cli repository](https://github.com/svd-ai-lab/sim-cli), [sim-plugin-comsol repository](https://github.com/svd-ai-lab/sim-plugin-comsol), [plugin PyPI](https://pypi.org/project/sim-plugin-comsol/), [vendor-independent troubleshooting](https://docs.svdailab.com/sim/troubleshooting/comsol/) | Independent community project, not a COMSOL product; plugin is alpha/experimental | Apache-2.0 for the community code; user supplies COMSOL, licenses, and dependencies | CLI/runtime; local or remote operation. Remote connect/execute endpoints must be confined to a trusted network | `sim.toml`, machine-readable command descriptions/JSON, bounded check/connect/inspect/exec/verify/save operations, solver-native artifacts | **Experimental interactive/human-in-the-loop adapter.** Never replace native Java batch without a same-model parity canary; a license check alone is not capability evidence |
| [Ansys Optics overview](https://www.ansys.com/products/optics), [FDTD](https://www.ansys.com/products/optics/fdtd), [Python API](https://optics.ansys.com/hc/en-us/articles/360037824513-Python-API-overview), [licensing overview](https://optics.ansys.com/hc/en-us/articles/360033862333-Lumerical-product-components-and-licensing-overview), [platform matrix](https://optics.ansys.com/hc/en-us/articles/16391565007379-System-Requirements-and-Supported-Platform) | Official Ansys vendor documentation; commercially maintained | Proprietary commercial licensing. FDTD, MODE, INTERCONNECT, CML Compiler, HPC/GPU, and cloud features can require distinct products or entitlements | Supported Windows/Linux configurations and Python compatibility are release-specific; automation API is available with installed/licensed products | Python `lumapi`; native projects/scripts/data; GDS, CML and Touchstone/network data as supported by each product | **Optional commercial/legacy-PDK family.** Probe FDTD, MODE, INTERCONNECT and CML separately; no evidence may be promoted across products or from mode/circuit to 3D full-wave |

## Architectural disposition

1. The preferred open core is
   `GDSFactory/KFactory -> KLayout DRC/LVS/L2N -> SAX`.
2. gplugins, scikit-rf, and openEPDA are respectively an adapter collection, a
   network-data utility, and an interchange reference. They are not independent
   physics validators.
3. Meep, Femwell, Tidy3D, COMSOL, and Ansys Lumerical are optional backends with
   separate capability, entitlement, budget, artifact, and evidence records.
4. `sim-cli` plus `sim-plugin-comsol` remains experimental and
   human-in-the-loop. Native COMSOL Java batch remains the trusted default.
5. Commercial and cloud solvers default to dry-run and concurrency one.
   Credentials, NDA PDKs, and proprietary model data must never enter logs or
   generated documentation.

## Minimum promotion test

An adapter is not `available` because a package, executable, configuration file,
or license server can be found. Promotion requires, in order:

1. non-mutating version, dependency, platform, and entitlement discovery;
2. a bounded dry-run or cost/plan inspection;
3. a deterministic known-answer adapter canary with machine-readable artifacts;
4. for a physics claim, the solver-specific dimensionality, material, boundary,
   source/mode, normalization, convergence, and benchmark gates.

Until those stages run locally, every entry in this survey remains
`LOCAL-UNVERIFIED` and `PHYSICS-UNVERIFIED`.
