# Implementation Plan: Speckit Workflow Atom

**Branch**: `011-speckit-workflow-atom` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-speckit-workflow-atom/spec.md`
**Design source**: [../../docs/plans/2026-09-02-spec-011-speckit-workflow-atom-design.md](../../docs/plans/2026-09-02-spec-011-speckit-workflow-atom-design.md)

## Summary

Extend the haex-hive atom-manifest schema with a new `speckit-workflow` atom kind that carries a `workflow.yml` payload plus optional constitution fragment, extensions declaration, and per-hook scripts. On `haex install` these files publish under stable, atom-owned paths under `.specify/workflows/` and `.specify/extensions/workflow-atoms/`; the constitution fragment merges into `.haex-hive/constitution.md` via the existing multi-source flow; a new `active_workflow` field in `workflow-registry.json` decides which workflow is binding. The spec's 10 FRs, 6 SCs, and 4 user stories translate into a single-project Python subpackage `src/haex_hive/workflow/` plus a reserved namespace of new error types and exit-code slots. Reader-side, a `resolve_active_workflow(repo_root)` helper hides the fallback logic from downstream speckit skills.

## Technical Context

**Language/Version**: Python 3.12 (matches existing haex-hive baseline)
**Primary Dependencies**: no new runtime dependencies: the workflow subpackage builds on existing modules (`haex_hive.schema.validator` for JSON Schema, `haex_hive.model.consumer_manifest` for atom resolution, `haex_hive.constitution.assemble` for multi-source merge, `haex_hive.io.transaction` for rename-swap, PyYAML already vendored transitively for the bundled speckit workflow.yml). Version-constraint parsing reuses `haex_hive.model.version_constraint.VersionConstraint` from Spec 007.
**Storage**: filesystem only. Committed content lands under `.specify/workflows/<atom-id>/`, `.specify/extensions/workflow-atoms/<atom-id>/`, and (via merge) `.haex-hive/constitution.md`. Device-local state (extension installs, publisher clones) lives under `$HAEX_HIVE_STATE/` per Principle II.
**Testing**: pytest (unit + integration + conformance) and ruff (`--select F401,F841` for dead-symbol prune). Existing test tree structure extended with `tests/workflow/` subpackage mirroring `tests/install/`.
**Target Platform**: Linux, macOS, Windows CLI (single-project Python CLI baseline). No new platform-specific primitives beyond what Spec 008 already ships.
**Project Type**: single-project Python CLI (Spec 007 baseline).
**Performance Goals**: `haex install` latency budget unchanged; the workflow-atom resolver adds one YAML parse per adopted workflow atom and a single JSON Schema validate against `workflow-registry.v1.schema.json`. Sub-100ms for the resolver on typical adoption (≤5 workflow atoms). No new I/O beyond what atom resolution already does.
**Constraints**: no absolute paths (Principle II: critical because the workflow.yml payload's own path fields must be validated by `RepoRelativePath.validate` + containment check against BOTH atom root and consumer root); no secrets in workflow.yml, constitution fragment, extensions.yml (Principle I: enforced by the existing `validate_no_plaintext_secrets` for constitution fragments; workflow.yml and extensions.yml add analogous checks); SHA-pinning on adoption (Principle IV: inherited from `.haex-hive.json` atom entries); constitution-merge review gate via `--accept-merged` (Principle VI: reused unchanged); concealment guard on workflow-contributed constitution fragments (Principle VIII: reused unchanged).
**Scale/Scope**: initial target ≤5 workflow atoms per project (typical: 1). No hard cap; the registry is a list, not a keyed table, and constraint-conflict resolution is O(n²) worst-case in atom count: acceptable at this scale.

## Constitution Check

*GATE 1: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.4.0 (via `.haex-hive/constitution.md` at generation `g_20260902T121516Z_1cf8`, source pinned at revision `336eaf1e`). Every principle evaluated:

| Principle | Verdict | Rationale |
|---|---|---|
| I. No Secrets in Git (NON-NEGOTIABLE) | PASS | Workflow atoms MUST NOT contribute secrets. FR-010 already runs the concealment guard on constitution fragments; the plan adds analogous `validate_no_plaintext_secrets` to workflow.yml and extensions.yml payloads before publication. |
| II. No Local Absolute Paths in Versioned Config (NON-NEGOTIABLE) | PASS | FR-001 mandates path containment via `RepoRelativePath.validate` on every `contributes.speckit_*` source, checked against both the atom root and the consumer repo root. The plan lifts these validators from Spec 007 (existing) and adds explicit path checks for workflow.yml's own `steps[].script` fields. |
| III. Project Identity Is Device-Independent (NON-NEGOTIABLE) | PASS | Workflow atoms are addressed by `(source, revision, atom-id)` triples exactly as any other atom. Nothing in this spec touches the identity layer. |
| IV. Cross-Repo References Pin Immutable Revisions (NON-NEGOTIABLE) | PASS | Workflow atoms are adopted via `.haex-hive.json` `atoms[].revision`: the same 40-char SHA discipline as every other atom. No branch/HEAD adoption. |
| V. Constitution Is a Contract, Not a Vibe (NON-NEGOTIABLE) | PASS | Workflow-atom constitution fragments merge into a designated `## Workflow-Contributed Rules` section with atom-id byline (FR-004). Section boundaries and byline make provenance auditable. |
| VI. Self-Modifying Instructions Are Always Review-Gated (NON-NEGOTIABLE) | PASS | The constitution merge remains a two-phase `--llm=file` / `--accept-merged` operation. No new bypass introduced; the multi-source merge machinery is reused as-is. |
| VII. Trust Boundaries Are Enforced Between Devices, Not Just Between Users | N/A | This spec adds no cross-device flow; it operates within one satellite's install transaction. |
| VIII. Reviewability Is the Only Trustworthy Base | PASS | `validate_no_concealment_instructions` runs against every workflow-atom constitution fragment as part of the accepted merged assembly (FR-010). The plan additionally runs safety validators on workflow.yml and extensions.yml payload bodies before publication. |
| §Development Workflow: Declared speckit workflow adherence | PASS | This plan is produced through `/speckit-plan` per the declared `.specify/workflows/speckit/workflow.yml` step. Next step per the same workflow is `review-plan` (PR review gate) → `/speckit-tasks`. |
| §Development Workflow: phasing discipline | PASS | Spec 011 lives in Phase 2/3 territory (compiler-adjacent) but its runtime dependencies (Spec 007, Spec 008) are landed. No Phase 4+ prerequisites needed. |
| §Governance: Conventional Commits | PASS | Every commit landed via the declared workflow will use `feat(...)`, `fix(...)`, `docs(...)`, `refactor(...)`, `test(...)`, or `spec(...)` prefixes as appropriate. |

