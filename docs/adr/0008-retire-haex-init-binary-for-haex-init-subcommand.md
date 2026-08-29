# ADR 0008: Retire the `haex-init` Binary in Favour of `haex init`

**Status**: Accepted
**Date**: 2026-08-29
**Related**: `docs/plans/2026-08-28-spec-007-unified-manifest-design.md`
(D17 CLI surface, §"v1 → v2 migration"); Spec 005
(`specs/005-haex-init/`, `docs/haex-init.md`); ADR 0007 (constitution
alignment with unified-manifest v2).

## Context

Spec 005 shipped a standalone Python CLI named `haex-init`
(`.specify/scripts/haex-init`, 94 KB, stdlib-only) that bootstraps a
project's `.haex-hive.json` v1 and pins the constitution SHA. It was
correct for the v1 schema and the Phase-1 operator flow it was written
for.

Spec 007 (unified manifest v2) introduces a substantially larger CLI
surface than initialization: `install`, `add`, `update`, `remove`,
`verify`, `migrate`, `constitution assemble`, `store prune`, and
others. D17 of spec-007 proposes a single top-level binary `haex` with
these as subcommands, and states that `haex-init` breaks at the v2
boundary — `haex-init migrate` is explicitly not an alias.

Two shapes were available for the transition:

1. **Keep `haex-init` and add a sibling `haex` binary for v2.** Two
   binaries; the operator must know which one to invoke depending on
   which schema version their project runs. Cross-refs from every doc
   and every future spec would have to name the right one.
2. **Retire `haex-init` and make initialization the `haex init`
   subcommand of a single `haex` binary.** One CLI surface across
   schema versions. Legacy operators re-invoke the same binary they
   already used for the migration verb.

Option 2 was decided on 2026-08-29 by the operator ("`haex-init` fliegt
raus und wird zu `haex init`").

## Decision

Retire `haex-init` as a separate binary. All initialization behavior
that Spec 005 assigns to `haex-init` moves under `haex init` as a
subcommand of the unified `haex` binary introduced by Spec 007.

Scope of this ADR:

- **Decision recorded.** `haex-init` is no longer part of the target
  CLI surface. `haex init` is the canonical spelling from Spec 007
  onwards.
- **Spec 005 status update.** Spec 005 and `docs/haex-init.md` gain a
  "Superseded by Spec 007 CLI surface" banner naming this ADR and the
  spec-007 design doc. Spec 005 remains the authoritative
  documentation for the v1 `haex-init` binary that is currently
  installed on operator machines; it is not deleted.
- **`--pin-constitution` behavior** carries over to `haex init
  --pin-constitution` with the same semantics; no functional change is
  chartered by this ADR.
- **Migration entry-point** for v1 → v2 remains `haex migrate` (spec-007
  D10). This ADR does not re-open that naming.

Explicitly **not decided by this ADR**:

- The implementation task list for producing the `haex` binary (that is
  Spec 007's landing content and any follow-up specs it invokes).
- Whether the retired `haex-init` script is deleted from
  `.specify/scripts/` on v2 boundary or left as a read-only legacy
  artifact (Spec 007 / Spec 008 decides).
- Whether a transitional `haex-init` wrapper that execs `haex init`
  ships during a deprecation window (Spec 007 may add this if the
  operator installed base warrants it; this ADR does not require it).
- Documentation refactoring of `specs/005-haex-init/plan.md`,
  `tasks.md`, `contracts/`, or `data-model.md`. Those describe a
  shipped v1 artifact and are frozen; new v2 initialization behavior
  is documented in Spec 007's deliverables, not by editing Spec 005.

## Consequences

**Immediate**:

- Spec 005's `spec.md` and `docs/haex-init.md` get a superseded-by
  banner in the same commit that lands this ADR, so no reader lands on
  those docs assuming they describe the v2 CLI.
- The name `haex-init` in any new spec, plan, or ADR is grounds for
  refusal — the canonical spelling is `haex init` (space, subcommand).
  Existing Spec 005 references and pre-v1.3.0 constitution wording
  (`Principle V unauthorized inheritance` example, etc.) are
  grandfathered as historical.
- Cross-references from spec-007 to Spec 005 (e.g., `haex_hive_version:
  "1"` migrations) name `haex-init` only as the retired v1 tool, not as
  a supported target.

**Follow-up (not in this ADR)**:

- The `haex` binary is delivered by Spec 007 (or Spec 007's implementation
  spec, TBD). Its bootstrap behavior for `haex init` is defined there,
  reusing the Spec 005 contracts as the semantic baseline.
- A future ADR MAY chose to delete `.specify/scripts/haex-init`
  entirely once Spec 007 is landed and operator machines have migrated;
  this ADR leaves the file in place.

## Rejected alternatives

- **Two-binary future** (option 1 above). Rejected: doubles the
  cross-reference burden across every doc, every operator-facing
  message, and every future ADR. It also means the constitution's
  Principle V allowlist wording would need to be aware of which binary
  wrote the file, which is worse than the schema-version-bound wording
  ADR 0007 already introduced.
- **Rename to a third name** (e.g., `hive`, `hh`). Rejected: spec-007
  D17 already commits to `haex` as the reverse-DNS-consistent brand
  root; changing it here would be a separate scope decision without a
  triggering constraint.
- **Keep `haex-init` and treat `haex` as a Phase-2 addition.**
  Rejected: leaves the v2 migration verb (`haex migrate`) orphaned in a
  binary that does not exist for v1 users. Spec 007 already found this
  contradiction and refuses `haex-init migrate` as an alias.
