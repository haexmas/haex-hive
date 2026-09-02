# Implementation Plan: Speckit Workflow Atom (simplified)

**Branch**: `011-plan-simplified` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-speckit-workflow-atom/spec.md`

## Summary

Under the 2026-09-02 simplification amendment (PR #54 merged), Spec 011 delivers a `speckit-workflow` atom kind that a project pins via `.haex-hive.json` to bind a specific speckit workflow. On `haex install` the atom's `workflow.yml` publishes at `.specify/workflows/<atom-id>/workflow.yml`, its hook scripts publish under the reserved namespace `.specify/extensions/workflow-atoms/<atom-id>/`, its constitution fragment merges into the shared `## Workflow-Contributed Rules` section of `.haex-hive/constitution.md`, and its extensions fragment merges with the consumer-owned `.specify/extensions.local.yml` to regenerate the deterministic output `.specify/extensions.yml`. Binding is implicit from adoption: one workflow atom in `.haex-hive.json` -> that workflow is binding; none -> the bundled speckit workflow is binding. Adopting two `speckit-workflow` atoms refuses with `key=multiple-workflow-atoms-refused`. No registry file, no `active_workflow` selector, no provenance cache; the reader helper `resolve_active_workflow(repo_root)` inspects `.haex-hive.json` directly.

## Technical Context

