# Phase-A Spec-Kit Requirements Checklist

## Scope and ownership

- [x] The spec says that skills may remain in `haexmas/atoms`.
- [x] The spec distinguishes publisher ownership from spaex materialization.
- [x] The spec explicitly excludes a spaex skill registry/client.
- [x] The spec explicitly excludes mandatory relocation to a separate repo.

## Contract

- [x] `external_skills` is a top-level molecule-manifest field.
- [x] External references are opaque strings and remain ordered/immutable.
- [x] An external-skill declaration requires an `install_hook`.
- [x] `atoms.skill` and `atoms.skills` are rejected.
- [x] Existing non-skill atom categories remain open.

## Delivery boundary

- [x] spaex materializes only declared file atoms.
- [x] The hook delegates the external skill installation.
- [x] External skill files are not claimed as spaex `install.lock` paths.
- [x] Hook side effects retain Spec 016's failure and reversibility limits.

## Review gate

- [x] Operator approves the spec and plan by requesting commit and PR.
- [x] Implementation resumes after approval; current schema/model slice is
  included in the reviewable PR.
