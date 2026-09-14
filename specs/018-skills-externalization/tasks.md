---

description: "Task list for structured external skill references and uvx hook delegation"
---

# Tasks: External Skill References

**Input**: Design documents from `specs/018-skills-externalization/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Required by the feature specification and the repository's TDD
workflow. Contract and integration tests are written before implementation.

**Scope**: This task list covers the clarified Phase-A delta: structured
`external_skills` references, the `skillsmd`/`uvx` default adapter contract,
and direct access to the pinned molecule manifest from an install hook. It
does not implement a skills registry, copy skill files through spaex, or build
the later UI phases.

## Phase 1: Setup and artifact alignment

**Purpose**: Make the design artifacts agree before code changes begin.

- [ ] T001 Update `specs/018-skills-externalization/plan.md` with the
  structured reference shape, `skillsmd` as the default external adapter, and
  `SPAEX_MOLECULE_MANIFEST` as an existing-manifest path contract.
- [ ] T002 [P] Synchronize the data model and manifest contract in
  `specs/018-skills-externalization/data-model.md` and
  `specs/018-skills-externalization/contracts/molecule-manifest-external-skills.v1.md`.

## Phase 2: Foundational contract work

**Purpose**: Define the schema and runtime boundary shared by all user stories.

- [ ] T003 [P] Add structured-reference contract tests in
  `tests/contract/test_molecule_manifest_external_skills.py` for repository,
  full revision SHA, repository-relative path, uniqueness, invalid values, the
  hook requirement, and retired `skill`/`skills` categories.
- [ ] T004 [P] Add parser tests in `tests/unit/test_external_skills_parser.py`
  for immutable ordered `ExternalSkillReference` values and backwards
  compatibility when the field is absent.
- [ ] T005 Extend
  `src/spaex/schema/data/molecule-manifest.v4.schema.json` with the structured
  `external_skills` object and validation rules while retaining the existing
  hook condition and open atom categories.
- [ ] T006 Extend `src/spaex/model/molecule_manifest.py` with a frozen
  `ExternalSkillReference` value object and immutable tuple parsing.

**Checkpoint**: The manifest contract and parser expose structured references,
but no installer side effect is implemented yet.

## Phase 3: User Story 1 - Declare an external skill without copying it (P1)

**Goal**: Preserve repository, revision, and path provenance without treating a
skill as a spaex-delivered atom.

**Independent Test**: Parse and validate a structured reference; confirm it is
available in `MoleculeManifest.external_skills` and absent from atom paths.

### Tests for User Story 1

- [ ] T007 [US1] Extend `tests/unit/test_external_skills_parser.py` with
  declaration-order and frozen-value assertions for multiple references.
- [ ] T008 [US1] Add a regression fixture in
  `tests/integration/test_external_skill_materialization.py` proving that
  `external_skills` does not enter the materialized file list or
  `install.lock` paths.

### Implementation for User Story 1

- [ ] T009 [US1] Update related resolver typing so structured references remain
  metadata only and are not added to materialized paths or install-lock paths.
- [ ] T010 [US1] Update `specs/018-skills-externalization/quickstart.md` and
  `README.md` with a co-located `haexmas/atoms` source example using a full
  revision SHA and repository-relative skill path.

**Checkpoint**: User Story 1 is independently testable without Node, registry
access, or skill materialization by spaex.

## Phase 4: User Story 2 - Reject retired skill atom categories (P1)

**Goal**: Prevent publishers from silently continuing to deliver skills through
the old `atoms.skill` or `atoms.skills` categories.

**Independent Test**: Schema validation rejects both retired categories and
continues accepting unrelated open category names.

### Tests and implementation for User Story 2

- [ ] T011 [P] [US2] Keep the retired-category and open-category cases in
  `tests/contract/test_molecule_manifest_external_skills.py` explicit and
  independently readable.
- [ ] T012 [US2] Run the existing CLI, resolver, and orphan-deletion fixtures
  that previously used `atoms.skills`, preserving their generic-category
  intent in `tests/cli/`, `tests/unit/`, and `tests/integration/`.

**Checkpoint**: User Story 2 is independently testable through contract and
compatibility tests.

## Phase 5: User Story 3 - Delegate installation through the hook boundary (P2)

**Goal**: Let a molecule-owned hook read the pinned manifest and invoke the
Python/uv-based `skillsmd` adapter while spaex remains the orchestrator.

**Independent Test**: A fixture hook reads the manifest path supplied by spaex,
invokes a fake skillsmd-compatible command, and receives the normal hook
failure semantics.

### Tests for User Story 3

- [ ] T014 [P] [US3] Add a hook-runner unit test in
  `tests/unit/test_hook_runner.py` asserting inherited environment, consumer
  repository cwd, and `SPAEX_MOLECULE_MANIFEST` pointing to the existing
  extracted `manifest.json`.
- [ ] T015 [US3] Add the end-to-end fixture in
  `tests/integration/test_external_skill_hook.py`; the hook reads the pinned
  manifest and uses a local fake installer, so tests do not contact PyPI or a
  registry.

### Implementation for User Story 3

- [ ] T016 [US3] Update `src/spaex/install/hook_runner.py` to pass the path of
  the already extracted molecule manifest as `SPAEX_MOLECULE_MANIFEST` while
  preserving inherited environment, cwd, stdio, and existing containment and
  failure behavior.
- [ ] T017 [US3] Add the `uvx skillsmd` invocation example and pinned adapter
  guidance to `docs/install-hooks.md` and
  `docs/adr/0021-external-skills-delegated-to-hooks.md`.
- [ ] T018 [US3] Clarify in `specs/018-skills-externalization/research.md` and
  `specs/018-skills-externalization/spec.md` that `agentskills.io` defines the
  format, `skillsmd` provides the default Python adapter, and the installed
  skill content remains outside spaex's lockfile.

**Checkpoint**: User Story 3 is independently testable with a local fixture;
the real `skillsmd` command remains a publisher-owned hook choice.

## Phase 6: Polish and validation

**Purpose**: Validate the clarified design and leave the task state accurate.

- [ ] T019 [P] Update `specs/018-skills-externalization/checklists/requirements.md`
  and `specs/018-skills-externalization/quickstart.md` with the final
  structured-reference and manifest-path acceptance evidence.
- [ ] T020 Run focused contract, parser, hook-runner, and integration tests;
  then run the full pytest suite, Ruff, mypy, and `git diff --check`. Record
  the exact evidence in this file before marking the tasks complete.
- [ ] T021 Review the final diff against `.spaex/constitution.md` and
  `.specify/memory/constitution.md`, confirm no new runtime registry
  dependency was introduced, and update `specs/018-skills-externalization/tasks.md`
  checkboxes in the same commit as each completed task.

## Dependencies and execution order

- Phase 1 precedes Phase 2 because schema and parser work must use the
  clarified artifact contract.
- Phase 2 blocks all user-story implementation.
- User Story 1 and User Story 2 can proceed in parallel after Phase 2.
- User Story 3 depends on the structured manifest model from User Story 1 but
  does not depend on User Story 2's category migration fixtures.
- Phase 6 follows all desired user-story work.

## Parallel opportunities

- T002, T003, and T004 can be prepared in parallel after T001.
- T007 and T011 can be prepared in parallel after the foundational tests.
- T014 and T015 can be written in parallel before T016.
- T019 can proceed in parallel with the final implementation review.

## Implementation strategy

1. Land the clarified design and task breakdown for review.
2. Implement the manifest contract and parser first.
3. Implement the hook environment contract and local integration fixture.
4. Run the complete validation gates and update task checkboxes eagerly.

The MVP is User Story 1 plus User Story 3: structured references can be
declared and delegated through a local hook without spaex materializing skill
content. User Story 2 remains a required compatibility guard for the release.
