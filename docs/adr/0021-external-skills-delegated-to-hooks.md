# ADR 0021: Delegate external skill installation to molecule hooks

**Status**: Accepted
**Date**: 2026-09-14

## Context

Agent Skills distribution tools already own discovery and installation. spaex
owns pinned molecule composition and deterministic file publication, but it is
not a skill registry. Treating a registry reference as an ordinary atom path
would make spaex copy content it does not own and would make lockfile paths
misleading.

## Decision

Molecule manifests may declare an opaque `external_skills` reference list. The
list is metadata and requires a molecule-declared `install_hook`; the hook may
invoke skills.sh or agentskills.io using the existing Spec 016 trust and
failure semantics. The referenced skill may live in the same publisher repo
as the molecule. The old `skill` and `skills` atom categories are rejected.

spaex does not resolve registry references, pin their content, or install them
directly.

## Consequences

- Publisher manifests are intentionally breaking and target the spaex 5.x
  release line.
- External registry versioning remains outside `.spaex/install.lock`.
- No Node or registry SDK dependency is added to spaex.
- Migration of publisher repositories is required before their next release.