**Language/Version**: Python 3.12 (matches existing haex-hive baseline).
**Primary Dependencies**: no new runtime dependencies. The workflow subpackage builds on `haex_hive.schema.validator` (JSON Schema), `haex_hive.model.consumer_manifest` (atom resolution), `haex_hive.model.version_constraint.VersionConstraint` (Spec 007 grammar), `haex_hive.constitution.assemble` (multi-source merge), `haex_hive.io.transaction` (rename-swap), and PyYAML (already vendored transitively for the bundled speckit workflow.yml).
**Storage**: filesystem only. Committed content lands under `.specify/workflows/<atom-id>/` (atom-owned), `.specify/extensions/workflow-atoms/<atom-id>/` (reserved atom namespace), `.specify/extensions.yml` (generated output), and `.haex-hive/constitution.md` (via merge). The consumer-owned `.specify/extensions.local.yml` is the local source and is never touched by the runtime. Device-local state (publisher clones) lives under `$HAEX_HIVE_STATE/`.
**Testing**: pytest (unit + contract + integration) and ruff (with `--select F401,F841` for dead-symbol prune). New tree `tests/workflow/` mirrors `tests/install/`; integration coverage includes cross-root crash/retry points and downgrade convergence.
**Target Platform**: Linux, macOS, Windows CLI (single-project Python CLI baseline).
**Project Type**: single-project Python CLI (Spec 007 baseline).
**Performance Goals**: `haex install` latency unchanged. Workflow pipeline adds at most one YAML parse for the adopted atom's fragment (FR-006 forbids multiple) plus one parse for `.specify/extensions.local.yml` when present. Sub-100ms on typical adoption.
**Constraints**: no absolute paths (Principle II, critical because workflow.yml payload's own `steps[].script` fields must be containment-checked); no secrets (Principle I); SHA-pinning (Principle IV, inherited); constitution-merge review gate (Principle VI, reused via `--accept-merged`); concealment guard (Principle VIII, reused).
**Scale/Scope**: at most one workflow atom per project (FR-006 enforced). No hard cap on `required_extensions[]` or `hooks.<stage>[]` entries.

## Constitution Check

*GATE 1: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.4.0. Every principle evaluated:

| Principle | Verdict | Rationale |
|---|---|---|
| I. No Secrets in Git (NON-NEGOTIABLE) | PASS | `validate_no_plaintext_secrets` runs on workflow.yml + extensions fragment + local source before publication. |
| II. No Local Absolute Paths in Versioned Config (NON-NEGOTIABLE) | PASS | FR-001 mandates path containment via `RepoRelativePath.validate`; the plan additionally validates workflow.yml's own `steps[].script` fields and every hook mapping destination. |
| III. Project Identity Is Device-Independent (NON-NEGOTIABLE) | PASS | Nothing in this spec touches the identity layer. |
| IV. Cross-Repo References Pin Immutable Revisions (NON-NEGOTIABLE) | PASS | Workflow atoms adopted via `.haex-hive.json` `atoms[].revision` (40-char SHA). No branch/HEAD. |
| V. Constitution Is a Contract, Not a Vibe (NON-NEGOTIABLE) | PASS | FR-004 designates a single `## Workflow-Contributed Rules` section with atom-id byline. |
| VI. Self-Modifying Instructions Are Always Review-Gated (NON-NEGOTIABLE) | PASS | Constitution merge remains two-phase (`--llm=file` + `--accept-merged`). |
| VII. Trust Boundaries Are Enforced Between Devices | N/A | This spec has no cross-device flow. |
| VIII. Reviewability Is the Only Trustworthy Base | PASS | `validate_no_concealment_instructions` runs on the workflow atom's constitution fragment (FR-010). |
| § Development Workflow: Declared speckit workflow adherence | PASS | This plan is produced through `/speckit-plan`. Next: `review-plan` -> `/speckit-tasks`. |
| § Development Workflow: phasing discipline | PASS | Spec 011 runtime dependencies (Spec 007, Spec 008) are landed. |
| § Governance: Conventional Commits | PASS | Every commit uses `feat/fix/docs/refactor/test/plan/spec(...)` prefixes. |

**GATE 1 verdict**: PASS. No violations, no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/011-speckit-workflow-atom/
├── spec.md
├── plan.md                                     # THIS file
├── research.md                                 # Phase 0 output
├── data-model.md                               # Phase 1 output
├── quickstart.md                               # Phase 1 output
├── contracts/
│   ├── atom-manifest.v2.speckit-workflow.md
│   ├── extensions-fragment.v1.md
│   ├── extensions-local.v1.md
│   └── extensions-generated.v1.md
├── checklists/
│   └── requirements.md
└── tasks.md                                    # /speckit-tasks output (separate PR)
```

### Source Code (repository root)

```text
src/haex_hive/
├── workflow/                                   # NEW subpackage
│   ├── __init__.py                             # re-exports resolver + public dataclasses
│   ├── resolver.py                             # resolve_active_workflow + validate_required_extensions + load_installed_extension_metadata
│   ├── fragment.py                             # WorkflowFragment + ExtensionRequirement + HookEntry
│   ├── local_source.py                         # LocalExtensionsSource + load_local_source
│   ├── merge.py                                # merge_extensions -> GeneratedExtensionsYml
│   ├── constraint.py                           # canonical constraint reduction (atom-vs-local)
│   ├── publisher.py                            # publish_workflow_atom + cross-root generation coordinator + delete-orphans hook
│   └── errors.py                               # 9 diagnostic subclasses
├── model/consumer_manifest.py                  # EXTENDED: parses the consumer manifest; workflow multiplicity is checked after atom resolution
├── constitution/assemble.py                    # EXTENDED: integrates workflow atom fragment into ## Workflow-Contributed Rules
├── install/errors.py                           # STILL empty (workflow errors live in workflow/errors.py)
├── util/exit_codes.py                          # EXTENDED: comment-only, reuses existing categories
└── cli/install.py                              # EXTENDED: install() calls the workflow pipeline before constitution merge

tests/
└── workflow/                                   # NEW test subpackage mirroring tests/install/
    ├── unit/                                   # test_resolver.py, test_fragment.py, test_local_source.py, test_merge.py, test_constraint.py
    ├── contract/                               # test_atom_manifest_speckit_workflow.py, test_extensions_{fragment,local,generated}_shape.py
    └── integration/                            # US1-4 integration tests
```

**Structure Decision**: single-project Python CLI. Workflow lives in its own subpackage; `install/` remains a consumer of `workflow/` at wiring time.

## Reserved Diagnostic Keys and Exit Codes

Nine diagnostic keys reserved. Category-reuse per Spec 008 practice:

| Diagnostic key | Category | Exit code | Trigger |
|---|---|---|---|
| `required-workflow-extension-missing` | Validation | `VALIDATION_REFUSE` (4) | `required_extensions[i].id` has no local `.specify/extensions/<id>/` |
| `required-workflow-extension-incompatible` | Validation | `VALIDATION_REFUSE` (4) | Installed extension's `extension.yml` version fails the atom's constraint |
| `invalid-constraint` | Input | `INPUT_REFUSE` (2) | Fragment or local source declares an unparseable `version_constraint` |
| `conflicting-constraint` | Validation | `VALIDATION_REFUSE` (4) | Atom and local declare same extension id with incompatible constraints |
| `optional-workflow-extension-conflict` | Warning (stderr) | 0 | Atom-vs-local optional mismatch; incompatible optional dropped |
| `conflicting-extension-metadata` | Validation | `VALIDATION_REFUSE` (4) | Non-constraint metadata (`homepage`) disagrees for same id |
| `workflow-hook-mapping-invalid` | Input | `INPUT_REFUSE` (2) | Hook mapping references missing/non-regular/duplicate/out-of-namespace source |
| `workflow-atom-extension-id-collision` | Input | `INPUT_REFUSE` (2) | Reserved `workflow-atoms/` namespace occupied by community extension, or same id declared twice within a single fragment list |
| `multiple-workflow-atoms-refused` | Input | `INPUT_REFUSE` (2) | `.haex-hive.json` adopted set has 2+ atoms with `contributes.speckit_workflow` |

## Phases

### Phase 0: Outline & Research (produces `research.md`)

Eight research decisions:

1. **R1 registry-alternative**: no registry file needed under one-active-per-repo; adoption alone signals binding.
2. **R2 extensions ownership boundary**: `.specify/extensions.local.yml` (consumer input) disjoint from `.specify/extensions.yml` (generated output).
3. **R3 multi-workflow refusal placement**: after publisher and atom manifests are resolved and validated, the workflow pipeline counts `contributes.speckit_workflow` fields and refuses before fragments or publication; `ConsumerManifest.from_json` only validates consumer-owned data.
4. **R4 constraint-merge algorithm**: simplified to atom-vs-local reduction (no cross-atom).
5. **R5 reader resolution fallback**: typed `WorkflowResolution` with `source: atom|bundled` and diagnostics field.
6. **R6 workflow.yml payload safety**: path containment + no-secrets + no-concealment on the payload body.
7. **R7 publisher-side atom directory shape**: reference structure a workflow-atom publisher must produce.
8. **R8 hook identity for replace-by-identity**: identity = `(stage, extension, command, script)` tuple (load-bearing detail from PR #54 hardening).

### Phase 1: Design & Contracts (produces `data-model.md`, `contracts/`, `quickstart.md`)

Prerequisites: research.md complete.

**data-model.md**: ten dataclasses (`WorkflowAtomManifest`, `WorkflowFragment`, `ExtensionRequirement`, `HookEntry`, `LocalExtensionsSource`, `GeneratedExtensionsYml`, `MergedRequirement`, `ExtensionRequirementSource`, `WorkflowResolution`, `InstalledExtensionMetadata`). The implementation and workflow tests cover `ExtensionRequirementSource` through `MergedRequirement.sources`.

**contracts/**:
- `atom-manifest.v2.speckit-workflow.md`: three new `contributes.*` fields + orphan-refusal cases.
- `extensions-fragment.v1.md`: atom-contributed extensions.yml fragment shape.
- `extensions-local.v1.md` (NEW from PR #54): consumer-owned `.specify/extensions.local.yml` shape + ownership boundary.
- `extensions-generated.v1.md` (NEW): generated output shape + deterministic serialisation.

**quickstart.md**: 9-step walkthrough including adoption against a consumer with existing `.specify/extensions.local.yml` entries.

**Agent context update**: no repo-root `CLAUDE.md`; skip.

### Phase 2: NOT covered by /speckit-plan

`tasks.md` is `/speckit-tasks`'s responsibility.

## Constitution Check (Post-Design Re-evaluation)

*GATE 2: Must pass after Phase 1 design artifacts are drafted, before /speckit-tasks.*

Re-evaluated after data-model + contracts + quickstart:

- **Principle I / VIII**: workflow.yml + fragment + local source pass secret + concealment validators before publication.
- **Principle II**: containment on every path including workflow.yml's own `steps[].script` fields and hook destinations.
- **Principle IV**: atom SHA-pinned.
- **Principle VI**: constitution merge unchanged.
- **Principle V**: byline provenance in `## Workflow-Contributed Rules` section.
- **§ Development Workflow adherence**: `resolve_active_workflow` resolves the declared-workflow bullet at read time.
- **New in this simplified plan**: extensions ownership split defends against silent operator-state loss.

**GATE 2 verdict**: PASS after Phase 1. No design decisions violate any principle.

## Complexity Tracking

*Empty. The simplified spec + this plan carry no unjustified deviations.*

---

## Post-Plan Follow-up Reminders

- After `/speckit-tasks` produces `tasks.md`, run `/speckit-analyze` to cross-check consistency.
- After Spec 011 lands, a PATCH constitution amendment MAY retire the "planned Spec 011" forward-reference in v1.4.0.
- `haex install --verify-only` (Spec 008 T037, deferred) will report `WorkflowResolution` once it lands; documented in FR-008 but out of scope until T037.
