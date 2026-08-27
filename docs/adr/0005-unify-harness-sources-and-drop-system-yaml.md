# ADR 0005: Unify `harness_sources` in `.haex-hive.json` and drop `.specify/system.yaml`

**Status**: Accepted
**Date**: 2026-08-27
**Related**: [Spec 004 — Cross-Repo References (Phase 1)](../../specs/004-cross-repo-refs/spec.md);
[Spec 004 design doc](../plans/2026-08-27-spec-004-cross-repo-refs-design.md);
supersedes the two-file arrangement introduced by ADR 0002.

## Context

Spec 003 shipped `.haex-hive.json` as the repo-scoped marker but kept
two allowlist-adjacent slots split across two files:

- `.haex-hive.json.constitution` — a single object naming the pinned
  constitution reference (`repository`, `revision`, `path`).
- `.specify/system.yaml.external_sources.allowed` — a list of URLs
  the project opts in to consume harness content from.

The split was historical: the constitution slot predated the
external-sources concept (Spec 001), and `system.yaml` predates the
`.haex-hive.json` marker (Spec 002/003). By the time Spec 004 arrived
to introduce cross-repo Git-SHA-pinned references, three problems
were visible:

1. **Two files for one concern.** Editing an allowlist meant reading
   both `.haex-hive.json` (for the constitution) and `.specify/system.yaml`
   (for everything else) to answer "what may this repo consume?"
2. **Two grammars.** JSON for one, YAML for the other. A canonical
   JSON Schema for one couldn't cover the other without a converter.
3. **Redundant concepts.** The `constitution` slot was a role-carrying
   external-source entry in disguise — it named a concrete
   `repository + revision + path` triple. Modelling it as a special
   sibling of `external_sources` obscured that.

## Decision

Spec 004 collapses both slots into one array under a new name in
`.haex-hive.json`:

- Rename `external_sources` → `harness_sources`.
- Flatten: no more nested `.allowed` sub-object.
- Merge the top-level `constitution` slot into the same array as a
  role-tagged entry (`{"role": "constitution", ...}`).
- Delete `.specify/system.yaml` entirely — `harness_sources` is now the
  sole allowlist location per Principle V.

### Pre-shape (Spec 003)

`.haex-hive.json`:

```json
{
  "haex_hive_version": "1",
  "identity": "local:haex-hive",
  "constitution": {
    "repository": "self",
    "revision": "<sha>",
    "path": ".specify/memory/constitution.md",
    "note": "..."
  },
  "external_sources": { "allowed": [] },
  "groups": [],
  "active_feature": null
}
```

`.specify/system.yaml`:

```yaml
system:
  id: haex-hive
external_sources:
  allowed: []
```

### Post-shape (Spec 004)

`.haex-hive.json`:

```json
{
  "haex_hive_version": "1",
  "identity": "local:haex-hive",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "<sha>",
      "path": ".specify/memory/constitution.md"
    }
  ],
  "groups": [],
  "active_feature": null
}
```

`.specify/system.yaml` is gone.

## Consequences

**Positive**

- One file, one grammar, one JSON Schema
  (`.specify/schemas/haex-hive.schema.json`) covers the entire opt-in
  surface. Editors validate inline; the `spec-resolve` tool and the
  schema are provably in agreement (see Spec 004 US3).
- The constitution reference is no longer a special case in the code
  paths — it is a `harness_sources` entry with `role: "constitution"`,
  matched by the same allowlist logic as everything else.
- Adding a new named role in the future is a schema-enum widening
  (PATCH-level constitution change), not a new top-level field.

**Neutral**

- Principle V's wording changes from citing `.specify/system.yaml`'s
  `external_sources.allowed` to citing `.haex-hive.json`'s
  `harness_sources`. This is a PATCH-level constitution bump
  (v1.1.0 → v1.1.1); no principle removed, added, or relaxed.

**Negative / migration cost**

- Every consuming repo needs to migrate their `.haex-hive.json` and
  delete their `.specify/system.yaml`. Only `haex-hive` itself is
  affected today (single-operator Phase 1). Downstream consumers will
  hit this when they onboard.
- Older ADRs (0002 in particular) still refer to `external_sources`
  and `.specify/system.yaml` by name. They are left intact as
  historical record; grep results outside `docs/adr/`, `docs/plans/`,
  and `specs/00[123]-*/` should be zero after Spec 004 lands
  (Spec 004 SC-008).

## Alternatives considered

- **Amending ADR 0002 in place.** Rejected: ADRs are append-only. New
  decisions get new ADRs; superseded ADRs retain their text and gain
  a "superseded by" link. ADR 0002 will be marked superseded in a
  follow-up housekeeping commit.
- **Keeping `.specify/system.yaml` as a YAML-only surface for
  non-JSON-friendly editors.** Rejected: modern editors handle both
  transparently, and the schema-canonicalization win from a single
  JSON file outweighs any theoretical YAML preference. The two-file
  arrangement's ergonomic cost (edit two files, remember which slot
  is where) is measurably worse than YAML-vs-JSON typing preference.
- **Keeping the `constitution` slot at top level with a pointer into
  `harness_sources`.** Rejected as complexity for no gain — the whole
  point of the collapse is that the constitution ref is not special.

## Traceability

- Design authority: [Spec 004 design doc](../plans/2026-08-27-spec-004-cross-repo-refs-design.md).
- Spec: [specs/004-cross-repo-refs/spec.md](../../specs/004-cross-repo-refs/spec.md)
  (FR-007, FR-018, FR-019 all name this rename).
- Data model: [specs/004-cross-repo-refs/data-model.md](../../specs/004-cross-repo-refs/data-model.md).
- Schema: [.specify/schemas/haex-hive.schema.json](../../.specify/schemas/haex-hive.schema.json).
- Constitution wording change: Principle V, v1.1.0 → v1.1.1 (this
  commit).