**GATE 1 verdict**: PASS. No violations, no complexity-tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/011-speckit-workflow-atom/
├── spec.md              # merged, hardened by 4 review passes (PR #51)
├── plan.md              # THIS file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── workflow-registry.v1.schema.json     # JSON Schema for .specify/workflows/workflow-registry.json
│   ├── atom-manifest.v2.speckit-workflow.md # narrative contract for the three new contributes.* fields
│   └── extensions-fragment.v1.md            # narrative contract for the workflow-atom-contributed extensions.yml shape
├── checklists/
│   └── requirements.md  # already exists (PR #51)
└── tasks.md             # Phase 2 output (/speckit-tasks: NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/haex_hive/
├── workflow/                              # NEW subpackage
│   ├── __init__.py
│   ├── resolver.py                        # resolve_active_workflow(repo_root) → WorkflowResolution
│   ├── registry.py                        # WorkflowRegistry (dataclass + JSON IO + schema-validate)
│   ├── fragment.py                        # WorkflowFragment (extensions.yml merge machinery)
│   ├── constraint.py                      # merge-and-refuse for version_constraint pairs
│   └── errors.py                          # 8 new workflow-specific HaexError subclasses (moved from install/errors.py's reserved slot per T055 note)
├── model/
│   └── consumer_manifest.py               # EXTENDED: recognises contributes.speckit_workflow / speckit_extensions / speckit_hooks
├── constitution/
│   └── assemble.py                        # EXTENDED: merges workflow-atom fragments into `## Workflow-Contributed Rules` section
├── install/
│   ├── errors.py                          # STILL empty (per T055): workflow errors live in workflow/errors.py alongside the module they belong to
│   └── (existing modules unchanged)
├── schema/
│   └── data/
│       └── workflow-registry.v1.schema.json  # NEW: vendored copy of the contract
├── util/
│   └── exit_codes.py                      # EXTENDED: 8 new numeric slots (see §Reserved diagnostic keys)
└── cli/
    └── install.py                         # EXTENDED: install() calls workflow.resolver.validate_required_extensions before publishing

tests/
└── workflow/                              # NEW test subpackage mirroring tests/install/
    ├── unit/
    │   ├── test_resolver.py
    │   ├── test_registry.py
    │   ├── test_fragment.py
    │   └── test_constraint.py
    ├── contract/
    │   ├── test_workflow_registry_schema.py
    │   └── test_atom_manifest_speckit_workflow.py
    └── integration/
        ├── test_adopt_workflow_atom.py            # US1
        ├── test_required_extension_gate.py        # US2
        ├── test_delete_orphans_workflow_atom.py   # US3
        └── test_coexistence.py                    # US4
