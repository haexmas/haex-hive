---
description: "Tasks for Phase 0 — Pilot Harness in haex-hive Itself"
---

# Tasks: Phase 0 — Pilot Harness in haex-hive Itself

**Input**: Design documents from `specs/001-phase-0-pilot-harness/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: this feature has no automated tests. Its "tests" are the manual
fresh-session validation runs defined in `quickstart.md` and enumerated as
tasks under User Stories 1–3 below. The plan explicitly defers automated
harness evaluation to a later phase (per the design doc).

**Organization**: tasks are grouped by user story so that each story can be
validated independently. Setup and Foundational tasks reflect harness
artifacts that must exist before any user story can be exercised.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]`, `[US2]`, `[US3]`, mapping to the user stories in `spec.md`
- File paths in each task are repo-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: repository scaffolding, spec-kit toolchain, feature-branch
plumbing. Everything in this phase is already committed on branch
`001-phase-0-pilot-harness` as of the plan commit — tasks are listed for
traceability and to allow a rebuild-from-scratch to follow the same order.

- [x] T001 Initialize `haex-hive` repository with `git init` at `/home/haex/Projekte/haex-hive/`
- [x] T002 Commit design doc at `docs/plans/2026-08-26-haex-hive-design.md`
- [x] T003 Run `specify init . --ai claude --force` to scaffold spec-kit under `.specify/` and install skills into `.claude/skills/`
- [x] T004 Create feature branch `001-phase-0-pilot-harness` and run `.specify/scripts/bash/setup-plan.sh --json`

**Checkpoint**: repository is spec-kit-initialised and on the feature branch.

---

## Phase 2: Foundational (Blocking Prerequisites for All User Stories)

**Purpose**: the harness artifacts a fresh agent session needs to find at the
repo root and under `.specify/`. Without these, no user story can pass —
they are the object under test. Tasks in this phase are already committed on
the branch as of the plan commit; listed for traceability.

⚠️ **CRITICAL**: No user story validation may begin until this phase is
complete.

- [x] T005 Write `haex-hive` constitution v1.0.0 at `.specify/memory/constitution.md` — seven NON-NEGOTIABLE principles, scope, workflow, governance
- [x] T006 Author `specs/001-phase-0-pilot-harness/spec.md` with three user stories and eight functional requirements
- [x] T007 Author `specs/001-phase-0-pilot-harness/plan.md` including a Constitution Check gate against all seven principles
- [x] T008 [P] Author `specs/001-phase-0-pilot-harness/research.md` resolving the three plan-time unknowns (second CLI, adapter filename, symlink availability)
- [x] T009 [P] Author `specs/001-phase-0-pilot-harness/contracts/system-yaml.schema.md` defining the `.specify/system.yaml` v1.0 contract
- [x] T010 [P] Author `specs/001-phase-0-pilot-harness/quickstart.md` as the human-runnable four-section validation checklist
- [x] T011 [P] Create `.specify/system.yaml` at repo root with `system.id: haex-hive` and empty `external_sources.allowed: []`
- [x] T012 [P] Create `AGENTS.md` at repo root as a symlink to `.specify/memory/constitution.md`
- [x] T013 Update the `<!-- SPECKIT START -->…<!-- SPECKIT END -->` block in `CLAUDE.md` to point at the constitution, active plan, active spec, allowlist file, and design doc
- [x] T014 Update `.specify/feature.json` to `{"feature_directory": "specs/001-phase-0-pilot-harness"}`

**Checkpoint**: all harness artifacts committed on the feature branch;
`git status` clean; fresh-session validation may now begin.

---

## Phase 3: User Story 1 — Fresh session reconstructs full context (Priority: P1) 🎯 MVP

**Goal**: prove that a fresh session in each of Claude Code and Codex can
reconstruct the seven constitutional principles and the current phase from
repository state alone.

**Independent Test**: quickstart.md §B (three tests: 1.1 Claude, 1.2 Codex,
1.3 refusal on constitutional violation). PASS criterion: ≥6/7 principles
named AND Phase 0 identified in Tests 1.1 and 1.2, AND agent refuses in
Test 1.3 citing Principle I by identifier or clear paraphrase.

### Validation runs for User Story 1

