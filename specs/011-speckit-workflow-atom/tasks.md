# Tasks: Speckit Workflow Atom

**Input**: Design documents from `/specs/011-speckit-workflow-atom/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included. Every FR needs a testable implementation, every SC needs a test task, and every contract needs schema-level coverage. Test task types are unit, contract, integration.

**Checkbox freshness is load-bearing.** When a task is completed, tick its checkbox in the same commit as the task's output, or at the latest in the next commit, before starting the next task. Handoff queries ("what was just done, what remains, what is the next step?") read this file's checkbox state as the primary state document. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4). Setup, Foundational, and Polish tasks carry no story label.
- Include exact file paths in descriptions.

## Path Conventions

Single-project Python CLI (Spec 007 baseline). Source lives under [src/haex_hive/](../../src/haex_hive/); tests under [tests/](../../tests/). Spec 011 adds a new `workflow/` subpackage plus a `tests/workflow/` subtree; extends `install/`, `constitution/`, and `schema/` in place; no restructure elsewhere. See [plan.md §Project Structure](./plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Wire the new workflow subpackage and its test tree into the existing tree so later phases can land into pre-created skeletons without one-off scaffolding.

- [ ] T001 Create workflow subpackage skeleton at [src/haex_hive/workflow/__init__.py](../../src/haex_hive/workflow/__init__.py) with module docstring; add stub files `resolver.py`, `registry.py`, `fragment.py`, `constraint.py`, `errors.py`, each with only a module docstring.
- [ ] T002 Create workflow test tree directories: `tests/workflow/contract/`, `tests/workflow/integration/`, `tests/workflow/unit/`. Match the `tests/install/*` convention: omit `__init__.py` files to avoid pytest package-name collisions with the real `haex_hive.workflow` package.
- [ ] T003 Extend [src/haex_hive/util/exit_codes.py](../../src/haex_hive/util/exit_codes.py) diagnostic-key documentation: append comments naming the nine diagnostic keys reserved for Spec 011 (see [plan.md §Reserved Diagnostic Keys](./plan.md)). Do not add new numeric slots; the plan mandates category reuse (`INPUT_REFUSE=2` and `VALIDATION_REFUSE=4`).
- [ ] T004 Extend [src/haex_hive/schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS` set with `workflow-registry.v1.schema.json`. Verify against the loader's kebab-case convention for `schema/data/*.schema.json`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shape all cross-story primitives (schemas, dataclasses, error types, small helpers). Every user story depends on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Schemas and their contract tests

- [ ] T005 [P] Vendor [contracts/workflow-registry.v1.schema.json](./contracts/workflow-registry.v1.schema.json) into [src/haex_hive/schema/data/workflow-registry.v1.schema.json](../../src/haex_hive/schema/data/workflow-registry.v1.schema.json). Verify byte-identical copy and that the schema loader (T004) registers it.
- [ ] T047 [P] Extend [src/haex_hive/schema/data/atom-manifest.v2.schema.json](../../src/haex_hive/schema/data/atom-manifest.v2.schema.json) with `contributes.speckit_workflow`, `contributes.speckit_extensions`, and `contributes.speckit_hooks`. Verify the shipped schema accepts the new manifest shape while preserving the existing fields and path constraints; keep T005's workflow-registry schema vendor task unchanged.
- [ ] T006 [P] Contract test for workflow-registry v1 in [tests/workflow/contract/test_workflow_registry_schema.py](../../tests/workflow/contract/test_workflow_registry_schema.py): load the schema; assert (a) bundled-only shape with `active_workflow: null` validates; (b) full shape with one atom-adopted workflow validates; (c) bundled entry with `atom_id` or `atom_revision` refuses; (d) atom entry without `atom_id` or `atom_revision` refuses; (e) invalid SemVer 2.0.0 `version` refuses; (f) unknown top-level fields refuse; (g) unknown per-workflow fields under `workflows.<id>` are accepted (forward compat).
- [ ] T007 [P] Contract test for atom-manifest v2 delta in [tests/workflow/contract/test_atom_manifest_speckit_workflow.py](../../tests/workflow/contract/test_atom_manifest_speckit_workflow.py): assert (a) `contributes.speckit_workflow` alone is a valid workflow-atom shape; (b) full triple `speckit_workflow` + `speckit_extensions` + `speckit_hooks` validates; (c) `speckit_workflow` value pointing at an absolute path refuses at load time; (d) `speckit_hooks` value naming a file (not a directory) refuses; (e) `speckit_extensions` without `speckit_workflow` refuses before staging; (f) `speckit_hooks` without `speckit_workflow` refuses before staging. Depends on T047.
- [ ] T008 [P] Contract test for extensions-fragment v1 in [tests/workflow/contract/test_extensions_fragment_shape.py](../../tests/workflow/contract/test_extensions_fragment_shape.py): validate the YAML fragment shape defined in [contracts/extensions-fragment.v1.md](./contracts/extensions-fragment.v1.md). Cover valid and invalid `required_extensions`, `optional_extensions`, and `hooks.<stage>[]` entries. Include the reviewer-clarified "duplicate `(stage, command)` within a single fragment" refusal test and a valid "same command in different fragments" case that must NOT refuse at the per-fragment level.

### Dataclasses and small helpers

- [ ] T009 [P] Implement `WorkflowAtomManifest` frozen dataclass in [src/haex_hive/workflow/registry.py](../../src/haex_hive/workflow/registry.py). `__post_init__` validates all path fields via `RepoRelativePath.validate` + containment against the atom root. Fields per [data-model.md §WorkflowAtomManifest](./data-model.md).
- [ ] T010 Implement `WorkflowRegistry` + `WorkflowEntry` frozen dataclasses in [src/haex_hive/workflow/registry.py](../../src/haex_hive/workflow/registry.py) with `from_json(raw: bytes)` (validates via `workflow-registry.v1.schema.json`) and `to_json_bytes()` (deterministic serialisation: sorted keys, 2-space indent, LF newlines). Depends on T005, T009; schedule after T009.
- [ ] T011 [P] Implement `WorkflowFragment` + `ExtensionRequirement` + `HookEntry` frozen dataclasses in [src/haex_hive/workflow/fragment.py](../../src/haex_hive/workflow/fragment.py). `ExtensionRequirement.__post_init__` parses `version_constraint` via `haex_hive.model.version_constraint.VersionConstraint`; on parse-error raises `InvalidConstraintError`. Depends on T009 (path validation helpers).
- [ ] T012 [P] Implement `ResolvedExtensionRequirement` + `ExtensionRequirementSource` frozen dataclasses in [src/haex_hive/workflow/constraint.py](../../src/haex_hive/workflow/constraint.py) as the return-type of the constraint-merge algorithm. No IO methods; construction only.
- [ ] T013 [P] Implement `WorkflowResolution` frozen dataclass in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py). Fields per [data-model.md §WorkflowResolution](./data-model.md).
- [ ] T014 Implement nine `HaexError` subclasses in [src/haex_hive/workflow/errors.py](../../src/haex_hive/workflow/errors.py) for the diagnostic-key slots reserved in [plan.md §Reserved Diagnostic Keys](./plan.md): `RequiredWorkflowExtensionMissingError`, `RequiredWorkflowExtensionIncompatibleError`, `InvalidConstraintError`, `ConflictingConstraintError`, `OptionalWorkflowExtensionConflictWarning` (not a raised error, a helper that emits stderr), `ConflictingExtensionMetadataError`, `WorkflowHookMappingInvalidError`, `WorkflowAtomExtensionIdCollisionError`, `WorkflowAtomResetToDefaultWarning` (stderr-only helper). Each raised class uses its diagnostic key + exit code from the plan's table.

### Extended shared model / helpers

- [ ] T015 Extend [src/haex_hive/model/consumer_manifest.py](../../src/haex_hive/model/consumer_manifest.py) `ConsumerManifest.from_json` to recognise atoms whose `contributes` map includes `speckit_workflow` and hydrate them as `WorkflowAtomManifest` per T009. Preserve backward-compat: atoms without `speckit_workflow` continue to hydrate as plain `AtomManifest`. Depends on T009.
- [ ] T016 Implement `constraint.merge(fragments: Iterable[WorkflowFragment]) -> tuple[ResolvedExtensionRequirement, ...]` in [src/haex_hive/workflow/constraint.py](../../src/haex_hive/workflow/constraint.py) per [research.md §R2](./research.md) and [contracts/extensions-fragment.v1.md §Constraint-merge algorithm](./contracts/extensions-fragment.v1.md). Order-independent canonical reduction. Empty-range refuses with `ConflictingConstraintError`. Depends on T011, T012, T014.
- [ ] T017 Implement `resolve_active_workflow(repo_root: Path) -> WorkflowResolution` in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py) per [research.md §R8](./research.md). Never raises: `fallback` variant absorbs registry-file corruption, schema-validation failure, and unresolvable `active_workflow`. Depends on T010, T013.

**Checkpoint**: Foundation ready. `haex install` continues to work unchanged for non-workflow atoms; workflow-atom recognition through `ConsumerManifest` and dataclass hydration are in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Adopt and activate a workflow atom (Priority: P1) 🎯 MVP

**Goal**: An operator adopts a workflow atom via `.haex-hive.json`, runs `haex install`, and `resolve_active_workflow` returns the atom's `workflow.yml` when `active_workflow` names its id.

**Independent Test**: On a fresh consumer checkout with a single `speckit-workflow` atom in `.haex-hive.json`, run `haex install --llm=file` + review + `haex install --accept-merged <candidate>`. Assert (a) `.specify/workflows/<atom-id>/workflow.yml` is byte-identical to the atom's contribution; (b) `.haex-hive/constitution.md` contains the `## Workflow-Contributed Rules` section with the atom's fragment under a `### From atom <id> (revision <sha>)` byline; (c) `workflow-registry.json` lists both bundled `speckit` and the atom-workflow; (d) `resolve_active_workflow` returns the atom-workflow when `active_workflow` is set to the atom's id.

### Unit tests for User Story 1

- [ ] T018 [P] [US1] Unit test `WorkflowAtomManifest` at [tests/workflow/unit/test_workflow_atom_manifest.py](../../tests/workflow/unit/test_workflow_atom_manifest.py): construction with all three optional fields; construction with only `workflow_path`; construction with an absolute `workflow_path` refuses; symlink escape refuses; frozen-immutability checks.
- [ ] T019 [P] [US1] Unit test `WorkflowRegistry` round-trip at [tests/workflow/unit/test_workflow_registry.py](../../tests/workflow/unit/test_workflow_registry.py): `from_json(to_json_bytes(x)) == x` for a bundled-only shape and a full mixed shape; validate that unknown top-level fields refuse; validate that unknown per-workflow fields under `workflows.<id>` are accepted and preserved in `unknown_extras`; perform a second install/upsert while the operator-selected active atom remains adopted and assert `active_workflow` is unchanged.
- [ ] T020 [P] [US1] Unit test `resolve_active_workflow` at [tests/workflow/unit/test_resolver.py](../../tests/workflow/unit/test_resolver.py): fallback when registry file missing; fallback when `active_workflow` is null or absent; fallback when `active_workflow` names an unresolvable id (with diagnostic in the result); resolution to atom-workflow when set; resolution to bundled when set to `"speckit"`.

### Implementation for User Story 1

- [ ] T021 [US1] Extend [src/haex_hive/constitution/assemble.py](../../src/haex_hive/constitution/assemble.py) to fold workflow-atom constitution fragments into the multi-source merge. Each fragment prepended with `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` under a single `## Workflow-Contributed Rules` section per [research.md §R4](./research.md). Section header appears exactly once; when no workflow-atom contributes, the section is omitted. Depends on T015 (ConsumerManifest workflow-atom recognition). Satisfies FR-004.
- [ ] T048 [US1] Implement pre-publication workflow-atom payload validation in [src/haex_hive/workflow/fragment.py](../../src/haex_hive/workflow/fragment.py) and add contract coverage in [tests/workflow/contract/test_workflow_payload_validation.py](../../tests/workflow/contract/test_workflow_payload_validation.py). Before staging, parse `workflow.yml` as YAML and validate its bundled-workflow shape; reject plaintext secrets and concealment instructions in every string field; validate `steps[].script` and `hooks[].script` for repo-relative containment below the declared `speckit_hooks` root and consumer atom-owned destination; require each referenced path to be a regular, non-symlink file included in the hooks publication. Keep T009's declared `contributes.*` path checks in place.
- [ ] T022 [US1] Implement `publish_workflow_atoms(atoms, dest_root, transaction)` in [src/haex_hive/workflow/registry.py](../../src/haex_hive/workflow/registry.py): run T048 before staging/copying; copy each atom's `workflow.yml` payload to `.specify/workflows/<atom-id>/workflow.yml`; copy its `hooks_dir` tree (if any) to `.specify/extensions/workflow-atoms/<atom-id>/`; read the consumer's existing `.specify/extensions.yml`, merge all `speckit_extensions` fragments with it using T016 and the contract's atom-first/local-last hook rules, and write the merged `.specify/extensions.yml` in the same transaction. Do not publish an atom fragment as a separate file. All destination paths validated for containment against consumer root. Publication participates in the same rename-swap generation as the constitution merge. Depends on T015, T016, T048. Satisfies FR-002, FR-003, and FR-005.
- [ ] T023 [US1] Implement `WorkflowRegistry.upsert(atoms, bundled_workflow)` in [src/haex_hive/workflow/registry.py](../../src/haex_hive/workflow/registry.py): rewrites the registry to reflect the current adopted-atom set plus the bundled entry, preserving the operator-set `active_workflow` field (unchanged unless the named atom is being removed in the same install, which is US3's concern). Depends on T010. Satisfies FR-006.
- [ ] T024 [US1] Wire `cli/install.py::run` to call `publish_workflow_atoms` (T022), fold workflow-atom constitution fragments (T021 already integrated in assemble), merge and publish `.specify/extensions.yml` (T022/T016), and rewrite `workflow-registry.json` via `WorkflowRegistry.upsert` (T023), all within the install transaction. Depends on T021, T022, T023. Satisfies FR-002, FR-003, FR-004, FR-005, FR-006.

### Integration test for User Story 1

- [ ] T025 [US1] Integration test at [tests/workflow/integration/test_adopt_workflow_atom.py](../../tests/workflow/integration/test_adopt_workflow_atom.py) using a fixture publisher repo declaring one `speckit-workflow` atom: run `haex install --llm=file` + `--accept-merged <candidate>` end-to-end; assert (a) workflow.yml published byte-for-byte; (b) hook scripts published under `.specify/extensions/workflow-atoms/<atom-id>/`; (c) `.specify/extensions.yml` contains the deterministic merge of the atom fragment with the consumer's pre-existing content and no standalone fragment file is published; (d) constitution fragment merged into `## Workflow-Contributed Rules` with the correct byline; (e) `workflow-registry.json` lists both workflows; (f) setting `active_workflow` in the registry and calling `resolve_active_workflow` returns the atom-workflow. Covers SC-001, SC-002, SC-003.

**Checkpoint**: User Story 1 is fully functional. Operators can adopt a workflow atom and select it as binding.

---

## Phase 4: User Story 2 - Required-extension validator refuses missing/incompatible extensions (Priority: P2)

**Goal**: `haex install` refuses BEFORE any file publication when a workflow atom's `required_extensions` names an extension that is absent or incompatible.

**Independent Test**: Adopt a workflow atom declaring `required_extensions: [{id: v-model-extension-pack, version_constraint: ">=0.7.2"}]` while ensuring `.specify/extensions/v-model-extension-pack/` does NOT exist. Run `haex install`. Assert exit code = `VALIDATION_REFUSE` (4), stderr contains `key=required-workflow-extension-missing`, and no files under `.specify/workflows/` or `.haex-hive/` were written.

### Unit tests for User Story 2

- [ ] T026 [P] [US2] Unit test `ExtensionRequirement` parsing at [tests/workflow/unit/test_extension_requirement.py](../../tests/workflow/unit/test_extension_requirement.py): valid `>=X.Y.Z`, `<=X.Y.Z`, `X.Y.Z`, `~=X.Y.Z` cases; unparseable constraint raises `InvalidConstraintError` with `key=invalid-constraint`; homepage optional; frozen-immutability.
- [ ] T027 [P] [US2] Unit test `constraint.merge` at [tests/workflow/unit/test_constraint_merge.py](../../tests/workflow/unit/test_constraint_merge.py): every case in the [contracts/extensions-fragment.v1.md](./contracts/extensions-fragment.v1.md) algorithm table. Order-independence check: `merge([A, B])` and `merge([B, A])` produce equal `ResolvedExtensionRequirement` tuples. Empty-range refusal with `ConflictingConstraintError`. Required-vs-optional interaction: required wins; compatible optional folds in; incompatible optional dropped with `OptionalWorkflowExtensionConflictWarning` on stderr.
- [ ] T028 [P] [US2] Unit test `WorkflowFragment` load-time refusals at [tests/workflow/unit/test_workflow_fragment.py](../../tests/workflow/unit/test_workflow_fragment.py): duplicate `(stage, command)` within one fragment raises `WorkflowHookMappingInvalidError`; same extension id required twice within one fragment raises `WorkflowAtomExtensionIdCollisionError`; unknown stage name refuses; malformed YAML refuses with `workflow-fragment-parse-failed`.

### Implementation for User Story 2

- [ ] T029 [US2] Implement `validate_required_extensions(resolved: Iterable[ResolvedExtensionRequirement], extensions_root: Path) -> None` in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py): raises `RequiredWorkflowExtensionMissingError` when `.specify/extensions/<id>/` is absent for a required id; raises `RequiredWorkflowExtensionIncompatibleError` when an installed version fails the constraint; retains compatible optional constraints in the resolved result; drops incompatible optional constraints with `OptionalWorkflowExtensionConflictWarning` on stderr; handles missing optional extensions separately as warning-only and does not refuse; emits no conflict warning for compatible optional constraints. Depends on T012, T014. Satisfies FR-007.
- [ ] T030 [US2] Implement `metadata_conflict_check(fragments)` in [src/haex_hive/workflow/fragment.py](../../src/haex_hive/workflow/fragment.py): compares non-constraint metadata (`homepage`) across fragments for the same extension id; raises `ConflictingExtensionMetadataError` on mismatch. Depends on T011, T014. Satisfies FR-005 (partial).
- [ ] T031 [US2] Wire `cli/install.py::run` to call `validate_required_extensions` (T029) and `metadata_conflict_check` (T030) BEFORE the constitution merge / staged writes. On any raised error, install refuses cleanly with zero files written under `.haex-hive.next/` or `.specify/`. Depends on T024, T029, T030. Satisfies FR-007.

### Integration test for User Story 2

- [ ] T032 [US2] Integration test at [tests/workflow/integration/test_required_extension_gate.py](../../tests/workflow/integration/test_required_extension_gate.py). Four subtests: (a) missing extension refuses with `key=required-workflow-extension-missing` and no files written; (b) incompatible version refuses with `key=required-workflow-extension-incompatible` and stderr names both installed and required versions; (c) optional missing extension proceeds with a warning, while compatible optional constraints are retained without a conflict warning; (d) two atoms declaring the same extension with compatible constraints merge to the canonical form and their differing `homepage` values for the same extension id refuse with `ConflictingExtensionMetadataError` plus `key=conflicting-extension-metadata`; assert the published `.specify/extensions.yml` contains the merged result. Covers SC-005.

---

## Phase 5: User Story 3 - Downgrade path via delete-orphans (Priority: P2)

**Goal**: Removing a workflow atom from `.haex-hive.json` and re-running `haex install` cleans up the atom's files and resets `active_workflow` to null if it named the removed atom.

**Independent Test**: Start from US1 endpoint (workflow atom adopted). Remove the atom entry from `.haex-hive.json`. Run `haex install`. Assert (a) `.specify/workflows/<atom-id>/` and `.specify/extensions/workflow-atoms/<atom-id>/` are absent; (b) atom's constitution fragment no longer in `.haex-hive/constitution.md`; (c) if `active_workflow` had named it, `workflow-registry.json.active_workflow` is now null and stderr shows `key=workflow-atom-reset-to-default`.

### Unit test for User Story 3

- [ ] T033 [P] [US3] Unit test `WorkflowRegistry.upsert` behaviour when the previously-active atom is being removed at [tests/workflow/unit/test_registry_upsert.py](../../tests/workflow/unit/test_registry_upsert.py): assert the entry is removed AND `active_workflow` resets to `null` AND `WorkflowAtomResetToDefaultWarning` is emitted. When the removed atom was NOT the active one, `active_workflow` is preserved verbatim.

### Implementation for User Story 3

- [ ] T034 [US3] Refine `WorkflowRegistry.upsert` (T023) to detect the "removed atom was the active one" case and reset `active_workflow` to null while emitting `WorkflowAtomResetToDefaultWarning` via `emit_refuse` (stderr-only, not an exit code). Depends on T023. Satisfies FR-009.
- [ ] T035 [US3] Ensure that under Spec 008's rename-swap primitive, whole-generation replacement covers `.specify/workflows/<atom-id>/` and `.specify/extensions/workflow-atoms/<atom-id>/` deletions automatically. Verify no explicit per-path delete step is needed. This task is a verification-only slot documenting the reliance on Spec 008 US4 semantics.

### Integration test for User Story 3

- [ ] T036 [US3] Integration test at [tests/workflow/integration/test_delete_orphans_workflow_atom.py](../../tests/workflow/integration/test_delete_orphans_workflow_atom.py): reuse fixture from T025. Three subtests: (a) remove atom while `active_workflow` names it, verify auto-reset + `key=workflow-atom-reset-to-default` on stderr; (b) remove atom while `active_workflow` names something else, verify preservation; (c) after a successful install assert `.specify/workflows/<atom-id>/` and `.specify/extensions/workflow-atoms/<atom-id>/` are both absent, and if rename-swap atomicity is tested, test each live tree separately without requiring cross-tree synchronization. Covers SC-004.

---

## Phase 6: User Story 4 - Coexistence of bundled + atom-adopted workflows (Priority: P3)

**Goal**: Multiple workflow atoms co-exist with the bundled workflow under `.specify/workflows/`. `active_workflow` field decides which is binding.

**Independent Test**: With bundled + two atom-adopted workflows present, verify `workflow-registry.json.workflows` lists all three; swapping `active_workflow` between them causes `resolve_active_workflow` to return each respectively; no exclusion or conflict.

### Unit test for User Story 4

- [ ] T037 [P] [US4] Unit test coexistence at [tests/workflow/unit/test_coexistence.py](../../tests/workflow/unit/test_coexistence.py): construct a registry with bundled + two atom entries; swap `active_workflow` through all three values (including null); verify `resolve_active_workflow` returns the correct source and path each time.

### Integration test for User Story 4

- [ ] T038 [US4] Integration test at [tests/workflow/integration/test_coexistence.py](../../tests/workflow/integration/test_coexistence.py) using a two-workflow-atom fixture: install both; assert `workflow-registry.json.workflows` has three entries (bundled + two atoms); iterate through valid `active_workflow` values and assert `resolve_active_workflow` returns the expected workflow each time. Covers SC-006.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Ensure spec-scoped changes leave the tree clean; no dead symbols; the operator quickstart works end-to-end; the full pytest suite passes with no regressions.

- [ ] T039 [P] Dead-symbol prune sweep: run `ruff check --select F401,F841 src tests` after all implementation tasks land; remove any transient imports the workflow subpackage or extended modules no longer need. Match the discipline of Spec 008 T055.
- [ ] T040 [P] Refresh public surface in [src/haex_hive/workflow/__init__.py](../../src/haex_hive/workflow/__init__.py): re-export `WorkflowAtomManifest`, `WorkflowRegistry`, `WorkflowFragment`, `WorkflowResolution`, `resolve_active_workflow`. Keep everything else module-private.
- [ ] T041 Run [specs/011-speckit-workflow-atom/quickstart.md](./quickstart.md) end-to-end on a fresh clone with `$HAEX_HIVE_STATE` pointing at a scratch dir: exercise steps 1-8 (adopt, first install with two-phase merge, verify publication, activate atom-workflow, refusal path, coexistence swap, downgrade, where-things-live). Record SC-001..SC-006 verification outcomes in the phase closing commit message.
- [ ] T042 Full pytest run (`pytest tests/workflow/` + `pytest tests/` for full-suite regression) after all implementation lands. Zero regressions; every new test added by Phases 3-6 passes.
- [ ] T043 [P] Update [.haex-hive/constitution.md](../../.haex-hive/constitution.md) via `haex install --llm=file` + `--accept-merged` once Spec 011 lands, to include a v1.4.1 PATCH constitution amendment that retires the "planned Spec 011" forward-reference in the Declared speckit workflow adherence bullet. This is a follow-up commit, not a Phase 7 task in the strict sense; task-slot retained for traceability.

### Deferred slots

- [ ] T044 [deferred] Runtime enforcement of workflow-adherence (pre-commit hook or GitHub Action that refuses task landings that skip the declared workflow's steps). Deferred to a Phase-7 constitution amendment per [plan.md §Complexity Tracking](./plan.md) and [spec.md §Assumptions](./spec.md). Not part of this spec's implementation.
- [ ] T045 [deferred] Automatic installation of speckit-community extensions when a workflow atom's `required_extensions` are absent. Delegated to specifyr's extension-install mechanism; out of scope per [spec.md §Assumptions](./spec.md).
- [ ] T046 [blocked on T037 (Spec 008)] `haex install --verify-only` integration: report the resolved workflow via `WorkflowResolution` in the verify-only output. Requires Spec 008 T037 (shared-read-lock + --verify-only) to land first. Task-slot retained for traceability.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. MVP boundary.
- **User Story 2 (Phase 4)**: Depends on Foundational AND US1 (T024 CLI wiring extends what US1 built). Can start in parallel with US1 only if editors coordinate on `cli/install.py`.
- **User Story 3 (Phase 5)**: Depends on Foundational AND US1 (T024). Can land after US1 with no US2 dependency.
- **User Story 4 (Phase 6)**: Depends on Foundational AND US1. Can land after US1.
- **Polish (Phase 7)**: Depends on all user stories being complete.

### Within Each User Story

- Tests first, then implementation, then integration test.
- Data-model + small helper tasks (T009-T014) complete before their story tasks consume them; T010 follows T009 because both modify `registry.py`, while T011-T013 may proceed in parallel where their dependencies are complete.

### Parallel Opportunities

- All contract tests (T006, T007, T008) run in parallel.
- T009 runs before T010; T011, T012, and T013 can run in parallel once their dependencies are complete.
- Unit tests within a story (T018-T020, T026-T028, T033, T037) run in parallel.
- Integration tests across stories can run in parallel once their story implementations land.

---

## Parallel Example: Phase 2 Foundational

```text
# Contract tests parallel:
Task: "Contract test workflow-registry v1 at tests/workflow/contract/test_workflow_registry_schema.py"  (T006)
Task: "Contract test atom-manifest v2 delta at tests/workflow/contract/test_atom_manifest_speckit_workflow.py"  (T007)
Task: "Contract test extensions-fragment v1 at tests/workflow/contract/test_extensions_fragment_shape.py"  (T008)

# Dataclass implementations:
Task: "WorkflowAtomManifest at src/haex_hive/workflow/registry.py"  (T009)
Task: "WorkflowRegistry+WorkflowEntry at src/haex_hive/workflow/registry.py"  (T010, after T009)
Task: "WorkflowFragment+ExtensionRequirement+HookEntry at src/haex_hive/workflow/fragment.py"  (T011)
Task: "ResolvedExtensionRequirement+ExtensionRequirementSource at src/haex_hive/workflow/constraint.py"  (T012)
Task: "WorkflowResolution at src/haex_hive/workflow/resolver.py"  (T013)

# Then T014 (errors) + T015 (ConsumerManifest extension) can proceed;
# Then T016 (constraint.merge) + T017 (resolve_active_workflow) finalise.
```

## Parallel Example: User Story 1

```text
# US1 unit tests parallel:
Task: "test_workflow_atom_manifest at tests/workflow/unit/test_workflow_atom_manifest.py"  (T018)
Task: "test_workflow_registry at tests/workflow/unit/test_workflow_registry.py"  (T019)
Task: "test_resolver at tests/workflow/unit/test_resolver.py"  (T020)

# Then US1 implementations sequential (share cli/install.py):
# T021 (assemble extension) → T048 (payload validation) → T022 (publish_workflow_atoms) → T023 (upsert)
# → T024 (CLI wiring integration) → T025 (integration test)
```

## Implementation Strategy

### MVP First (User Story 1 Only)

Land Phases 1-3. `haex install` publishes a single adopted workflow atom, merges its constitution fragment, records it in `workflow-registry.json`, and the operator can flip `active_workflow` manually to make it binding. That is the smallest viable Spec 011 delivery.

### Incremental Delivery

- Phase 4 (US2): required-extensions gate. Adds pre-publish refusal for missing/incompatible extensions.
- Phase 5 (US3): delete-orphans + `active_workflow` auto-reset. Enables clean revert.
- Phase 6 (US4): multiple-workflow-atom fixture + integration test. Confirms coexistence works, but the coexistence guarantee is a consequence of Phase 3 already (US4 mainly adds test coverage).
- Phase 7 (Polish): dead-symbol prune, quickstart end-to-end, full regression.

### Parallel Team Strategy

- Engineer A drives Phase 1-2 (setup + foundational + contract tests).
- Engineer B drives Phase 3 (US1) once Phase 2 hits its `Checkpoint`.
- Engineer C picks up Phases 4 + 5 in parallel with each other after US1's `cli/install.py` wiring (T024) lands.
- Phase 6 (US4) needs only extended fixtures, no new implementation; land near the end alongside Polish.

---

## Coverage Traceability

### Functional Requirements

| FR | Implementation task(s) | Test task(s) |
|---|---|---|
| FR-001 (workflow atom shape + path safety) | T009, T015, T047 | T007, T018 |
| FR-002 (publication location) | T022, T024 | T025 |
| FR-003 (hook scripts) | T022, T048 | T025 |
| FR-004 (constitution fragment merge) | T021 | T025 |
| FR-005 (extensions fragment merge) | T011, T016, T022, T024, T030 | T008, T028, T032 |
| FR-006 (workflow registry active_workflow) | T023, T024 | T019, T025 |
| FR-007 (required-extensions gate) | T029, T031 | T032 |
| FR-008 (reader resolution) | T017 | T020 |
| FR-009 (delete-orphans on removal) | T034, T035 | T036 |
| FR-010 (concealment guard on fragments) | T021 (reuses existing `validate_no_concealment_instructions`), T048 (workflow payload validation) | T025 asserts no publication when fragment carries concealment content, T048 |

### Success Criteria

| SC | Test task(s) |
|---|---|
| SC-001 (byte-for-byte workflow.yml publication) | T025 |
| SC-002 (constitution fragment merge) | T025 |
| SC-003 (`resolve_active_workflow` helper) | T020, T025 |
| SC-004 (delete-orphans) | T036 |
| SC-005 (required-extensions refusal) | T032 |
| SC-006 (coexistence via `workflow-registry.json.workflows`) | T038 |

### Diagnostic Keys

| Diagnostic key | Raising task | Test task |
|---|---|---|
| `required-workflow-extension-missing` | T029 | T032 (a) |
| `required-workflow-extension-incompatible` | T029 | T032 (b) |
| `invalid-constraint` | T011 (`ExtensionRequirement.__post_init__`) | T026 |
| `conflicting-constraint` | T016 (empty-range refusal) | T027 |
| `optional-workflow-extension-conflict` | T029 (warning-only, stderr for incompatible optional constraints) | T032 (c) |
| `conflicting-extension-metadata` | T030 | T032 (d) |
| `workflow-hook-mapping-invalid` | T011 (`WorkflowFragment` construction), T022 (publication-time) | T008, T028 |
| `workflow-atom-extension-id-collision` | T011 | T028 |
| `workflow-atom-reset-to-default` | T034 (warning-only, stderr) | T036 (a) |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps a task to its user story for traceability; Setup, Foundational, and Polish tasks carry no label.
- Every user story is independently completable and testable per its Independent Test section in [spec.md](./spec.md).
- Verify tests fail against the T001/T002 skeleton before implementing the story.
- Commit after each task or logical group; keep this file's checkboxes fresh, see [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).
- Stop at any checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts across concurrent tasks, cross-story dependencies that break independence.
