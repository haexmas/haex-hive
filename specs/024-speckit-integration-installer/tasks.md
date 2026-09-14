---

description: "Implementation tasks for declarative Spec Kit integration installation"
---

# Tasks: Declarative Spec Kit Integration Installer

**Input**: Design documents from `/specs/024-speckit-integration-installer/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

**Tests**: Included because the feature specification defines independent acceptance scenarios and the plan requires contract, unit, and integration coverage.

**Checkbox freshness**: Mark each task complete in this file immediately after its output is verified, before starting the next dependent task.

## Phase 1: Setup

**Purpose**: Establish the feature's source and test boundaries without adding dependencies.

- [X] T001 Verify the existing Python, pytest, ruff, mypy, and schema-test conventions in `pyproject.toml`, `src/`, and `tests/`; document any implementation constraints in `specs/024-speckit-integration-installer/plan.md`
- [X] T002 [P] Add the `src/spaex/integrations/` package boundary and package export conventions in `src/spaex/integrations/__init__.py`
- [X] T003 [P] Add deterministic fake-`specify` fixture coverage in `tests/integration/test_speckit_installation.py`

---

## Phase 2: Foundational

**Purpose**: Implement the validated data contracts and pure decision logic required by all user stories.

**Checkpoint**: Manifest, lock, declaration, selection, and fingerprint contracts are testable before subprocess orchestration begins.

- [X] T004 [P] [US1] Write molecule-manifest contract tests for valid `speckit` declarations, exact/lower-bound version constraints, integration options, and speckit-only molecules in `tests/contract/test_molecule_manifest_speckit.py`
- [X] T005 [P] [US1] Write molecule-manifest rejection tests for malformed constraints, invalid keys/options, global-install requests, executable paths, and conflicting hook declarations in `tests/contract/test_molecule_manifest_speckit.py`
- [X] T006 [P] [US2] Write install-lock contract tests for fingerprints, selected-key ordering, successful outcome values, malformed records, and failed-run non-publication in `tests/contract/test_install_lock_speckit.py`
- [X] T007 [P] [US1] Extend `src/spaex/schema/data/molecule-manifest.v4.schema.json` with the strict optional `speckit` declaration shape and validation limits from `contracts/molecule-manifest-speckit.v1.md`
- [X] T008 [P] [US2] Extend `src/spaex/schema/data/install-lock.v4.schema.json` with the optional per-molecule `speckit` record from `contracts/install-lock-speckit.v1.md`
- [X] T009 [US1] Add typed `SpeckitDeclaration` and integration-option parsing/validation to `src/spaex/model/molecule_manifest.py`, preserving existing manifest behavior for molecules without `speckit`
- [X] T010 [US2] Add the optional typed `speckit` lock contribution and validation/serialization support to `src/spaex/model/install_lock.py`
- [X] T011 [US1] Write pure selection, version-policy, canonicalization, fingerprint, no-op, and outcome tests in `tests/unit/test_speckit_integration.py`
- [X] T012 [US1] Implement pure Spec Kit declaration validation, selection precedence, version-policy matching, declaration fingerprinting, and outcome-state helpers in `src/spaex/integrations/speckit.py`

---

## Phase 3: User Story 1 - Select Spec Kit agents during installation (Priority: P1) 🎯 MVP

**Goal**: A molecule can declare official Spec Kit integrations and an interactive install can install only the agents selected by the operator.

**Independent Test**: A fake official CLI receives only the selected integration command, writes only its project-local marker, and the resulting lock contains the selected outcome.

### Tests for User Story 1

- [X] T013 [P] [US1] Add fake-CLI integration coverage for selected-agent installation and per-agent outcome reporting in `tests/integration/test_speckit_installation.py`
- [X] T014 [P] [US1] Add official-CLI argv, working-directory, option-forwarding, and no-shell invocation tests in `tests/unit/test_speckit_integration.py`

### Implementation for User Story 1

- [X] T015 [US1] Implement the subprocess adapter for `specify version`, `specify integration list`, and `specify integration install <key>` with argument arrays, repository `cwd`, visible output, and typed failures in `src/spaex/integrations/speckit.py`
- [X] T016 [US1] Add interactive selection handling and `--speckit-agents` parsing for `none`, `all`, and comma-separated keys in `src/spaex/cli/main.py`
- [X] T017 [US1] Integrate validated Spec Kit declaration collection, supported-key detection, interactive selection, and serial official CLI installation into `src/spaex/cli/install.py`
- [X] T018 [US1] Forward Spec Kit selection and opt-out values from `spaex add` into the internal install path in `src/spaex/cli/add.py`
- [X] T019 [US1] Publish selected Spec Kit outcomes in the staged install lock while preserving normal molecule publication and existing non-Spec-Kit contributions in `src/spaex/cli/install.py` and `src/spaex/model/install_lock.py`

**Checkpoint**: User Story 1 is independently functional for Claude Code and Codex CLI fixtures.

---

## Phase 4: User Story 2 - Reuse the same selection deterministically (Priority: P1)

**Goal**: Repeated installs reuse persisted selection and avoid unnecessary external CLI invocations; changed selections install only newly selected integrations.

**Independent Test**: Two installs with the same declaration and lock produce zero second-run install commands; adding a new agent produces only that agent's command.

### Tests for User Story 2

- [X] T020 [P] [US2] Add repeat-install no-op and no-prompt tests using the persisted lock fingerprint in `tests/integration/test_speckit_installation.py`
- [X] T021 [P] [US2] Add changed-selection delta tests proving unchanged integrations are preserved and only newly selected keys are invoked in `tests/integration/test_speckit_selection.py`
- [X] T022 [P] [US2] Add declaration-option/revision conflict tests for multiple adopted molecules in `tests/integration/test_speckit_selection.py`

### Implementation for User Story 2

- [X] T023 [US2] Implement lock-based selection reuse and fingerprint comparison for already-satisfied and newly selected states in `src/spaex/integrations/speckit.py`
- [X] T024 [US2] Add multi-molecule Spec Kit declaration conflict detection that refuses before external invocation in `src/spaex/cli/install.py`
- [X] T025 [US2] Preserve existing per-integration outcomes and update only affected keys when extending the install lock in `src/spaex/cli/install.py`

**Checkpoint**: User Story 2 is independently functional and idempotent for unchanged, changed, and conflicting declarations.

---

## Phase 5: User Story 3 - Use the official Spec Kit integration contract (Priority: P1)

**Goal**: spaex delegates layouts, command semantics, and conflict behavior to the installed official CLI for Claude Code and Codex CLI.

**Independent Test**: The fake CLI proves the exact official command contract and project-local destinations; no spaex code contains agent-specific skill-file copying.

### Tests for User Story 3

- [X] T026 [P] [US3] Add Claude Code and Codex conformance fixtures for project-local `.claude/skills/` and `.agents/skills/` results in `tests/integration/test_speckit_installation.py`
- [X] T027 [P] [US3] Add unsupported-integration and locally-modified-file conflict-boundary tests in `tests/integration/test_speckit_failure_boundary.py`

### Implementation for User Story 3

- [X] T028 [US3] Implement CLI version verification, supported integration discovery, and integration-specific option forwarding according to `contracts/molecule-manifest-speckit.v1.md` in `src/spaex/integrations/speckit.py`
- [X] T029 [US3] Ensure the install orchestration never writes agent-specific skill files directly and reports official CLI output and conflict failures in `src/spaex/cli/install.py`
- [X] T030 [US3] Add molecule-removal warning behavior without automatic Spec Kit uninstall in `src/spaex/cli/remove.py`

**Checkpoint**: User Story 3 is independently functional for the official Claude and Codex integration contracts.

---

## Phase 6: User Story 4 - Run safely in automation (Priority: P2)

**Goal**: Non-interactive callers receive deterministic selection, prerequisite, failure, and opt-out behavior without hanging or claiming false success.

**Independent Test**: A fake-CLI test suite covers explicit selection, persisted selection, missing selection, missing CLI, incompatible version, unsupported key, failed invocation, partial external side effects, and one-shot opt-out.

### Tests for User Story 4

- [X] T031 [P] [US4] Add non-interactive explicit-selection, persisted-selection, missing-selection, and `--no-speckit-integrations` tests in `tests/integration/test_speckit_selection.py`
- [X] T032 [P] [US4] Add missing CLI, incompatible version, unsupported integration, non-zero exit, cancellation, and partial-side-effect failure tests in `tests/integration/test_speckit_failure_boundary.py`
- [X] T033 [P] [US4] Add machine-readable diagnostic/result assertions for every documented Spec Kit failure category in `tests/unit/test_speckit_integration.py`

### Implementation for User Story 4

- [X] T034 [US4] Implement non-interactive refusal, explicit opt-out, cancellation, and typed machine-readable diagnostics from `contracts/speckit-cli-surface.md` in `src/spaex/integrations/speckit.py`
- [X] T035 [US4] Ensure failed external operations retain the previous spaex generation and never publish failed Spec Kit outcomes in `src/spaex/cli/install.py`
- [X] T036 [US4] Expose the documented install/add result shape and diagnostic codes through the CLI dispatch and output layer in `src/spaex/cli/main.py` and `src/spaex/cli/add.py`

**Checkpoint**: User Story 4 is independently safe for CI and other non-interactive callers.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the complete feature against the contracts and repository quality gates.

- [X] T037 [P] Update the user-facing installation and molecule documentation with the Spec Kit declaration example and external-side-effect warning in `docs/speckit-integrations.md`
- [X] T038 [P] Add or update the feature quickstart fixture so `specs/024-speckit-integration-installer/quickstart.md` remains runnable without network access via `tests/integration/test_speckit_installation.py`
- [X] T039 Run formatter, linter, type checker, contract tests, unit tests, and all Spec Kit integration tests; record unavailable checks and fixes in `specs/024-speckit-integration-installer/quickstart.md`
- [X] T040 Run the full repository test suite and validate the final implementation against `specs/024-speckit-integration-installer/spec.md`, `plan.md`, and all files under `contracts/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; verify conventions before creating code.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP implementation.
- **User Story 2 (Phase 4)**: Depends on User Story 1's lock publication path.
- **User Story 3 (Phase 5)**: Depends on User Story 1's subprocess adapter; can overlap with User Story 2 after the shared adapter is stable.
- **User Story 4 (Phase 6)**: Depends on User Story 1's CLI surface and User Story 2's persisted-selection path.
- **Polish (Phase 7)**: Depends on all required user stories.

