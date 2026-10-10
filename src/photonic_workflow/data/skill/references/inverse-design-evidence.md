# Inverse-design evidence and adoption decisions

Reviewed 2026-09-29 with targeted literature refreshes through 2026-10-10; native
Hadamard route reviewed through 2026-10-10. Distinguish paper results, reusable mathematics, implemented
software, and local full-wave evidence. This is a targeted research update, not
an exhaustive systematic review or a novelty certificate. Public resources below
contain original summaries and links, not redistributed paper PDFs or vendor code.

## Four supplied papers

The local PDFs were read, with formula pages visually checked. Page locators below
refer to article pages (the He PDF has an additional publisher-information page).

| Source | Decision-changing evidence | Adopted route and limitation |
|---|---|---|
| He et al., *Science Advances* **9**, eadg6685 (2023), [DOI](https://doi.org/10.1126/sciadv.adg6685), pp. 3–6 | 50:50 and 33:67 blocks, three design wavelengths, double filtering; quantum characterization includes postselected success and process tomography | Complex amplitude/phase objectives, robust corners and circuit-level verification. A split ratio alone is not a Hadamard/process-fidelity certificate; ideal postselected CNOT success is 1/9, distinct from optical/detection losses. The full compact cascade discussion includes single-photon simulations, not proof of deterministic cascaded two-photon gates. |
| Christiansen & Sigmund, *JOSA B* **38**, 496–509 (2021), [DOI](https://doi.org/10.1364/JOSAB.406048), Secs. 6–10, Eqs. 17–22 | Adjoint efficiency; a naive gray design loses substantial performance after thresholding; double filtering treats correlated erosion/dilation | Full derivative chain, continuation, binary reevaluation and calibrated process offsets. The paper's 2D nondispersive examples, COMSOL 5.5 files and filter parameters do not qualify a 3D SOI device or a new software version. |
| Molesky et al., *Nature Photonics* **12**, 659–670 (2018), [DOI](https://doi.org/10.1038/s41566-018-0246-9), Box 1 and pp. 663–667 | Adjoint formulation, multiple representations, nonlinear overlap tradeoffs and computational/manufacturing limits | Match representation and state equations to the task; reduced/circuit screening with targeted full-wave work. Search success does not prove a universal physical limit or global optimum. Historical industrial-status statements are not treated as current facts. |
| Piggott et al., *Scientific Reports* **7**, 1786 (2017), [DOI](https://doi.org/10.1038/s41598-017-01939-2), pp. 2–3 | Curvature filtering plus separate removal of narrow gaps/bridges; the splitter used six frequencies and 216 state solves over 18 iterations | Enforce width, gap and curvature separately; count per-frequency forward/adjoint costs. Its GPU-FDFD timings cannot be transferred to COMSOL or this laptop. Its design/fabrication settings are examples, not a generic PDK. |

Source file SHA-256 prefixes for local identification: He `04cef80218b92c77`,
JOSA B `d97a1817b3d59fa3`, Molesky `088fdc91950f08a1`, Piggott `9ab8c02ab519a223`.
Full hashes and original names are recorded with the private reading manifest.
The 33-page He author manuscript and S1–S8 supplement were subsequently read
from [arXiv 2309.04895](https://arxiv.org/pdf/2309.04895), SHA-256
`dc09cac43c46b2ad5f9809b9922d2ca1be4f223261b33875283d62e5d5d4806c`.
Fig. S2 fixes the Hadamard block's **cross geometry**, with inputs left/bottom
and outputs top/right. The experimental Hadamard fidelity is a basis-state
matrix-overlap measure, not the conditional Choi metric used in our engineering
checker. No Hadamard throughput floor is specified there. Exact physical
reproduction still requires resolving the paper's unspecified numerical choices.

## Recent methods and current tools

Entries were checked against primary paper/author/publisher or official tool
pages. Reported speedups in those works are not local measured speedups.

| Source, status at review | Useful idea | Decision for this workflow |
|---|---|---|
| Schubert et al., [ACS Photonics 2022 / author record](https://arxiv.org/abs/2201.12965v2), DOI 10.1021/acsphotonics.2c00313 | Conditional feasible-design generation and straight-through gradients for strict length scales | Candidate route when ordinary density/contour design repeatedly fails DRC; separately check the generator's precise rule set and biased gradient behavior. |
| Ballew et al., [ACS Photonics **10**, 836–844 (2023)](https://doi.org/10.1021/acsphotonics.2c00862); [2021 author derivation](https://arxiv.org/pdf/2107.09468) inspected | Constrain local permittivity steps to improve binarization while using the optical gradient | Candidate for persistent gray-to-binary degradation. The author derivation does not establish native COMSOL/filter-chain integration, fabrication rules or a local speedup; publisher full-page access returned 403. |
| Schul et al., [Nature Reviews Materials **11**, 621–631 (2026)](https://doi.org/10.1038/s41578-026-00915-5), published 20 April; [author-hosted article](https://web.stanford.edu/group/nqp/jv_files/papers/InvDesRev.pdf) inspected for scaling/foundry sections | Updated overview of large 3D design, manufacturability, alternative materials and quantum/nonlinear systems | Keep inexpensive 2D experiments within their model scope, and budget fabrication constraints and targeted 3D adoption separately. A newer survey is not device acceptance or a reason to install another solver. |
| [BOSON inverse](https://arxiv.org/abs/2411.08210), author preprint record (2024 submission) | Variation-aware subspace optimization | Motivate active process scenarios and reduced search spaces; not installed or reproduced here. |
| [MAPS](https://arxiv.org/abs/2503.01046), author preprint (2025) | Multi-fidelity data, AI-assisted simulation and fabrication-aware inverse-design infrastructure | Retain explicit fidelity labels and reusable data. Training, dataset generation and port-convention adoption remain real costs. |
| Sofronov et al., [Accelerated inverse design of passive Si Photonics](https://arxiv.org/abs/2505.03352), preprint (2025) | Differentiable geometry-to-Yee-grid mapping and GPU FDTD | Evaluate for large repeated campaigns only after backend setup and independent COMSOL comparison. No new solver dependency in the core. |
| Seo et al., [physics-guided fabrication-aware diffusion](https://arxiv.org/abs/2504.17077), author preprint; publisher DOI 10.1021/acsphotonics.5c00993 listed in 2026 literature | Generative initialization combined with physics feedback | Conditional, amortized-use option. The publisher page returned HTTP 403 in this review; do not treat its full text as inspected. |
| Zhou et al., [PRISM v2](https://arxiv.org/html/2602.15762v2), revised 2026-06-01; author record says accepted to ACM TODAES | Compact calibration patterns, differentiable process models and optical-sensitivity-weighted mask correction | A strong long-term fabrication route. The reported virtual-foundry studies are controlled proxies, not qualification of our foundry; requires independent mask/SEM calibration and held-out devices. |
| Danis et al., [learned design-rule-compliant manifolds](https://doi.org/10.1002/lpor.71486), *Laser & Photonics Reviews* Early View (2026) | Search in a learned feasible geometry manifold | Useful when reusable training amortizes; account for training cost, excluded design families and foundry-specific DRC. Retain a direct shape/adjoint baseline. |
| He et al., [hyper-spectral recursive inverse design](https://www.nature.com/articles/s41467-026-76328-3), *Nature Communications* **17**, 9613 (2026); [author version](https://arxiv.org/html/2510.12104v1) | Decompose system targets, design local scattering elements, then optimize interconnect phases with compact models | Adopt this hierarchy for large circuits with meaningful feedback; retain complex reflection and phase in the compact model. The paper's spectral-complexity scaling is task-specific, not a general inverse-design speedup or quantum-gate result. |
| Rodionov et al., [MOCLIP](https://www.nature.com/articles/s41467-026-76714-x), September 2026 version of record; [author version](https://arxiv.org/html/2511.18980v1) | Contrastively learned geometry/spectrum representations from a large experimental metasurface dataset | An amortized design-family option, not a replacement for this gate's complex modal matrix. Published amplitude-spectrum prediction does not establish phase or coherent-gate fidelity; count data acquisition and training before claiming low total cost. |
| Dasdemir et al., [factorization caching](https://arxiv.org/html/2307.05388v1), author preprint (2023) | Reuse sparse symbolic analysis and compatible numerical factorizations in FDFD | Separate unchanged sparsity from unchanged matrix values. Numerical factors require the same operator and linearization state; the native coupled-Jacobian diagnostic shows why a converged primal field alone is insufficient. No transfer of its reported FDFD speedup to COMSOL is claimed. |
| Dunning & Wein, [automatic projection continuation](https://doi.org/10.1007/s00158-025-03968-2), *Structural and Multidisciplinary Optimization* **68**, 33 (2025), full open-access text inspected | Relate projection progression to objective/grayness; reduce move limits as the projection transition narrows | Candidate remedy for persistent high-beta oscillation. Compare from the same checkpoint and count all model evaluations; results on structural/thermal benchmarks do not establish improvement for Maxwell gates. Not implemented as automatic continuation here. |
| Song et al., [adaptive beta update](https://doi.org/10.1016/j.cma.2026.118805), *CMAME* **453**, 118805 (2026), publisher abstract/preview only | Use grayness and stability to guide projection updates | Supports investigating adaptive continuation instead of fixed iteration intervals. Full method and supplementary results were not inspected; no reproduction or speedup claim. |
| Eriksson et al., [TuRBO](https://proceedings.neurips.cc/paper/2019/hash/6c990b7aca7bc7058f5e98ea909e924b-Abstract.html), NeurIPS 2019 | Local BO for expensive higher-dimensional black boxes | Optional mature algorithm; the core's small mixed-pool GP-EI is explicitly not its implementation. |
| [BoTorch qMFKG tutorial](https://botorch.org/docs/tutorials/multi_fidelity_bo), official docs, v0.18.1 shown on review date | Target-fidelity knowledge gradient with cost-aware sampling | Use when calibrated fidelity data justify the dependency; not claimed implemented by `optimize suggest`. |
| [Meep adjoint tutorial](https://meep.readthedocs.io/en/latest/Python_Tutorials/Adjoint_Solver/), official docs | Open-source forward/adjoint workflow and material-grid gradients | Alternative backend with its own Windows/WSL, license, dispersion and gradient tests; no automatic installation. |
| [COMSOL 6.4 solvers](https://www.comsol.com/release/6.4/studies-and-solvers) and [metalens topology tutorial](https://doc.comsol.com/6.4/doc/com.comsol.help.models.opt.metalens_topology_optimization/metalens_topology_optimization.html), vendor docs | cuDSS, mode following and a native optical topology route | Locally benchmark CPU/GPU; qualify native adjoint separately. Eigenmode following still needs modal overlap/gauge checks in degenerate subspaces. |

Search coverage: inverse design/adjoint, manufacturing/robustness, multi-fidelity
optimization and COMSOL performance, with targeted 2025–2026 queries and backward
method references. Some publisher pages were blocked; local supplied full texts
and primary author versions provided fallbacks. Verify current versions again
before future installation or making a new comparative claim.

The October refresh checked publisher metadata/indexed text and the linked
author versions for the recursive-design and MOCLIP entries. Direct publisher
full-page opens redirected to an inaccessible identity endpoint; their complete
versions of record were not inspected. The decisions above are workflow
inferences from the identified methods, not local reproductions.

## Implementation status

- **Implemented and software-tested:** low-dimensional candidate suggestions,
  exact conic-filter transpose, projection derivatives, smooth worst-case loss,
  fixed-basis matrix metrics, directional checks, conditional interval comparison,
  task-weighted error allocation, serial Windows solver benchmark.
- **Local licensed pilot:** CPU and actual cuDSS solves on an official 2D optical
  scatterer fixture; accuracy agreement within that fixed model is separate from
  convergence and from any user's research-device gates.
- **Implemented native example:** COMSOL adjoint/MMA through a bounded control field,
  Helmholtz filter, mirror and projection; scalar-parameter directional checks
  and a fixed-checkpoint discrete-CVF directional check across five frequencies;
  warm-start mesh/projection continuation; binary contour reconstruction and
  bounded scalar threshold calibration. The [runnable Hadamard example](../examples/comsol-hadamard-inverse/README.md)
  checks independent source columns and signed boundary flux. It is a 2D
  material-index model, with explicit selected-mode and physical-stack limits.
  The generated CVF is stored as split-complex in this COMSOL version, with a
  near-zero second component; the continuous filter field is real. These must
  be read back separately. The discrete check supports its tested direction,
  not a claim that every gradient or resulting device is qualified.
- **Derived proposal:** allocate component precision by task sensitivity and a
  fitted cost law; its assumptions and proof are in the multi-fidelity reference.
- **Not implemented/qualified:** a general-purpose native adjoint adapter beyond
  the reviewed example, qMFKG/TuRBO, fabrication digital twin, GPU-FDTD backend, automatic
  3D acceptance or foundry yield prediction.

Keep one public skill with these on-demand routes. The runtime, optical invariants
and acceptance contracts are shared; duplicating them into independently installed
skills would add synchronization cost. Split a future member only when it has a
distinct invocation, a self-contained dependency set and independent behavioral
tests, while retaining one canonical source for shared physics rules.
