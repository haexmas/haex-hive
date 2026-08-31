---
description: "Task list for feature implementation"
---

# Tasks: graphify-first-authoring atom/molecule

**Input**: Design documents from `/specs/atoms/graphify-first-authoring/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included — `plan.md`'s own Project Structure already commits to a `tests/atoms/graphify_first_authoring/` tree, so test tasks are generated alongside implementation tasks (not strict red-green TDD ceremony, just tests as a first-class deliverable matching the rest of this repo's convention).

**Checkbox freshness is load-bearing.** When a task is completed, tick its checkbox in the same commit as the task's output — or at the latest in the next commit, before starting the next task. See [ADR 0004](../../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: Tasks are grouped by user story (spec.md's US1–US4) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task's output)
- **[Story]**: Which user story this task belongs to (US1–US4)

## Path Conventions

Per plan.md's Structure Decision — not the generic `src/`/`tests/` application template. This feature's primary deliverable is a content/config package under `.specify/atoms/graphify-first-authoring/`, plus small edits to two existing root files (`manifest.json`, `.haex-hive.json`) and this repo's own `.gitignore`. Tests live under this repo's existing `tests/` tree.

---

## Phase 1: Setup

**Purpose**: Create the atom package skeleton and the test package skeleton that every later phase writes into.

- [X] T001 Create the atom package skeleton: `.specify/atoms/graphify-first-authoring/` with a `hooks/` subdirectory (empty save for a `.gitkeep`, filled in by later phases)
- [X] T002 Create the test package skeleton: `tests/atoms/graphify_first_authoring/__init__.py` and `tests/atoms/graphify_first_authoring/conftest.py`, where `conftest.py` inserts `.specify/atoms/graphify-first-authoring/` and its `hooks/` subdirectory onto `sys.path` so the atom's scripts (`install.py`, `_refresh.py`, `_snapshot.py`, `_tracked_branches.py`) are importable as plain modules from tests without packaging them into `haex_hive`

**Checkpoint**: directories exist; nothing yet to test.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one piece of logic shared by two later stories (US2's hook and US4's installer both need to know if the current branch is tracked). US1 needs none of this — it is pure contributed prose and may proceed as soon as Setup is done, in parallel with this phase if desired.

**⚠️ CRITICAL**: US2, US3, US4 cannot begin until this phase is complete. US1 is unaffected.

- [X] T003 Implement tracked-branch detection in `.specify/atoms/graphify-first-authoring/hooks/_tracked_branches.py`: auto-detect the default branch via `git symbolic-ref refs/remotes/origin/HEAD`, merge with `.haex-hive.json`'s optional `tracked_branches[]` array, expose a single `is_tracked(branch: str) -> bool` (research.md D4)
- [X] T004 Unit tests for tracked-branch detection in `tests/atoms/graphify_first_authoring/test_tracked_branches.py`: default-branch-only case, `tracked_branches[]` merge case, non-tracked branch returns `False`, missing `.haex-hive.json` handled gracefully

**Checkpoint**: `_tracked_branches.is_tracked()` is available and tested — US2 and US4 can now proceed.

---

## Phase 3: User Story 1 - Operator adopts the rule and agents stop silently duplicating code (Priority: P1) 🎯 MVP

**Goal**: Contribute a constitution principle that, once assembled into an adopting repo's `.haex-hive/constitution.md`, changes agent behavior — consult the graph before authoring, prefer extending an existing candidate, refuse-then-propose, honor the escape hatch, bootstrap/refresh when the graph is absent/stale.

**Independent Test**: Merge this atom's `constitution.md` into a test repo's `.haex-hive/constitution.md` (manually, or via `haex constitution assemble`). With a knowledge graph containing one relevant existing artifact, ask an agent to author a function duplicating it. Verify the agent names the candidate, states the delta, and proposes extending it — no code from Phase 2 is required for this to hold.

- [X] T005 [US1] Write the atom manifest in `.specify/atoms/graphify-first-authoring/manifest.json` declaring `contributes.constitution: "constitution.md"`, conforming to `specs/007-unified-manifest-v2/contracts/atom-manifest.v2.schema.json`
- [X] T006 [US1] Write the contributed constitution text in `.specify/atoms/graphify-first-authoring/constitution.md` covering: consult-before-author (FR-002), prefer-extend-over-duplicate including unexported/incomplete candidates (FR-003), refuse-then-propose with warn-and-proceed on consult failure and **ask-when-uncertain on borderline similarity or scope-creep risk** (FR-004), single-session escape hatch responsive to any natural-language operator request to skip (FR-005), bootstrap-when-absent/refresh-when-stale holding independent of hooks (FR-010), plain `graphify` CLI invocations rather than any one harness's slash-command syntax (FR-016). Additionally include (adapted from the Claude Code `prevent-redundancy` skill, kept harness-agnostic): (a) **Refactor Proposal Format** — 4-point checklist (candidate location as `file:line`; proposed helper signature; estimated lines saved; ONE concrete call-site rewritten as proof-of-concept before touching others); (b) **Red Flags self-detection** — new function name close to an existing one (`formatDate` vs `formatDateString`), third date/retry/validation utility in the codebase, 10-line block copied "just to adapt slightly", the thought "similar but different enough" (usually isn't), starting `function helper(…)` without checking; (c) **Test-fixture nuance** — duplicated arrange/assert/setup blocks are often intentional signal (don't touch), but helper functions in tests remain fully under this rule; (d) **Optional interpreting-output thresholds** — ≥6 identical lines with same logic → extract; <5 lines that are structural (setup, error-wrapping) → often OK, don't over-extract; hits inside test files → usually leave alone unless they are helpers per (c)
- [X] T007 [P] [US1] Validate `.specify/atoms/graphify-first-authoring/manifest.json` against `specs/007-unified-manifest-v2/contracts/atom-manifest.v2.schema.json` using the repo's existing `jsonschema` dependency, in `tests/atoms/graphify_first_authoring/test_manifest_schema.py`
- [ ] T008 [US1] Manually verify via [quickstart.md](quickstart.md) steps 3–5 (adopt in `.haex-hive.json`, `haex constitution assemble`, `haex constitution show`) that an agent follows the contributed authoring behavior — this is an agent-behavior check, not a unit test. T024/T025 verify assembly and source attribution only; they do not satisfy this task.

**Checkpoint**: User Story 1 is independently complete — the rule exists and is adoptable, with no dependency on US2/US3/US4.

---

## Phase 4: User Story 2 - Graph stays current automatically on tracked branches (Priority: P2)

**Goal**: Every commit landing on a tracked branch refreshes `graphify-out/` incrementally, without blocking the commit if the refresh itself fails.

**Independent Test**: Commit a change on the tracked branch through plain `git commit` (no agent involved). Verify `graphify-out/` reflects the new commit afterward.

- [X] T009 [P] [US2] Implement refresh logic in `.specify/atoms/graphify-first-authoring/hooks/_refresh.py`: invoke `graphify <repo-root> --update`; `graphify` itself writes `graphify-out/.meta.json`'s `indexed_at_sha` during indexing/refresh; on failure, warn to stderr and return normally rather than raising (contracts/git-hooks.md, FR-006)
- [X] T010 [US2] Implement the `post-commit` hook entrypoint in `.specify/atoms/graphify-first-authoring/hooks/post-commit`: check `_tracked_branches.is_tracked()` (no-op if false), call `_refresh.py`, always exit 0 regardless of outcome (depends on T003, T009)
- [X] T011 [P] [US2] Unit tests for refresh logic in `tests/atoms/graphify_first_authoring/test_refresh.py`: the simulated graphify process writes the freshness marker as graphify would, and the real refresh path invokes that process successfully; simulated `graphify` failure warns without raising (depends on T009)
- [X] T012 [US2] Integration test in `tests/atoms/graphify_first_authoring/test_post_commit_hook.py`: real `git commit` on a tracked branch triggers the installed hook and the graphify stub writes `graphify-out/.meta.json`'s `indexed_at_sha` through the real `_refresh.py` path, matching the new `HEAD` (depends on T010)

**Checkpoint**: User Stories 1 AND 2 both work independently.

---

## Phase 5: User Story 3 - Feature branches and worktrees see a correct fork-point view (Priority: P2)

**Goal**: A newly created worktree gets the parent branch's `graphify-out/` copied in at creation time, representing the fork point; never overwritten if already present; discarded with the branch.

**Independent Test**: On a repo with an existing tracked-branch graph, create a new worktree off it. Verify the new worktree's `graphify-out/` is populated immediately, matching the parent's graph.

- [X] T013 [P] [US3] Implement snapshot logic in `.specify/atoms/graphify-first-authoring/hooks/_snapshot.py`: locate the parent worktree via `git worktree list --porcelain`, copy a complete parent `graphify-out/` containing `graph.json` recursively if no complete graph exists locally, replace an incomplete destination directory, and no-op for an absent/incomplete parent graph or complete destination (contracts/git-hooks.md, FR-008)
- [X] T014 [US3] Implement the `post-checkout` hook entrypoint in `.specify/atoms/graphify-first-authoring/hooks/post-checkout`: check the third argument is `1` (branch checkout), call `_snapshot.py`, always exit 0 regardless of outcome (depends on T013)
- [X] T015 [P] [US3] Unit tests for snapshot logic in `tests/atoms/graphify_first_authoring/test_snapshot.py`: copies when absent locally, no-op when already present, no-op when parent has none (depends on T013)
- [X] T016 [US3] Integration test in `tests/atoms/graphify_first_authoring/test_post_checkout_hook.py`: real `git worktree add` from a repo with an existing `graphify-out/` produces a populated copy in the new worktree (depends on T014)

**Checkpoint**: User Stories 1, 2, AND 3 all work independently.

---

## Phase 6: User Story 4 - Adoption is a single command (Priority: P3)

**Goal**: One installer command verifies the `graphify` CLI, offers to register it with the operator's harness, installs both hooks with a platform-correct shebang, and adds `graphify-out/` to `.gitignore` — refusing cleanly (no partial changes) on any unmet precondition.

**Independent Test**: Run the installer in a fresh clone with `graphify` on PATH but no hooks installed. Verify hooks appear with a working shebang, `.gitignore` is updated, and the harness-registration step prompts rather than runs silently.

- [X] T017 [US4] Implement shebang resolution in `.specify/atoms/graphify-first-authoring/install.py`: resolve `shutil.which("python3") or shutil.which("python")`, refuse with a clear diagnostic if neither is found (research.md D1, FR-015)
- [X] T018 [US4] Implement installer preconditions in `install.py`, in this order: tracked-branch check via `_tracked_branches.is_tracked()` (FR-013), offer a default-Yes `pip install graphifyy` prompt when `graphify` is absent (FR-011), then hook-collision check for both target hook paths (FR-014) — declining or failing package installation refuses with no partial changes (depends on T003, T017)
- [X] T019 [US4] Implement installer actions in `install.py`: write both hooks with the resolved shebang, add a `graphify-out/` line to `.gitignore` if absent (FR-017), prompt before invoking `graphify install` only when the explicit local registration marker is absent, record successful registration in local git config, and print manual follow-up when declined (FR-012) (depends on T018)
- [X] T020 [P] [US4] Unit tests for the installer in `tests/atoms/graphify_first_authoring/test_install.py`: each precondition's refusal path leaves no partial changes, a successful run writes both hooks plus the `.gitignore` line, the default-Yes package prompt/refusal is covered, and the `graphify install` prompt is gated by the explicit registration marker, including graph-cache-present/unmarked and marker-present cases (depends on T019)

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Wire the atom into haex-hive's own repo as its first self-adopting consumer, and validate the whole pipeline end-to-end.

- [X] T021 [P] Write `.specify/atoms/graphify-first-authoring/README.md` (operator adoption docs, mirroring [quickstart.md](quickstart.md))
- [X] T022 Add the new atom entry to the repo-root `manifest.json` (data-model.md §RootManifestEntry) — depends on T005. **This lands as Commit 1 of the two-commit self-adoption convention**: Spec 007's `haex-hive.v2.schema.json` requires a full 40-char SHA in `atoms[]`'s `revision` field and has no in-tree self-reference form, so the pin can only reference a commit that already exists — T023 supplies that pin in Commit 2 once T022's SHA is known
- [X] T023 Add the new `atoms[]` entry to the repo-root `.haex-hive.json` for haex-hive's own self-adoption (data-model.md §ConsumerManifestEntry) — depends on T022. **This is Commit 2 of the two-commit self-adoption convention**: its `revision` field pins the exact SHA of T022's Commit 1, which is already in git history at this point (pinned to `4425c76097576fcdf93cefb407bf16d4c13dc781`)
- [X] T024 Run `haex constitution assemble` and review the merged `.haex-hive/constitution.md` (this exercises the multi-source LLM-merge path, since haex-hive now has two constitution-contributing atoms) — depends on T023. **Verified in this session** against a materialized publisher clone (`HAEX_HIVE_STATE=<scratchpad>` + self-clone at the expected repo digest), first with `--llm file` to produce the pending merge JSON (both sources correctly listed with their pinned revisions), then with `--accept-merged <merged.md>` to publish the merged constitution
- [X] T025 Run `haex constitution show` and verify the "Assembled from" preface names both source atoms — depends on T024. **Preface printed**: `- com.github.haexmas.haex-hive.constitution @ cc5fa94` and `- com.github.haexmas.haex-hive.graphify-first-authoring @ 4425c76`
- [ ] T026 [P] Run the full [quickstart.md](quickstart.md) walkthrough end-to-end on a scratch clone — deferred: end-to-end walkthrough is meaningful only after the atom's commits reach the public `haex-hive` repository so a fresh clone can pin the same SHA. Its constituent behaviors are already covered by T004 (tracked-branch detection), T011/T012 (post-commit refresh, real git), T015/T016 (post-checkout snapshot, real git+worktree), T020 (installer preconditions and outputs), and T024/T025 (multi-source assemble + show against a materialized publisher clone)
- [X] T027 [P] Run `ruff` and `mypy` (per the repo's existing `pyproject.toml` tool config) over all new atom scripts and tests
- [X] T028 [P] Append a `graphify-out/` line to the repo-root `.gitignore` so haex-hive's own self-adoption does not surface the artifact directory in subsequent working-tree operations — this is the direct enforcement of FR-009 for this repo (rather than routing through the installer's `.gitignore` write, which targets *other* consumers)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — starts immediately
- **Foundational (Phase 2)**: depends on Setup — blocks US2, US3, US4 only (not US1)
- **User Story 1 (Phase 3)**: depends on Setup only — may proceed in parallel with Foundational
- **User Stories 2–4 (Phases 4–6)**: each depends on Foundational; independent of each other and of US1
- **Polish (Phase 7)**: depends on US1 (needs T005's manifest) and, for T023–T025, effectively on all of US1–US4 being adoptable — this is the point where the pieces are wired together and validated as a whole

### Within Each User Story

- US1: manifest (T005) and constitution text (T006) before schema validation (T007) and manual verification (T008)
- US2: `_refresh.py` (T009) before the hook entrypoint (T010); unit tests (T011) can run alongside T010; integration test (T012) after T010
- US3: `_snapshot.py` (T013) before the hook entrypoint (T014); unit tests (T015) can run alongside T014; integration test (T016) after T014
- US4: T017 → T018 → T019 are sequential (same file, `install.py`); unit tests (T020) after T019

### Parallel Opportunities

- T007 (US1 schema test) can run alongside T008 (manual verification)
- T009 (US2 refresh logic) and T013 (US3 snapshot logic) touch different files and share only the already-complete Foundational phase — can be worked in parallel by different people
- T011 alongside T010; T015 alongside T014 (unit tests don't need the hook entrypoint, only the logic module underneath it)
- T020 (US4 tests) can run alongside US2/US3 work once Foundational is done
- T021, T026, T027 in Polish are independent of each other

---

## Parallel Example: User Story 2 and User Story 3 together

```bash
# Once Phase 2 (Foundational) is complete, these can run concurrently:
Task: "Implement refresh logic in .specify/atoms/graphify-first-authoring/hooks/_refresh.py"
Task: "Implement snapshot logic in .specify/atoms/graphify-first-authoring/hooks/_snapshot.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 3: User Story 1 (does not need Phase 2)
3. **STOP and VALIDATE**: manually verify per T008 that the contributed text changes agent behavior in a test repo
4. This alone delivers the atom's entire reason for existing — everything else is automation and convenience on top

### Incremental Delivery

1. Setup → User Story 1 → validate (MVP)
2. Foundational → User Story 2 → validate independently
3. User Story 3 → validate independently (can run in parallel with Story 2's implementation, after Foundational)
4. User Story 4 → validate independently
5. Polish: wire haex-hive's own self-adoption, run quickstart end-to-end, lint/typecheck

---

## Notes

- [P] tasks touch different files and don't depend on another incomplete task's output
- US1 has zero code — it is pure contributed prose; its "tests" are a schema check plus a manual behavioral verification, not unit tests of application logic
- Neither hook (`post-commit`, `post-checkout`) may ever cause the underlying git operation to fail — this is verified explicitly in T011/T012 and T015/T016, not left implicit
- Commit after each task or logical group; tick the checkbox in the same commit per ADR 0004
