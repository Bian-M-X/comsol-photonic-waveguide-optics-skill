# Project Structure And Git Policy

Use this reference when creating a new simulation project, handing off work to a new conversation, or deciding what belongs in git.

## Recommended Folder Layout

```text
project-root/
  README.md
  PROJECT.md
  requirements/
    paper_targets.md
    assumptions.md
    conventions.md
  models/
    java/
    mph/                 # usually gitignored
  runs/
    YYYYMMDD_short-name/
      manifest.md
      logs/
      tables/
      figures/
      reports/
      runtime/           # prefs/config/tmp, usually gitignored
  scripts/
  data/
    raw/                 # usually gitignored if large/proprietary
    processed/
  reports/
  handoff/
```

## Naming Rules

- Include device family, variant, key parameters, sweep window, and date in artifact names.
- Use units in column names: `lambda_nm`, `gap_um`, `R_bend_um`.
- Keep stdout rows machine-parseable for screening jobs.
- Prefer ASCII filenames for scripts and generated code; reports may use local-language names if the toolchain handles UTF-8 reliably.

## What Goes In Git

Usually commit:

- source Java/Python/PowerShell scripts;
- small CSV summaries;
- markdown reports and handoffs;
- plotting code;
- parameter manifests;
- small reference figures when useful.

Usually do not commit:

- `.mph`, `.class`, `.log`, solver cache, runtime prefs/config/tmp;
- proprietary PDFs, vendor examples, screenshots, or licensed documentation;
- local absolute paths, usernames, license files, tokens, credentials;
- large raw sweeps unless the repository is explicitly designed for data artifacts.

## Handoff Requirements

Every meaningful run should leave:

- exact command or script path;
- solver route used;
- model source file;
- output table path;
- key metrics;
- known limitations;
- next recommended action.

For long projects, keep a short `handoff/latest.md` that a new conversation can read first.

## Git Repository Recommendation

Use a git repository when the project has more than one of:

- multiple model variants;
- more than one simulation campaign;
- scripts that will be reused;
- reports that will be revised;
- collaboration or future restart needs.

Keep heavy COMSOL artifacts outside git or in a separate artifact store. The git repo should make the workflow reproducible, not become a dump of binary solver outputs.