```

**Structure Decision**: single-project Python CLI. Workflow lives in its own subpackage (`workflow/`) rather than extending `install/` because its concerns (registry, constraint merge, active-workflow selection) are orthogonal to the install transaction: install uses the resolver, but the resolver itself has its own model, contracts, and lifecycle. Path chosen matches Spec 008's convention of one subpackage per concern.

## Reserved Diagnostic Keys and Exit Codes

The spec (SC-005 tick-note) already reserved eight diagnostic keys; this plan assigns numeric exit-code slots. All slots reuse existing categories from `haex_hive.util.exit_codes` where semantically appropriate; new numeric values are reserved only where no fit exists.

| Diagnostic key | Category | Exit code | Trigger |
|---|---|---|---|
| `required-workflow-extension-missing` | Validation | reuse `VALIDATION_REFUSE` (4) | atom's `required_extensions[i].id` has no local `.specify/extensions/<id>/` |
| `required-workflow-extension-incompatible` | Validation | reuse `VALIDATION_REFUSE` (4) | installed extension version fails atom's declared constraint |
| `invalid-constraint` | Input | reuse `INPUT_REFUSE` (2) | atom's `version_constraint` is not a parseable `VersionConstraint` |
| `conflicting-constraint` | Validation | reuse `VALIDATION_REFUSE` (4) | two adopted atoms declare incompatible exact / lower-bound constraints for the same extension id |
| `optional-workflow-extension-conflict` | Warning (stderr only) | not an exit code | one atom's required + another's optional constraints conflict on the same id; required wins, optional ignored |
| `conflicting-extension-metadata` | Validation | reuse `VALIDATION_REFUSE` (4) | two adopted atoms declare the same extension id with incompatible non-constraint metadata (`homepage`, etc.) |
| `workflow-hook-mapping-invalid` | Input | reuse `INPUT_REFUSE` (2) | hook mapping in workflow-atom's extensions fragment references a non-existent, non-regular, duplicated, or out-of-namespace source |
| `workflow-atom-extension-id-collision` | Input | reuse `INPUT_REFUSE` (2) | atom's `required_extensions[]` names the same id twice within a single atom |
| `workflow-atom-reset-to-default` | Warning (stderr only) | not an exit code | downgrade removed the atom that `active_workflow` named; auto-reset to null |

**Note**: the "reuse existing categories" discipline avoids inventing new exit codes for cases that fit cleanly into the existing FR-006 exit-code table. Only if a spec review objects at the review-plan gate would we add fresh numeric slots.

## Phases

### Phase 0: Outline & Research (produces `research.md`)

Open decisions the spec left implicit that the plan resolves during research:

1. **Registry schema shape**: is `workflow-registry.json` a strictly-versioned schema, or a loose JSON document with an ignored-unknown-fields policy? Decision (research): strictly versioned via `workflow-registry.v1.schema.json`, reject unknown top-level fields to catch typos, allow unknown per-workflow entries under `workflows.<id>` to accommodate future speckit-community fields.
2. **Constraint merge algorithm**: how do we combine two exact-or-lower-bound constraints for the same extension id in an order-independent way? Decision (research): normalise to canonical form (exact wins over lower-bound; two lower bounds merge to the higher; exact-vs-exact must match or refuse; exact-vs-lower-bound requires exact ≥ lower). Documented as an algorithm in research.md and mirrored in `workflow/constraint.py`.
3. **Extension-directory naming discipline**: should atom-contributed hook scripts live under `.specify/extensions/<atom-id>/` (namespace overlap with speckit-community extensions) or under a reserved `.specify/extensions/workflow-atoms/<atom-id>/` sub-namespace? Decision (research, ratified by spec's US1 acceptance scenario 1): reserved `workflow-atoms/` prefix. Prevents any possibility of an atom shadowing a legitimately-installed community extension.
4. **Constitution fragment merge byline format**: how is a workflow-atom's fragment attributed inside the shared `## Workflow-Contributed Rules` section? Decision (research): each fragment prefixed by a subsection heading `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` followed by the fragment body. Multiple fragments append in include-order under the shared section header.
5. **Diagnostic-key exit-code discipline**: reuse existing category codes vs new numeric slots? Decision (research, already anchored in §Reserved Diagnostic Keys above): reuse existing codes with disambiguation via the diagnostic key string. No new numeric slots needed for MVP.

### Phase 1: Design & Contracts (produces `data-model.md`, `contracts/`, `quickstart.md`)

Prerequisites: research.md complete.

**data-model.md** captures five new frozen dataclasses:

