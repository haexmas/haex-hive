# ADR 0007: Unified Manifest v2 — Constitution Alignment

**Status**: Proposed
**Date**: 2026-08-29
**Related**: `.specify/memory/constitution.md` §Core Principles IV, V, VI
and §Scope; constitution version bump 1.2.0 → 1.3.0;
`docs/plans/2026-08-28-spec-007-unified-manifest-design.md`
(supersedes `docs/plans/2026-08-28-blueprints-and-unified-manifest-design.md`
and `docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md`).

## Context

Spec-007 (unified manifest v2) is the accepted successor to spec-006 and
to the earlier "blueprints" design draft. Its landing content requires
the constitution to move in step; otherwise spec-007 merges against
wording that names constructs the v2 schema no longer uses, and against
an unstated review-gate for schema migrations.

Four specific frictions exist against constitution v1.2.0:

1. **Principle V names a wire-level field.** The current text ties the
   opt-in allowlist to the exact string `harness_sources`. Spec-007's
   `.haex-hive.json` v2 renames that array to `atoms[]` (spec-007
   §"Consumer `.haex-hive.json` v2", line 700: "replaces v1's
   `harness_sources[]`. Uniform shape per D12."). The principle itself
   — opt-in per project via an explicit allowlist — is unchanged; only
   the field name is version-dependent.
2. **Principle IV assumes files, not directories.** The reference format
   `repository + full commit SHA + repo-relative path` is worded as if
   `path` addresses a single file. Spec-007 D11/D13 introduces atoms as
   directories containing a `manifest.json`, so a pinned `path` may
   resolve to a directory. Nothing in the invariant weakens; the wording
   just needs to admit both shapes.
3. **Principle VI has no migration guidance for versioned config
   schemas.** The `.haex-hive.json` v1 → v2 migration (spec-007 D10,
   §"v1 → v2 migration") is itself an act of self-modifying the
   consumer's harness state. Principle VI already forbids in-place
   auto-writes generally; it does not yet pin down the required shape
   for schema migrations specifically. Spec-007 fixes a concrete
   pattern: an explicit `haex migrate` verb writing a sidecar and
   printing a reviewable diff.
4. **`.haex-hive/constitution.md` has no reserved status.** Spec-007
   D2/D16 introduces a consumer-side effective (possibly LLM-merged)
   constitution file at that path, committed to the consumer repo. The
   constitution currently reserves no location for it, so consumer repos
   could collide with the path or treat it as an ordinary file.

## Decision

Amend the constitution to version 1.3.0. Four changes, all landed in the
same commit as this ADR (Governance rule: ADR + constitution update +
version bump land together).

1. **Principle V — allowlist field name is schema-version-bound.**
   Replace the naked field name `harness_sources` with wording that
   names the *concept* (per-project allowlist array) and enumerates the
   version-specific field names: `atoms[]` in `.haex-hive.json` v2,
   `harness_sources[]` in v1. The three "Implementation guidance for
   agents" paragraphs added in v1.1.0 keep their v1 field name in
   parentheses; the primary spelling is the v2 name. Rationale: the
   invariant is "opt-in per project via a named allowlist", not the
   spelling. Binding the spelling to schema version makes future v3
   schema evolutions PATCH-level for wording alone.
2. **Principle IV — `path` admits directories.** Append one sentence to
   the principle's body: `path` may address either a single
   repo-relative file or a directory whose canonical manifest is
   `<path>/manifest.json` (a spec-007 atom). The immutability rule and
   the SHA requirement do not change.
3. **Principle VI — schema migrations run through a review-gated
   `migrate` verb.** Add a clarifying paragraph: any schema migration
   of a versioned config file (`.haex-hive.json`, `install.lock`,
   `constitution.md`, `manifest.json`, or successor schemas) MUST be
   performed by an explicit migration verb that (a) writes candidate
   output to a `.migrated` sidecar, (b) prints a reviewable diff against
   the current file, (c) is deterministic given identical inputs, and
   (d) supports `--dry-run`/`--check`. No in-place rewrite of a
   versioned config file is permitted, even by agent tools.
4. **New "Reserved paths" convention under §Scope.** Add a short
   subsection: `.haex-hive/constitution.md` (consumer-side) is reserved
   for the effective (possibly merged-from-sources) constitution the
   consumer repo commits, per spec-007 D2/D16. Its provenance is either
   a straight-copy of one source atom or the LLM-merged result of many;
   in both cases it is committed content, not an agent-writable cache.

Version bump: **1.2.0 → 1.3.0** (MINOR). Justification: no principle
removed, no NON-NEGOTIABLE relaxed; Principle VI is materially expanded
(schema-migration clause), a new reserved-path convention is added, and
two other principles receive clarifying wording. Under the version-bump
rules that lands as MINOR.

## Consequences

**Immediate**:

- Spec-007 can merge without the wording contradiction the current
  Principle V spelling would cause.
- The `haex migrate` command (spec-007) is a constitutionally-required
  shape, not just a design choice.
- Consumer repos have a reserved path (`.haex-hive/constitution.md`)
  they can commit without collision.

**Follow-up (not part of this ADR)**:

- `.haex-hive.json` at the repo root re-pins to the new constitution SHA
  after this commit lands, in a separate `chore(harness-sources):`
  commit (precedent: 730bfb3).
- Spec-005 (`haex-init` binary) still ships under its current name. The
  spec-007 rename to `haex` is a separate decision tracked in spec-007's
  Spec 007 landing content and, if accepted, in a later ADR that
  supersedes the spec-005 CLI naming; this ADR does not decide it.
- Spec-006 (`docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md`)
  gains a `Status: Superseded by spec-007` header in a docs-only
  follow-up commit.

## Rejected alternatives

- **Keep `harness_sources` in the constitution and rename `atoms[]` back
  in spec-007.** Rejected: spec-007's D11/D13/D16 shape ("atom" as a
  first-class content unit with a `manifest.json`) is load-bearing well
  beyond the field name. Reverting the name here would either force
  spec-007 to keep the term `harness_sources` for something that is no
  longer a "source" in the v1 sense, or split the terminology between
  the schema and the constitution. Both are worse than a
  version-conditional field name in the constitution.
- **Amend Principle IV and V but leave the migration rule for a later
  ADR.** Rejected: spec-007's Spec 008 landing depends on the migration
  contract being constitutional, not per-spec. Deferring it forces a
  second amendment in the same release window.
- **PATCH bump (1.2.1) instead of MINOR.** Rejected: Principle VI gains
  a new normative clause and §Scope gains a new reserved-path
  convention. Both are expansions, not wording refinements.