- [ ] T015 [US1] Start the timer at the top of `quickstart.md` §A, complete §A setup checks, and record the start time in §E — this is prerequisite to every following US1/US2/US3 task
- [ ] T016 [US1] Run Test 1.1 in a fresh Claude Code session at repo root, following `quickstart.md` §B verbatim; record answer and pass/fail
- [ ] T017 [US1] Run Test 1.2 in a fresh Codex session at repo root, following `quickstart.md` §B verbatim; record answer and pass/fail; if Codex does not read `AGENTS.md`, note as a research finding against `research.md` Decision 2
- [ ] T018 [US1] Run Test 1.3 (refusal on constitutional violation) in either fresh session; record answer and pass/fail
- [ ] T019 [US1] Run Test 1.4 (session started in a subdirectory) per `quickstart.md` §B; record answer and pass/fail — this covers the subdirectory edge case from `spec.md` §Edge Cases
- [ ] T020 [US1] Persist Test 1.1–1.4 results in `specs/001-phase-0-pilot-harness/.validation-runs/<YYYY-MM-DD>.md`; include exact prompt used, exact answer verbatim, pass/fail per test, and whether the design doc was consulted at any point

**Checkpoint**: quickstart.md §B fully green for at least one Claude Code
session and one Codex session. If a test fails, do NOT proceed — either fix
the harness (usually a wording gap in the constitution or the CLAUDE.md
pointer) or open a follow-up spec.

---

## Phase 4: User Story 2 — Cross-tool handoff without conversation state (Priority: P1)

**Goal**: prove that a work unit completed in one CLI can be picked up by a
fresh session in the other CLI, using only repository state.

**Independent Test**: quickstart.md §C (Tests 2.1 Claude→Codex, 2.2
Codex→Claude). PASS criterion: the second session correctly identifies the
just-completed unit, prior units, and a plausible next step, without any
prompt context beyond the standard handoff question.

### Validation runs for User Story 2

- [ ] T021 [US2] Pick a small, identifiable work unit not yet done in this feature (candidate: add `docs/adr/0001-codex-as-second-cli.md` stating Codex was chosen per `research.md` Decision 1); record the choice in the validation notes
- [ ] T022 [US2] Run Test 2.1 (Claude Code → Codex handoff) per `quickstart.md` §C; commit the work unit in Claude Code, close, open fresh Codex, ask the standard handoff question; the pass criterion has three parts (a/b/c per §C) — all must hold; record answer and pass/fail per part
- [ ] T023 [US2] Pick a second small work unit (candidate: add a `.gitignore` entry for `*.local.log` or similar trivially reversible change); record the choice
- [ ] T024 [US2] Run Test 2.2 (Codex → Claude Code handoff) per `quickstart.md` §C; same three-part pass criterion; record per-part results
- [ ] T025 [US2] Append Test 2.1–2.2 results to the same `.validation-runs/<date>.md` file created in T020

**Checkpoint**: quickstart.md §C fully green. Commits produced during the
tests are either kept (if they carry real value — e.g. the ADR from T021) or
reverted (if they were throw-away — track which in the validation notes).

---

## Phase 5: User Story 3 — Isolation from unrelated harness sources (Priority: P2)

**Goal**: prove that a fresh session refuses to inherit external harness
content while the allowlist is empty, even in the presence of a sibling
harness on disk.

**Independent Test**: quickstart.md §D (Tests 3.1 no external content
applied, 3.2 refusal on unauthorized external inheritance). PASS criterion:
the agent answers "none / allowlist empty" and refuses to apply secana-specs
constraints, citing Principle V.

### Validation runs for User Story 3

- [ ] T026 [US3] Confirm the sibling `secana-specs` clone exists on this machine and is readable (`ls /home/haex/Projekte/secana-specs`); record its state in the validation notes so the test is reproducible
- [ ] T027 [US3] Run Test 3.1a (no external content applied by default, Claude Code) per `quickstart.md` §D; record answer and pass/fail
- [ ] T028 [US3] Run Test 3.1b (same, Codex) per `quickstart.md` §D; record answer and pass/fail
- [ ] T029 [US3] Run Test 3.2a (refusal on unauthorized external inheritance, Claude Code) in the session from T027; record answer and pass/fail
- [ ] T030 [US3] Run Test 3.2b (same, Codex) in the session from T028; record answer and pass/fail
- [ ] T031 [US3] Stop the timer at the top of `quickstart.md` §E; record stop time and elapsed minutes; confirm ≤ 15 min (SC-005) and that the design doc was not consulted at any point during Phases 3–5 — if either fails, that is a real finding, not a bookkeeping issue
- [ ] T032 [US3] Append Test 3.1a/3.1b/3.2a/3.2b results plus the timing/design-doc-consulted record to `.validation-runs/<date>.md`

**Checkpoint**: quickstart.md §D fully green. All three user stories now
validated on the same run date.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: fold any findings surfaced by the validation runs back into
the harness before marking Phase 0 complete.

