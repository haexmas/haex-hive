# Phase-A Spec-Kit Requirements Checklist

This checklist tracks design alignment, not runtime implementation evidence.
Implementation tasks remain open in `tasks.md`.

## Scope and ownership

- [x] The spec says that skills may remain in `haexmas/atoms`.
- [x] The spec distinguishes publisher ownership from spaex materialization.
- [x] The spec explicitly excludes a spaex skill registry/client.
- [x] The spec explicitly excludes mandatory relocation to a separate repo.

## Contract

- [x] `external_skills` is a top-level molecule-manifest field.
- [x] External references are structured `{repository, revision, path}`
  objects and remain ordered/immutable.
- [x] External-skill declarations do not require a provider `install_hook`.
- [x] `atoms.skill` and `atoms.skills` are rejected.
- [x] Existing non-skill atom categories remain open.

## Delivery boundary

- [x] spaex materializes only declared file atoms.
- [x] Only the explicit consumer-selected adapter installs external skills.
- [x] The consumer owns the installer, agent, scope, and explicit installation
  lifecycle through `skill_installation`.
- [x] External skill files are not claimed as spaex `install.lock` paths.
- [x] Hook side effects retain Spec 016's failure and reversibility limits.

## Review gate

- [x] The clarified design and review fixes are submitted through PR #125.
- [ ] Operator reviews and merges the clarified design before implementation.
- [ ] The structured schema/model, policy, and command implementation follows
  in a separate change; it is not included in this design-only PR.
