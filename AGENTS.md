# Project notes for haex-hive contributors

- When running spec-kit scripts under `.specify/scripts/`, verify the value
  of `.specify/feature.json` matches the intended feature directory before
  invoking. The scripts read that pointer as the source of truth.
- Placeholder identity `local:haex-hive` in `.haex-hive.json` will change
  to a git remote URL once the repo has one. Do not modify it during
  local prototyping.