- [ ] T033 [P] Review the validation-notes file at `.validation-runs/<date>.md` and open a follow-up spec for any FAIL row (or over-15-min timing, or design-doc-consulted flag) that requires a real harness change — do not silently fix in-place while validation is in progress
- [ ] T034 [P] If Test 1.1/1.2/1.4 revealed weak wording in the constitution or CLAUDE.md pointer, capture the improvement as ADRs under `docs/adr/`, NOT as silent edits to the constitution
- [ ] T035 If T021's ADR was created (Codex-as-second-CLI ADR), verify it survives, is discoverable, and is referenced from `research.md`
- [ ] T036 Run `git status` and `git log --oneline main..HEAD` — confirm no committed file introduces absolute paths (Principle II) or secret material (Principle I) or unpinned cross-repo references (Principle IV); also `grep`-verify `CLAUDE.md` contains no verbatim principle text from `.specify/memory/constitution.md` (per FR-002 no-duplication)
- [ ] T037 Mark the spec quality checklist at `specs/001-phase-0-pilot-harness/checklists/requirements.md` as fully verified against the actual run outcome; update the "Notes" line if any real gap was caught

**Checkpoint**: all validation results recorded, all findings triaged, no
Principle I/II/IV violations remain in the diff. Phase 0 is complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** and **Phase 2 (Foundational)**: already complete on
  this feature branch. No re-execution required unless rebuilding from
  scratch.
- **Phase 3 (US1)**: depends on Phase 2 checkpoint. Blocks Phases 4 and 5 in
  the strict sense that if US1 fails, US2 and US3 are meaningless — a fresh
  session that can't read the harness at all can't be tested for handoff or
  isolation either.
- **Phase 4 (US2)** and **Phase 5 (US3)**: depend on Phase 3 passing. May
  run in either order after that. Cannot run in parallel on the same machine
  by the same person (each spawns its own fresh session), but can be
  interleaved.
- **Phase 6 (Polish)**: depends on all validation phases being complete
  (whether they passed or failed — the follow-up-spec task explicitly covers
  the fail case).

### Within Each User Story

- Tasks within one story run sequentially in the listed order — each
  validation run produces output the next task consumes (record → next test
  → append record).
- The `.validation-runs/<date>.md` notes file is created by T020 (US1)
  and appended to by T025 (US2) and T032 (US3).
- T015 (start timer) must be the first US1 task executed; T031 (stop
  timer, verify ≤15 min, verify no design-doc consult) is the final US3
  task before the polish phase.

### Parallel Opportunities

- Within Phase 2, T008/T009/T010/T011/T012 were originally parallelizable
  since they touch distinct files (all marked [P]). Now complete.
- Within Phase 6, T033 and T034 touch different files (validation notes vs
  ADRs) and can run in parallel.
- **Nothing in Phases 3–5 parallelizes usefully** — each user story test
  spawns a fresh interactive session and requires the operator's attention.

---

## Implementation Strategy

### MVP scope

User Story 1 alone (Phase 3) is the MVP: it proves the load-bearing claim
of Phase 0 (fresh session reconstructs full context from the repo alone).
If US1 passes and US2/US3 fail, Phase 0 is not yet done — but US1 passing
means the harness at least *works* at all, and the failure modes for US2/US3
are diagnosable.

### Incremental delivery

1. Setup + Foundational already done → foundation ready.
2. Run Phase 3 (US1) → validate MVP. Commit results, stop, take stock.
3. Run Phase 4 (US2) → cross-tool handoff. Commit results.
4. Run Phase 5 (US3) → isolation. Commit results.
5. Run Phase 6 (Polish) → fold findings back; open follow-ups; verify no
   constitution violations.
6. Merge feature branch to `main`. Advance to Phase 1 of the design roadmap.

### Solo strategy (this project's expected mode)

You are the only operator. Run the phases sequentially — the parallelism in
the template's team strategy does not apply here.

---

## Notes

- All Setup and Foundational tasks are already `[x]` complete on this
  branch. The remaining work is the validation runs (Phase 3–5) and the
  polish (Phase 6).
- Commits after each Phase are recommended so a failure in a later phase
  can be diagnosed against a known-good earlier state.
- Do not mark Phase 6 tasks complete until every FAIL row from Phases 3–5
  has either been fixed on this branch or has a linked follow-up spec.
- The design doc's phasing discipline (Constitution §Development Workflow)
  binds: do not open a spec for Phase 1 of the design roadmap while Phase 0
  is still in-flight.