### Parallel Opportunities

- T002 and T003 can run in parallel after T001.
- T004, T005, T006, T007, and T008 can run in parallel because they touch separate contract/schema files.
- T013 and T014 can run in parallel before the US1 implementation tasks.
- T020, T021, and T022 can run in parallel after the US1 checkpoint.
- T026 and T027 can run in parallel after the US1 adapter exists.
- T031, T032, and T033 can run in parallel after the US1/US2 CLI paths exist.
- T037 and T038 can run in parallel; T039 and T040 remain sequential validation tasks.

### Implementation Strategy

1. Complete Setup and Foundational validation first.
2. Deliver User Story 1 as the MVP: declaration, selection, official CLI delegation, and lock publication.
3. Add deterministic reuse and changed-selection handling.
4. Add Claude/Codex conformance and removal/conflict behavior.
5. Add automation safety and failure-boundary guarantees.
6. Run the full quality and contract validation before handoff.

## Notes

- Every task has a checkbox, sequential ID, required story label where applicable, and concrete file path.
- `[P]` marks only tasks that can safely proceed in parallel on distinct files or independent test cases.
- Implementation must repeat the required plain `graphify query` consultation before authoring each new named production artifact and evaluate all returned candidates.
- The runtime `uv` dependency provisions the pinned Spec Kit CLI; no copied Spec Kit `SKILL.md` content is planned.
