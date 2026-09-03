# Tasks: Speckit Workflow Atom (simplified)

**Input**: Design documents from `/specs/011-speckit-workflow-atom/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included. Every FR needs a testable implementation, every SC needs a test task, every contract needs schema-level coverage, and the reviewer's hardened concepts (cross-root recovery, local-source preservation, verification rollback) each need dedicated crash-injection tests.

**Checkbox freshness is load-bearing.** When a task is completed, tick its checkbox in the same commit as the task's output, or at the latest in the next commit, before starting the next task. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1, US2, US3, or US4. Setup, Foundational, and Polish tasks carry no story label.
- Include exact file paths.

## Path Conventions

Single-project Python CLI (Spec 007 baseline). Source lives under [src/haex_hive/](../../src/haex_hive/); tests under [tests/](../../tests/). Spec 011 adds a `workflow/` subpackage plus `tests/workflow/` subtree; extends `install/`, `constitution/`, `model/`, and `schema/` in place. See [plan.md §Project Structure](./plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create workflow subpackage skeleton at [src/haex_hive/workflow/__init__.py](../../src/haex_hive/workflow/__init__.py) with module docstring; add stub files `resolver.py`, `fragment.py`, `local_source.py`, `merge.py`, `constraint.py`, `publisher.py`, `errors.py`, each carrying only a module docstring.
- [ ] T002 Create workflow test tree directories: `tests/workflow/contract/`, `tests/workflow/integration/`, `tests/workflow/unit/`. Match the `tests/install/*` convention: omit `__init__.py` files to avoid pytest package-name collisions with the real `haex_hive.workflow` package.
- [ ] T003 Extend [src/haex_hive/util/exit_codes.py](../../src/haex_hive/util/exit_codes.py) diagnostic-key documentation: append comments naming the nine diagnostic keys reserved for Spec 011 (see [plan.md §Reserved Diagnostic Keys](./plan.md)). No new numeric slots; reuse `INPUT_REFUSE=2` and `VALIDATION_REFUSE=4`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Schemas + atom-manifest extension

- [ ] T004 [P] Extend [src/haex_hive/schema/data/atom-manifest.v2.schema.json](../../src/haex_hive/schema/data/atom-manifest.v2.schema.json) with the three new `contributes.*` fields (`speckit_workflow`, `speckit_extensions`, `speckit_hooks`) per [contracts/atom-manifest.v2.speckit-workflow.md](./contracts/atom-manifest.v2.speckit-workflow.md). Verify the extended schema accepts the new manifest shape while preserving all existing fields and path constraints.
- [ ] T005 [P] Add new schema `src/haex_hive/schema/data/haex-hive-generation.v1.schema.json` for the cross-root generation record written into `.specify.next/.haex-hive-generation.json`: required fields `generation_id`, `root`, `participating_roots[]`; `additionalProperties: false`. Register in [src/haex_hive/schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS`.

### Contract tests

- [ ] T006 [P] Contract test for atom-manifest v2 delta at [tests/workflow/contract/test_atom_manifest_speckit_workflow.py](../../tests/workflow/contract/test_atom_manifest_speckit_workflow.py): assert (a) minimal `speckit_workflow` only validates; (b) full triple validates; (c) absolute path in `speckit_workflow` refuses; (d) `speckit_hooks` naming a file refuses; (e) `speckit_extensions` without `speckit_workflow` refuses before staging; (f) `speckit_hooks` without `speckit_workflow` refuses before staging. Depends on T004.
- [ ] T007 [P] Contract test for extensions-fragment v1 shape at [tests/workflow/contract/test_extensions_fragment_shape.py](../../tests/workflow/contract/test_extensions_fragment_shape.py): valid + invalid `required_extensions`, `optional_extensions`, `hooks.<stage>[]` cases; duplicate `(stage, extension, command, script)` within one fragment refuses; same command across two different fragments (or one across fragment/local) does NOT refuse at load; unknown stage refuses.
- [ ] T008 [P] Contract test for extensions-local v1 shape at [tests/workflow/contract/test_extensions_local_shape.py](../../tests/workflow/contract/test_extensions_local_shape.py): absent file returns empty declarations; `installed[]` and `settings` pass-through validates; duplicate hook identity within one stage refuses; duplicate id in `required_extensions[]` refuses.
- [ ] T009 [P] Contract test for extensions-generated v1 shape at [tests/workflow/contract/test_extensions_generated_shape.py](../../tests/workflow/contract/test_extensions_generated_shape.py): top-of-file comment includes `generated by haex install: do not edit`; deterministic sort of requirement lists by id; hook-list ordering rule (atom entries in fragment order, local entries after, identity-matched local replaces in position); `origin` field present on every entry.
- [ ] T010 [P] Contract test for haex-hive-generation.v1 schema at [tests/workflow/contract/test_generation_record_schema.py](../../tests/workflow/contract/test_generation_record_schema.py): valid record for `.specify/` root validates; missing `participating_roots` refuses; unknown fields refuse; malformed `generation_id` (not matching `g_YYYYMMDDTHHMMSSZ_XXXX` pattern) refuses.

### Dataclasses

- [ ] T011 [P] Implement `WorkflowAtomManifest` frozen dataclass in [src/haex_hive/workflow/fragment.py](../../src/haex_hive/workflow/fragment.py). `__post_init__` validates every declared path via `RepoRelativePath.validate` + containment against atom root. Fields per [data-model.md §WorkflowAtomManifest](./data-model.md).
- [ ] T012 [P] Implement `ExtensionRequirement` + `HookEntry` frozen dataclasses in [src/haex_hive/workflow/fragment.py](../../src/haex_hive/workflow/fragment.py). `ExtensionRequirement.__post_init__` parses `version_constraint`; raises `InvalidConstraintError` on syntax failure.
- [ ] T013 [P] Implement `WorkflowFragment` frozen dataclass in [src/haex_hive/workflow/fragment.py](../../src/haex_hive/workflow/fragment.py) plus `load_workflow_fragment(atom_manifest, atom_root) -> WorkflowFragment` loader. Duplicate hook identity or duplicate extension id within one fragment refuses at load. Depends on T011, T012.
- [ ] T014 [P] Implement `LocalExtensionsSource` frozen dataclass in [src/haex_hive/workflow/local_source.py](../../src/haex_hive/workflow/local_source.py) with `load_local_source(consumer_root) -> LocalExtensionsSource`. Absent file returns an empty instance. Captures the raw `source_bytes` (bytes read from disk) for later cross-check per data-model.md §Cross-root publication and recovery contract. Depends on T012.
- [ ] T015 [P] Implement `ExtensionRequirementSource` + `MergedRequirement` frozen dataclasses in [src/haex_hive/workflow/constraint.py](../../src/haex_hive/workflow/constraint.py).
- [ ] T016 [P] Implement `GeneratedExtensionsYml` frozen dataclass in [src/haex_hive/workflow/merge.py](../../src/haex_hive/workflow/merge.py) with `to_yaml_bytes()` deterministic serialiser per [contracts/extensions-generated.v1.md](./contracts/extensions-generated.v1.md).
- [ ] T017 [P] Implement `InstalledExtensionMetadata` frozen dataclass in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py) with `load_installed_extension_metadata(extensions_root, extension_id) -> InstalledExtensionMetadata` (reads `extension.yml` as authoritative version; no `.registry` cross-check).
- [ ] T018 [P] Implement `WorkflowResolution` frozen dataclass in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py) per data-model.md.
- [ ] T019 Implement nine `HaexError` subclasses in [src/haex_hive/workflow/errors.py](../../src/haex_hive/workflow/errors.py) covering the diagnostic-key slots reserved in [plan.md §Reserved Diagnostic Keys](./plan.md): `RequiredWorkflowExtensionMissingError`, `RequiredWorkflowExtensionIncompatibleError`, `InvalidConstraintError`, `ConflictingConstraintError`, `OptionalWorkflowExtensionConflictWarning` (stderr-only helper), `ConflictingExtensionMetadataError`, `WorkflowHookMappingInvalidError`, `WorkflowAtomExtensionIdCollisionError`, `MultipleWorkflowAtomsRefusedError`. Each raised class carries its documented diagnostic key + exit code.

### Extended shared model + coordinator scaffolding

- [ ] T020 Extend [src/haex_hive/model/consumer_manifest.py](../../src/haex_hive/model/consumer_manifest.py) `ConsumerManifest.from_json` to (a) recognise `contributes.speckit_workflow` atoms and hydrate as `WorkflowAtomManifest`; (b) detect the multi-workflow-atom case and raise `MultipleWorkflowAtomsRefusedError` (per research.md §R3) BEFORE any fragment loader runs. Depends on T011, T019. Satisfies FR-006.
- [ ] T021 Implement `constraint.merge(fragment, local_source) -> tuple[MergedRequirement, ...]` in [src/haex_hive/workflow/constraint.py](../../src/haex_hive/workflow/constraint.py) per research.md §R4: order-independent canonical reduction on atom-vs-local pair; empty-range refuses with `ConflictingConstraintError`; required-vs-optional interaction folds compatible optional in, drops incompatible optional with `OptionalWorkflowExtensionConflictWarning`. Depends on T012, T015, T019.
- [ ] T022 Implement `resolve_active_workflow(repo_root: Path) -> WorkflowResolution` in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py) per research.md §R5: inspects `ConsumerManifest`, returns typed result with `source: atom|bundled`; propagates `MultipleWorkflowAtomsRefusedError` rather than falling back. Depends on T018, T020. Satisfies FR-008.
- [ ] T023 Implement `merge_extensions(fragment, local_source) -> GeneratedExtensionsYml` in [src/haex_hive/workflow/merge.py](../../src/haex_hive/workflow/merge.py) per FR-005: atom-first + local-last precedence, identity-replace via `(stage, extension, command, script)` tuple per research.md §R8, metadata-conflict refuses with `ConflictingExtensionMetadataError`, non-constraint-metadata sort deterministic. Depends on T013, T014, T016, T021, T019. Satisfies FR-005.

**Checkpoint**: Foundation ready. Non-workflow atoms continue to install unchanged; workflow-atom recognition + fragment loading + merge + resolver are in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Adopt a workflow atom and it becomes binding (Priority: P1) 🎯 MVP

**Goal**: Operator adopts a workflow atom via `.haex-hive.json`; `haex install` publishes it and the workflow is automatically binding.

**Independent Test**: On fresh consumer checkout with one `speckit-workflow` atom in `.haex-hive.json`, run `haex install --llm=file` + `--accept-merged`; assert workflow.yml + hooks + constitution fragment + merged `.specify/extensions.yml` all publish correctly; `resolve_active_workflow` returns the atom-workflow.

### Unit tests for User Story 1

- [ ] T024 [P] [US1] Unit test `WorkflowAtomManifest` at [tests/workflow/unit/test_workflow_atom_manifest.py](../../tests/workflow/unit/test_workflow_atom_manifest.py): all-three-optional construction; workflow-only construction; absolute path refuses; symlink escape refuses; frozen-immutability.
- [ ] T025 [P] [US1] Unit test `WorkflowFragment` load at [tests/workflow/unit/test_workflow_fragment.py](../../tests/workflow/unit/test_workflow_fragment.py): valid load; duplicate hook identity refuses; duplicate extension id refuses; unknown stage refuses.
- [ ] T026 [P] [US1] Unit test `resolve_active_workflow` at [tests/workflow/unit/test_resolver.py](../../tests/workflow/unit/test_resolver.py): atom-workflow when adopted; bundled fallback when no workflow atom; parse-error on `.haex-hive.json` propagates diagnostic; frozen-immutability of result.

### Implementation for User Story 1

- [ ] T027 [US1] Extend [src/haex_hive/constitution/assemble.py](../../src/haex_hive/constitution/assemble.py) to fold workflow-atom constitution fragment into the multi-source merge inside a single `## Workflow-Contributed Rules` section under a `### From atom <atom-id> (revision <short-sha>)` byline. When no workflow atom contributes, section omitted. Depends on T020, T022. Satisfies FR-004, FR-010 (reuses existing concealment guard).
- [ ] T028 [US1] Implement `publish_workflow_atom(atom, staged_specify_root, transaction)` in [src/haex_hive/workflow/publisher.py](../../src/haex_hive/workflow/publisher.py): copies workflow.yml to `.specify.next/workflows/<atom-id>/workflow.yml`; copies hooks tree to `.specify.next/extensions/workflow-atoms/<atom-id>/`; validates all destination paths for containment against consumer root; refuses with `key=workflow-atom-extension-id-collision` when reserved namespace is occupied by a community extension. Depends on T020. Satisfies FR-002, FR-003.
- [ ] T029 [US1] Implement pre-publication workflow.yml payload safety in [src/haex_hive/workflow/publisher.py](../../src/haex_hive/workflow/publisher.py) per research.md §R6: parse YAML; run `validate_no_plaintext_secrets`; run `validate_no_concealment_instructions`; validate `steps[].script` and `hooks[].script` for containment against declared hooks root. Depends on T028. Satisfies FR-001 payload half.
- [ ] T030 [US1] Wire `cli/install.py::run` to invoke the workflow pipeline: load workflow atom via T020, load fragment via T013, load local source via T014, run `merge_extensions` via T023, write merged output to `.specify.next/extensions.yml`, call `publish_workflow_atom` via T028, then let constitution/assemble.py's T027-extended merge run. Depends on T020, T023, T027, T028. Satisfies FR-005 wire-up.

### Integration test for User Story 1

- [ ] T031 [US1] Integration test at [tests/workflow/integration/test_adopt_workflow_atom.py](../../tests/workflow/integration/test_adopt_workflow_atom.py) using a fixture publisher with one `speckit-workflow` atom (with constitution fragment + extensions fragment + hooks): run `haex install --llm=file` + `--accept-merged <candidate>` end-to-end; assert (a) `.specify/workflows/<atom-id>/workflow.yml` byte-identical; (b) hook scripts under `.specify/extensions/workflow-atoms/<atom-id>/`; (c) `.specify/extensions.yml` regenerated with merged content and generated-header comment; (d) `.specify/extensions.local.yml` byte-identical to before (or absent as before); (e) `## Workflow-Contributed Rules` section under correct byline; (f) `resolve_active_workflow` returns `source=atom`. Covers SC-001, SC-002, SC-003.

**Checkpoint**: US1 fully functional. Operators can adopt a workflow atom and it binds automatically.

---

## Phase 4: User Story 2 - Required-extension validator refuses (Priority: P2)

**Goal**: `haex install` refuses BEFORE any file publication when required extension is missing or incompatible.

**Independent Test**: Adopt atom with `required_extensions[]` naming a missing extension; run `haex install`; assert exit non-zero, stderr contains diagnostic key, no files published.

### Unit tests for User Story 2

- [ ] T032 [P] [US2] Unit test `ExtensionRequirement` parsing + `InvalidConstraintError` at [tests/workflow/unit/test_extension_requirement.py](../../tests/workflow/unit/test_extension_requirement.py): valid `>=X.Y.Z`, `<=X.Y.Z`, `X.Y.Z`, `~=X.Y.Z`; unparseable refuses with `key=invalid-constraint`.
- [ ] T033 [P] [US2] Unit test `constraint.merge` atom-vs-local at [tests/workflow/unit/test_constraint_merge.py](../../tests/workflow/unit/test_constraint_merge.py): every case in [contracts/extensions-fragment.v1.md](./contracts/extensions-fragment.v1.md) algorithm table; empty-range refuses; required-vs-optional interaction produces expected `MergedRequirement`.
- [ ] T034 [P] [US2] Unit test `merge_extensions` at [tests/workflow/unit/test_merge.py](../../tests/workflow/unit/test_merge.py): identity-replace on hook conflict; atom-first + local-last precedence; metadata conflict raises `ConflictingExtensionMetadataError`; deterministic sort of requirement lists.
- [ ] T035 [P] [US2] Unit test `LocalExtensionsSource` immutability at [tests/workflow/unit/test_local_source.py](../../tests/workflow/unit/test_local_source.py): loading captures `source_bytes` verbatim; empty when file absent; equal instances compare equal.
- [ ] T036 [P] [US2] Unit test `InstalledExtensionMetadata` loading at [tests/workflow/unit/test_installed_metadata.py](../../tests/workflow/unit/test_installed_metadata.py): valid `extension.yml` loads; missing file raises `RequiredWorkflowExtensionMissingError`; `.registry` presence is IGNORED (documented invariant).

### Implementation for User Story 2

- [ ] T037 [US2] Implement `validate_required_extensions(merged: GeneratedExtensionsYml, extensions_root: Path) -> None` in [src/haex_hive/workflow/resolver.py](../../src/haex_hive/workflow/resolver.py): raises `RequiredWorkflowExtensionMissingError` when required id has no local `.specify/extensions/<id>/`; raises `RequiredWorkflowExtensionIncompatibleError` when `extension.yml.version` fails constraint; emits `OptionalWorkflowExtensionConflictWarning` on stderr for incompatible optional; retains compatible optional silently. Depends on T017, T019. Satisfies FR-007.
- [ ] T038 [US2] Wire `cli/install.py::run` to call `validate_required_extensions` (T037) AFTER `merge_extensions` (T023) but BEFORE `.specify.next/` staging. On any raised error, install refuses cleanly with zero files written under `.specify.next/`, `.haex-hive.next/`, `.specify/`, or `.haex-hive/`. Depends on T030, T037. Satisfies FR-007 wire-up.

### Integration test for User Story 2

- [ ] T039 [US2] Integration test at [tests/workflow/integration/test_required_extension_gate.py](../../tests/workflow/integration/test_required_extension_gate.py): (a) missing extension refuses with `key=required-workflow-extension-missing`; (b) incompatible version refuses with `key=required-workflow-extension-incompatible`; (c) optional missing extension proceeds with warning; (d) invalid version-constraint syntax in atom refuses with `key=invalid-constraint`; (e) atom + local same-id conflict on `homepage` refuses with `key=conflicting-extension-metadata`. Assert every refusal case leaves zero files under `.specify.next/`, `.haex-hive.next/`, `.specify/workflows/`, `.specify/extensions/workflow-atoms/`, and does NOT rewrite `.specify/extensions.yml` or `.haex-hive/constitution.md`. Covers SC-005.

---

## Phase 5: User Story 3 - Downgrade removes workflow atom's artifacts (Priority: P2)

**Goal**: Removing the workflow atom from `.haex-hive.json` cleans up all its published state.

**Independent Test**: Start from US1 endpoint; remove atom entry; re-run `haex install`; assert atom's files, hook scripts, constitution fragment, and extensions.yml entries all absent; local source byte-identical.

### Unit tests for User Story 3

- [ ] T040 [P] [US3] Unit test workflow-atom removal path in `merge_extensions` at [tests/workflow/unit/test_merge_downgrade.py](../../tests/workflow/unit/test_merge_downgrade.py): given a `LocalExtensionsSource` only (no `WorkflowFragment`), the resulting `GeneratedExtensionsYml` contains only local declarations; no ghost entries survive.

### Implementation for User Story 3

- [ ] T041 [US3] Extend `publish_workflow_atom` (T028) to compute the delete-orphans set: enumerate the currently-adopted workflow atom's owned paths; on downgrade (no adopted workflow atom), the staged `.specify.next/workflows/` and `.specify.next/extensions/workflow-atoms/` are empty which triggers the whole-generation replacement to erase the previous atom's paths under Spec 008 rename-swap semantics. Depends on T028. Satisfies FR-009.

### Integration test for User Story 3

- [ ] T042 [US3] Integration test at [tests/workflow/integration/test_delete_orphans_workflow_atom.py](../../tests/workflow/integration/test_delete_orphans_workflow_atom.py): start from adopted state; remove atom from `.haex-hive.json`; re-run `haex install`. Assert (a) `.specify/workflows/<atom-id>/` absent; (b) `.specify/extensions/workflow-atoms/<atom-id>/` absent; (c) `## Workflow-Contributed Rules` section absent from `.haex-hive/constitution.md`; (d) generated `.specify/extensions.yml` reduces to local declarations only; (e) `.specify/extensions.local.yml` byte-identical to before adoption; (f) `resolve_active_workflow` returns `source=bundled`. Covers SC-004.

---

## Phase 6: User Story 4 - Refuse multiple workflow-atom adoptions (Priority: P2)

**Goal**: `.haex-hive.json` naming two `speckit-workflow` atoms refuses before any publication.

**Independent Test**: Author consumer with two workflow atoms; run `haex install`; assert exit non-zero + `key=multiple-workflow-atoms-refused` on stderr; no files under staged or live roots.

### Unit test for User Story 4

- [ ] T043 [P] [US4] Unit test `ConsumerManifest.from_json` multi-workflow-atom detection at [tests/workflow/unit/test_multi_workflow_detection.py](../../tests/workflow/unit/test_multi_workflow_detection.py): one workflow atom validates; zero workflow atoms validates; two workflow atoms raise `MultipleWorkflowAtomsRefusedError` with stderr naming all offending ids.

### Integration test for User Story 4

- [ ] T044 [US4] Integration test at [tests/workflow/integration/test_multi_workflow_refused.py](../../tests/workflow/integration/test_multi_workflow_refused.py) using a fixture publisher with two workflow atoms adopted in one `.haex-hive.json`: run `haex install`; assert exit code = `INPUT_REFUSE` (2); stderr contains `key=multiple-workflow-atoms-refused` and names both atom ids and sources; assert zero files under `.specify.next/`, `.haex-hive.next/`, `.specify/workflows/`, `.specify/extensions/workflow-atoms/`, and neither `.specify/extensions.yml` nor `.haex-hive/constitution.md` were touched. Covers SC-006.

---

## Phase 7: Cross-Root Publication Recovery (reviewer-hardened)

The reviewer-hardened cross-root recovery contract (data-model.md §Cross-root publication and recovery contract) is orthogonal to any single user story but MUST land alongside the US1 wiring or the install is unsafe against crashes.

### Cross-root coordinator implementation

- [ ] T045 [US1] Implement `CrossRootGenerationCoordinator` in [src/haex_hive/workflow/publisher.py](../../src/haex_hive/workflow/publisher.py): materialises `.specify.next/` and `.haex-hive.next/` in sibling directories on the same filesystem; writes `.haex-hive-generation.json` record into `.specify.next/` naming `generation_id`, `root`, and `participating_roots=[".haex-hive/", ".specify/"]`; validates the record against `haex-hive-generation.v1.schema.json` (T005) before any live-root change. Depends on T005, T028. Satisfies plan.md §Reserved Diagnostic Keys wire-up.
- [ ] T046 [US1] Extend the coordinator (T045) with local-source re-read gate: immediately before the first swap, re-read `.specify/extensions.local.yml` from live and compare bytes with `LocalExtensionsSource.source_bytes` captured at load time (T014); if bytes differ or file presence changed, refuse without publishing either root and emit a clear diagnostic. Depends on T014, T045. Satisfies plan.md local-source preservation invariant.
- [ ] T047 [US1] Extend the coordinator (T045) with two-phase commit order per data-model.md §Cross-root publication and recovery contract: (a) atomically replace or delete `.specify/` managed files in deterministic order excluding `.specify/extensions.local.yml`, saving pre-images to `.specify.prev/`; fsync each changed file plus the `.specify/` directory; (b) commit `.haex-hive/` via Spec 008's `publish_generation` with a `post_write_verify` callback (T048) and `visibility.json` naming both participating roots. Depends on T045, T046. Satisfies plan.md cross-root contract.
- [ ] T048 [US1] Implement `post_write_verify` callback for the cross-root commit in [src/haex_hive/workflow/publisher.py](../../src/haex_hive/workflow/publisher.py): after `.haex-hive/` swap runs but before `publish_generation` removes `.haex-hive.prev/`, verify (a) both live-root generation records exist; (b) `visibility.json.generation_id` matches `.haex-hive/install.lock.visibility_marker.generation_id` matches `.specify/.haex-hive-generation.json.generation_id`; (c) `participating_roots` lists match byte-identically. On verification failure, restore all changed `.specify/` managed paths from `.specify.prev/` and raise so `publish_generation` restores `.haex-hive/` while its previous root is still available. Depends on T045, T047. Satisfies plan.md verification rollback contract.
- [ ] T049 [US1] Implement recovery under `install/inflight.py` extension in [src/haex_hive/install/inflight.py](../../src/haex_hive/install/inflight.py): under the same exclusive lock as `haex install`, run before any input read on retry. Read and validate `.specify.next/`, `.specify.prev/`, `.haex-hive.next/`, `.haex-hive.prev/` siblings and their generation records. Well-formed and attributably-stale siblings are deleted; malformed or unattributable records refuse recovery and preserve the sibling. After sibling classification, compare live generation records + marker: if only `.specify/` changed, restore from `.specify.prev/`; if `.haex-hive/` also swapped, let Spec 008's mechanism restore from `.haex-hive.prev/`. Fsync every parent directory. Depends on T005. Satisfies plan.md cross-root recovery.
- [ ] T050 [US1] Extend reader helper `resolve_active_workflow` (T022) to enforce the visibility boundary per data-model.md: after loading `.haex-hive/visibility.json`, require its `generation_id` and `participating_roots` to match `.haex-hive/install.lock` AND `.specify/.haex-hive-generation.json`; any mismatch (including the interval between `.specify/` swap and `.haex-hive/` marker swap) rejects the view as unavailable and returns `source=bundled` with a diagnostic. Depends on T022, T005.

### Cross-root recovery + verification-rollback tests

- [ ] T051 [P] [US1] Unit test cross-root generation record round-trip at [tests/workflow/unit/test_cross_root_record.py](../../tests/workflow/unit/test_cross_root_record.py): construct record, serialise, deserialise, verify against schema; malformed records refuse.
- [ ] T052 [US1] Integration test (crash-injection matrix) at [tests/workflow/integration/test_cross_root_recovery.py](../../tests/workflow/integration/test_cross_root_recovery.py): parametrise a crash injection at each of five boundaries per data-model.md §Cross-root publication and recovery contract: (a) after staging siblings; (b) after first `.specify/` managed-path replacement but before `.haex-hive/` swap; (c) after `.haex-hive/` swap but before `post_write_verify`; (d) after `post_write_verify` succeeds; (e) during stale-sibling cleanup. Each case runs the install in a child, kills it at the boundary via `HAEX_HIVE_CRASH_AFTER` seam, then reruns install; asserts convergence to a valid generation and that the live tree matches one of {complete-previous, complete-new}, never mixed.
- [ ] T053 [US1] Integration test verification-rollback at [tests/workflow/integration/test_verification_rollback.py](../../tests/workflow/integration/test_verification_rollback.py): inject a fault where `post_write_verify` deterministically raises AFTER the `.specify/` managed paths are replaced. Assert `.specify/` restored byte-for-byte from `.specify.prev/`, `.haex-hive/` restored by Spec 008's mechanism, both `.next/` and `.prev/` siblings cleaned per recovery contract, and the final tree matches the pre-install state exactly (including `.specify/extensions.local.yml` untouched).
- [ ] T054 [US1] Integration test local-source preservation invariant at [tests/workflow/integration/test_local_source_preserved.py](../../tests/workflow/integration/test_local_source_preserved.py): six scenarios asserting `.specify/extensions.local.yml` byte-identity: (a) successful install with atom adopted; (b) install with atom removed (downgrade); (c) install refused at required-extension gate; (d) install refused at multi-workflow-atoms; (e) install crashed after `.specify/` replacement and recovered; (f) install with `.specify/extensions.local.yml` absent (empty declarations, install succeeds, file remains absent).
- [ ] T055 [US1] Integration test mixed-generation reader-rejection at [tests/workflow/integration/test_mixed_generation_reader.py](../../tests/workflow/integration/test_mixed_generation_reader.py): craft a filesystem state where `.specify/.haex-hive-generation.json` names generation-A but `.haex-hive/visibility.json` names generation-B (simulated by kicking off an install and racing a reader between the two swaps). Assert the reader helper (T050) returns `source=bundled` with a diagnostic rather than exposing a mixed view.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T056 [P] Dead-symbol prune sweep: run `ruff check --select F401,F841 src tests` after all implementation lands; remove any transient imports the workflow subpackage or extended modules no longer need. Match Spec 008 T055 discipline.
- [ ] T057 [P] Refresh public surface in [src/haex_hive/workflow/__init__.py](../../src/haex_hive/workflow/__init__.py): re-export `WorkflowAtomManifest`, `WorkflowFragment`, `LocalExtensionsSource`, `GeneratedExtensionsYml`, `WorkflowResolution`, `resolve_active_workflow`; keep everything else module-private.
- [ ] T058 Run [specs/011-speckit-workflow-atom/quickstart.md](./quickstart.md) end-to-end on a fresh clone with `$HAEX_HIVE_STATE` pointing at a scratch dir: exercise all 9 steps (adopt, first install with local source, verify publication, verify binding, refusal path missing extension, refusal path two workflows, downgrade, where-things-live). Record SC-001..SC-006 verification outcomes in the phase closing commit message.
- [ ] T059 Full pytest run (`pytest tests/workflow/` + full-suite regression) after all implementation lands. Zero regressions; every new test added by Phases 3-7 passes.
- [ ] T060 Constitution v1.4.1 follow-up: after Spec 011 lands, propose a PATCH-level amendment to [.specify/memory/constitution.md](../../.specify/memory/constitution.md) that retires the "planned Spec 011" forward-reference in the § Development Workflow declared-speckit-workflow-adherence bullet. Task-slot retained for traceability; the amendment is a separate PR.

### Deferred slots

- [ ] T061 [deferred] Runtime enforcement of declared workflow adherence (pre-commit hook or CI gate refusing task landings that skip declared workflow steps). Deferred to a Phase-7 constitution amendment per plan.md §Complexity Tracking. Not part of Spec 011.
- [ ] T062 [deferred] Automatic installation of speckit-community extensions when `required_extensions[]` are absent locally. Delegated to specifyr; out of scope per spec.md §Assumptions.
- [ ] T063 [blocked on T037 (Spec 008)] `haex install --verify-only` integration: report the resolved `WorkflowResolution` in verify-only output. Requires Spec 008 T037 (`--verify-only` + shared-read lock) to land first. Task-slot retained.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. Can start immediately.
- **Foundational (Phase 2)**: depends on Setup. BLOCKS all user stories.
- **US1 MVP (Phase 3)**: depends on Foundational. Independent of US2-US4 test paths.
- **US2 (Phase 4)**: depends on Foundational + US1's `cli/install.py::run` extension (T030). Can start in parallel with US3/US4 only if editors coordinate on `install.py`.
- **US3 (Phase 5)**: depends on Foundational + US1. Downgrade is a re-invocation of the same pipeline with fewer atoms.
- **US4 (Phase 6)**: depends on Foundational (T020 is the multi-workflow-atom detection).
- **Cross-Root Recovery (Phase 7)**: US1 pipeline must be in place first; T045-T050 land during or shortly after Phase 3. Recovery tests T051-T055 depend on the full Phase 7 implementation.
- **Polish (Phase 8)**: depends on all user stories + Phase 7 complete.

### Parallel Opportunities

- All contract tests (T006-T010) run in parallel.
- All dataclass implementations (T011-T018) run in parallel (each in its own file).
- Unit tests within a story run in parallel (T024-T026, T032-T036, T040, T043).
- Integration tests across stories run in parallel once implementations land.

---

## Parallel Example: Phase 2 Foundational

```text
# Contract tests parallel:
Task: "Contract test atom-manifest v2 delta at tests/workflow/contract/test_atom_manifest_speckit_workflow.py"  (T006)
Task: "Contract test extensions-fragment shape at tests/workflow/contract/test_extensions_fragment_shape.py"  (T007)
Task: "Contract test extensions-local shape at tests/workflow/contract/test_extensions_local_shape.py"  (T008)
Task: "Contract test extensions-generated shape at tests/workflow/contract/test_extensions_generated_shape.py"  (T009)
Task: "Contract test generation-record schema at tests/workflow/contract/test_generation_record_schema.py"  (T010)

# Dataclass implementations parallel:
Task: "WorkflowAtomManifest at src/haex_hive/workflow/fragment.py"  (T011)
Task: "ExtensionRequirement + HookEntry at src/haex_hive/workflow/fragment.py"  (T012)
Task: "WorkflowFragment loader at src/haex_hive/workflow/fragment.py"  (T013, after T011+T012)
Task: "LocalExtensionsSource at src/haex_hive/workflow/local_source.py"  (T014, after T012)
Task: "ExtensionRequirementSource + MergedRequirement at src/haex_hive/workflow/constraint.py"  (T015)
Task: "GeneratedExtensionsYml at src/haex_hive/workflow/merge.py"  (T016)
Task: "InstalledExtensionMetadata at src/haex_hive/workflow/resolver.py"  (T017)
Task: "WorkflowResolution at src/haex_hive/workflow/resolver.py"  (T018)

# Then T019 (errors), T020 (ConsumerManifest extension), T021-T023 (helpers) finalise.
```

## Implementation Strategy

### MVP First (User Story 1 Only)

Land Phases 1-3 + Phase 7 cross-root recovery. Without Phase 7 the install is unsafe against crashes. The MVP delivers: adopt one workflow atom, install succeeds atomically across two roots, workflow is binding via reader helper.

### Incremental Delivery

- Phase 4 (US2): required-extensions gate. Adds refusal for missing/incompatible extensions.
- Phase 5 (US3): downgrade. Enables clean revert.
- Phase 6 (US4): multi-workflow-atom refusal. Guardrail.
- Phase 8 (Polish): dead-symbol prune, quickstart end-to-end, full regression, constitution v1.4.1 follow-up slot.

---

## Coverage Traceability

### Functional Requirements

| FR | Implementation task(s) | Test task(s) |
|---|---|---|
| FR-001 (workflow atom shape + path safety) | T011, T020, T029 | T006, T024 |
| FR-002 (publication location) | T028, T030, T045, T047 | T031 |
| FR-003 (hook scripts + reserved namespace + collisions) | T028, T041 | T031, T042 |
| FR-004 (constitution fragment merge) | T027 | T031 |
| FR-005 (extensions fragment merge + local ownership) | T013, T014, T016, T021, T023, T030 | T007, T008, T009, T025, T033, T034, T035, T039, T054 |
| FR-006 (multi-workflow-atom refusal) | T020, T019 | T043, T044 |
| FR-007 (required-extensions gate) | T017, T037, T038 | T036, T039 |
| FR-008 (reader resolution) | T018, T022, T050 | T026, T055 |
| FR-009 (delete-orphans on removal) | T041 | T040, T042 |
| FR-010 (concealment guard) | T027 (reuses `validate_no_concealment_instructions`), T029 | T031 asserts no publication with concealment content |

### Success Criteria

| SC | Test task(s) |
|---|---|
| SC-001 (byte-for-byte workflow.yml publication) | T031 |
| SC-002 (constitution fragment merge under byline) | T031 |
| SC-003 (`resolve_active_workflow` helper) | T026, T031, T042 |
| SC-004 (delete-orphans) | T042, T054 (b) |
| SC-005 (required-extensions refusal) | T039 |
| SC-006 (multi-workflow-atom refusal) | T044 |

### Diagnostic Keys

| Key | Raising task | Test task |
|---|---|---|
| `required-workflow-extension-missing` | T037 | T036, T039 (a) |
| `required-workflow-extension-incompatible` | T037 | T039 (b) |
| `invalid-constraint` | T012 | T032, T039 (d) |
| `conflicting-constraint` | T021 | T033 |
| `optional-workflow-extension-conflict` | T037 (warning) | T039 (c) |
| `conflicting-extension-metadata` | T023 | T034, T039 (e) |
| `workflow-hook-mapping-invalid` | T013, T028 | T007, T025 |
| `workflow-atom-extension-id-collision` | T013, T028 | T007, T008, T025, T031 |
| `multiple-workflow-atoms-refused` | T020 | T043, T044 |

### Reviewer-hardened concepts

| Concept | Implementation task(s) | Test task(s) |
|---|---|---|
| Cross-root publication recovery | T045, T047, T049, T050 | T051, T052, T055 |
| Local-source preservation invariant | T014 (captures source_bytes), T023 (never writes to local), T028 (excludes local from staging), T046 (re-read gate) | T035, T054 |
| Verification rollback | T048 (`post_write_verify` callback), T047 (`.specify.prev/` staging), T049 (recovery) | T053 |

### Contracts

| Contract | Schema task | Contract test task |
|---|---|---|
| atom-manifest.v2.speckit-workflow.md | T004 | T006 |
| extensions-fragment.v1.md | (narrative) | T007 |
| extensions-local.v1.md | (narrative) | T008 |
| extensions-generated.v1.md | (narrative) | T009 |
| haex-hive-generation.v1.schema.json | T005 | T010 |

### Dataclasses

Every dataclass in data-model.md has a construction task + a unit-test task:

| Dataclass | Construction task | Unit-test task |
|---|---|---|
| WorkflowAtomManifest | T011 | T024 |
| WorkflowFragment | T013 | T025 |
| ExtensionRequirement | T012 | T032 |
| HookEntry | T012 | T025 (via WorkflowFragment), T034 (via merge) |
| LocalExtensionsSource | T014 | T035 |
| GeneratedExtensionsYml | T016 | T034 |
| MergedRequirement | T015, T021 | T033 |
| ExtensionRequirementSource | T015 | T033 (via MergedRequirement.sources) |
| InstalledExtensionMetadata | T017 | T036 |
| WorkflowResolution | T018 | T026 |

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks.
- `[Story]` label maps a task to its user story for traceability; Setup, Foundational, Cross-Root Recovery, and Polish tasks carry no label except the Cross-Root Recovery tasks which are all `[US1]` because they land alongside US1 wiring.
- Every user story is independently completable and testable per its Independent Test section in [spec.md](./spec.md).
- Verify tests fail against the T001/T002 skeleton before implementing the story.
- Commit after each task or logical group; keep this file's checkboxes fresh (see [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md)).
- Stop at any checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts across concurrent tasks, cross-story dependencies that break independence.