- `WorkflowAtomManifest(atom_id, workflow_path, constitution_path?, extensions_path?, hooks_dir?)`: the atom-manifest v2 extension. Constructor validates all paths via `RepoRelativePath.validate` + containment.
- `WorkflowRegistry(schema_version, active_workflow, workflows: dict[str, WorkflowEntry])`: the shape of `.specify/workflows/workflow-registry.json`. `WorkflowEntry(id, name, version, source: Literal["bundled", "atom"], installed_at, updated_at, atom_id?)`. IO via `from_json` / `to_json_bytes` with strict schema-validate.
- `WorkflowFragment(atom_id, revision, required_extensions, optional_extensions, hooks)`: parsed representation of an atom-contributed extensions.yml fragment. `required_extensions` / `optional_extensions` are `list[ExtensionRequirement(id, version_constraint, homepage?)]`.
- `ResolvedExtensionRequirement(extension_id, effective_constraint, sources: list[tuple[atom_id, kind]])`: result of merging fragments across all adopted workflow atoms. Records which atoms contributed to each requirement for diagnostics.
- `WorkflowResolution(active_id, workflow_path, source: Literal["bundled", "atom", "fallback"], diagnostics: list[str])`: return value of `resolve_active_workflow(repo_root)`. `fallback` when `active_workflow` names an unresolvable id.

**contracts/**:

- `workflow-registry.v1.schema.json`: JSON Schema for the registry file. `additionalProperties: false` at the top level; `workflows.<id>` accepts unknown fields for forward compat. Enum-constrained `source` field. `active_workflow` is `string | null`.
- `atom-manifest.v2.speckit-workflow.md`: narrative contract describing the three new `contributes.*` fields, their path-validation rules, and their publication targets. References Spec 007's atom-manifest schema as the base and this contract as the delta.
- `extensions-fragment.v1.md`: narrative contract for the atom-contributed extensions.yml shape. Includes the constraint-merge algorithm from research.md as the canonical reference.

**quickstart.md**: operator walkthrough:
1. Author or fork a workflow atom (publisher-side, out-of-scope for detailed walk-through)
2. Adopt via `.haex-hive.json` with pinned SHA
3. Run `haex install --llm=file` → `--accept-merged` (constitution fragment review)
4. Set `active_workflow` to the atom's id in `workflow-registry.json`
5. Verify: `resolve_active_workflow` returns the atom's workflow.yml
6. Downgrade: remove atom from `.haex-hive.json`, re-run `haex install`, confirm cleanup

**Agent context update**: after Phase 1 lands, update the `<!-- SPECKIT START -->` / `<!-- SPECKIT END -->` markers in project-root `CLAUDE.md` (if the file exists at repo root: it does not, per earlier inventory; skip until an operator adds one) to reference this plan file.

### Phase 2: NOT covered by /speckit-plan

`tasks.md` is `/speckit-tasks`'s responsibility. This plan explicitly stops before task decomposition.

## Constitution Check (Post-Design Re-evaluation)

*GATE 2: Must pass after Phase 1 design artifacts are drafted, before /speckit-tasks.*

Re-evaluated against the same principles after data-model + contracts + quickstart draft:

- **Principle I / VIII**: the design preserves the concealment / secret guards (FR-010 unchanged; plan adds analogous checks to workflow.yml and extensions.yml payloads).
- **Principle II**: `WorkflowAtomManifest`'s constructor validates all paths at parse time; `workflow.yml`'s own `steps[].script` and `hooks[].script` fields are validated in `workflow/fragment.py` before publication.
- **Principle IV**: `WorkflowRegistry.WorkflowEntry.atom_id` (when `source == "atom"`) is a reverse-DNS id; the underlying `revision` is recorded in `install.lock.atoms[]` already (Spec 008 machinery, unused-and-unchanged here).
- **Principle VI**: constitution merge remains gated by `--accept-merged`. `## Workflow-Contributed Rules` section is populated only through the merge candidate; no direct write.
- **§Development Workflow**: `resolve_active_workflow` is what the constitution's declared-workflow bullet resolves to at read time. The design closes the loop.

**GATE 2 verdict**: PASS after Phase 1. No design decisions violate any principle.

## Complexity Tracking

*Empty. No unjustified deviations from the constitution.*

---

## Post-Plan Follow-up Reminders

- After `/speckit-tasks` produces `tasks.md`, run `/speckit-analyze` to cross-check consistency against spec + plan + tasks.
- After landing Spec 011 (`/speckit-implement` complete + PR merged), a PATCH-level constitution amendment MAY retire the "planned Spec 011" forward-reference in the v1.4.0 §Development Workflow bullet.
- `haex install --verify-only` (Spec 008 T037, deferred) will read `WorkflowResolution` to report which workflow is binding. Wiring is documented in FR-008 but the flag itself is out-of-scope until T037 lands.
