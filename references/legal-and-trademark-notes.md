# Legal and Trademark Notes

This reference is a practical publication checklist, not legal advice.

## Goals

Reduce risk when publishing this skill project by ensuring it:

- does not use commercial solver trademarks in the project or skill name
- does not imply affiliation, authorization, sponsorship, or endorsement
- does not redistribute proprietary software, official docs, model files, screenshots, logos, or license files
- uses trademarks only to identify compatible third-party software environments
- states that users must supply their own valid licenses
- avoids publishing local machine paths, user names, license details, model outputs, and private project files

## Trademark-Safe Wording

Project names, repository names, folders, and skill names should avoid third-party trademarks.

Acceptable project-style names:

- `photonic-waveguide-optics-skill`
- `integrated-photonics-simulation-skill`
- `waveguide-interferometer-skill`

Avoid names that incorporate third-party marks.

In body text, refer to third-party software only when needed for compatibility. In Markdown, `&reg;` may be used to render the registered-trademark symbol while keeping the source file ASCII-safe:

```text
compatible with licensed COMSOL&reg; Multiphysics&reg; simulation software installations
```

Include attribution:

```text
COMSOL and COMSOL Multiphysics are registered trademarks of COMSOL AB.
```

Include non-affiliation:

```text
This project is independent and is not affiliated with, endorsed by, sponsored by, or authorized by COMSOL AB.
```

## Content Guardrails

Do not include:

- official product logos or brand artwork
- official screenshots
- official example model files
- copied official manual text
- license files
- installer files or binaries
- generated project names that contain third-party marks
- local absolute paths, license-server details, private paper PDFs, or confidential project data

Self-authored workflow notes, original scripts, and compatibility instructions are acceptable when they do not copy proprietary materials and do not imply endorsement.

## Publication Checklist

Before publishing:

- [x] Repository name contains no third-party solver trademark.
- [x] `SKILL.md` skill name contains no third-party solver trademark.
- [x] `README.md` includes non-affiliation language.
- [x] `NOTICE.md` includes trademark attribution.
- [x] No logos, screenshots, manuals, official examples, or binaries are included.
- [x] Users are told to provide their own valid licenses.
- [x] MIT or other license is clearly limited to this repository's original text/scripts.
- [x] Any software references are compatibility statements, not endorsement claims.
- [x] No author-specific absolute installation paths or local project paths are included.
- [x] Helper scripts require `-SolverRoot` or `PHOTONIC_SOLVER_ROOT` instead of hard-coded local paths.

## Official Sources Consulted

- COMSOL trademark and brand guidelines: https://www.comsol.com/trademarks
- COMSOL knowledge base guidance on referencing the software in publications: https://www.comsol.com/support/knowledgebase/1223
- COMSOL license option summary, which points users to the applicable license agreements: https://www.comsol.com/products/licensing
