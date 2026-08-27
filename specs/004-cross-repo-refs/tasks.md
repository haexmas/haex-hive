---
description: "Tasks for Spec 004 — Cross-Repo References (Phase 1)"
---

# Tasks: Spec 004 — Cross-Repo References (Phase 1)

**Input**: Design documents from `specs/004-cross-repo-refs/`
**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: this feature ships shell-driven tests (Python-stdlib tool
tested via bash + `set -e` + string assertions). Tests are REQUIRED,
not optional — FR-024, FR-025, FR-026 name them as deliverables.

**Checkbox freshness is load-bearing.** When a task is completed, tick
its checkbox in the same commit as the task's output — or at the
latest in the next commit, before starting the next task. Handoff
queries ("what was just done, what remains, what is the next step?")
read this file's checkbox state as the primary state document; stale
ticks systematically drift the answers toward pending items that are
secretly done. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: tasks grouped by phase. Foundational work is heavy
here because every user story consumes the same tool + config surface.
User Story phases (US1..US4) then extend that surface with subcommand-
specific behavior and their own tests. Within each US phase, tests and
implementation are interleaved rather than strictly test-first — the
shell harness is easier to write against a partially-working tool than
purely predictively.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: `[US1]`, `[US2]`, `[US3]`, `[US4]` mapping to the user stories in `spec.md`
- File paths in each task are repo-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: directory scaffolding and helper scripts everything below depends on.

- [ ] T001 Create the new source directories `.specify/schemas/` and `tests/spec-resolve/fixtures/` (empty; contents land in later tasks)
- [ ] T002 [P] Create `tests/spec-resolve/run-all.sh` as the test entrypoint (executable stub calling each `test-*.sh` in order, `set -euo pipefail`, aggregates pass/fail count) at `tests/spec-resolve/run-all.sh`
- [ ] T003 [P] Add `tests/spec-resolve/fixtures/.tmp/` and any generated fixture output to `.gitignore` (the generated repos are never committed) at `.gitignore`

**Checkpoint**: directories in place, test runner stub commits.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: config schema, config migration, constitution PATCH, ADR, and the tool's shared skeleton (config loader + validation) that every user story consumes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete — every story exercises the tool's config-load path.

### 2a — Data-model artefacts

- [ ] T004 Write the canonical JSON Schema at `.specify/schemas/haex-hive.schema.json` following the draft in `specs/004-cross-repo-refs/contracts/haex-hive.schema.draft.json` — enforce `additionalProperties: false`, the `role` enum (Phase 1: `["constitution"]`), the URL-scheme pattern for `repository`, the SHA-only pattern for `revision`, and the `allOf` shape constraints for role-carrying vs permission-only entries
- [ ] T005 Migrate `.haex-hive.json` to the unified shape: remove the top-level `constitution` object, replace `external_sources.allowed: []` with `harness_sources: [{ role: "constitution", repository: "self", revision: "<current pinned SHA>", path: ".specify/memory/constitution.md" }]`; keep `identity`, `identity_note`, `groups`, `active_feature` unchanged at `.haex-hive.json`
- [ ] T006 Delete `.specify/system.yaml` (the `harness_sources` slot in `.haex-hive.json` is the sole allowlist location per FR-019) — verify no other file references the path

### 2b — Governance artefacts

- [ ] T007 Write ADR at `docs/adr/0005-unify-harness-sources-and-drop-system-yaml.md` documenting the rename `external_sources` → `harness_sources`, the collapse of the split `constitution` slot + `external_sources.allowed` into one array, and the removal of `.specify/system.yaml` — quote the pre- and post-shape and link to spec 004 + design doc
- [ ] T008 PATCH-bump the constitution: rewrite Principle V's wording to cite `.haex-hive.json`'s `harness_sources` array rather than `.specify/system.yaml`'s `external_sources.allowed` list; update the version line to `**Version**: 1.1.1 | **Ratified**: 2026-08-26 | **Last Amended**: 2026-08-27`; ensure the changes are pure wording (no principle removed, added, or relaxed) at `.specify/memory/constitution.md`
- [ ] T009 Update `.haex-hive.json`'s constitution entry `revision` field to the SHA of the T008 commit (the new v1.1.1 constitution) — same file already touched in T005, this is the post-PATCH re-pin

### 2c — Tool skeleton

- [ ] T010 Create the `spec-resolve` script skeleton at `.specify/scripts/spec-resolve` — `#!/usr/bin/env python3` shebang, executable bit set, `argparse` top-level with three subcommand parsers (`resolve`, `prefetch`, `status`) and a common `--repo` option; each subcommand handler is a stub raising `NotImplementedError` for now
- [ ] T011 Implement config-loading helpers in `spec-resolve`: functions to (a) locate `.haex-hive.json` relative to `--repo` or `cwd`, (b) parse JSON with a specific error type for malformed JSON, (c) run schema-mirror validation (targeted checks matching `haex-hive.schema.json`'s constraints) returning either a validated in-memory model or a list of validation errors with array-index + field pinpoints per FR-017 — same file `.specify/scripts/spec-resolve`
- [ ] T012 Implement common validators in `spec-resolve`: URL-scheme check (accept `^https://`, `^ssh://`, SCP-style `^[^/@:\s]+@[^/@:\s]+:.+$`; reject `file://`, `git://`, `http://`, bare paths per Q3 clarification), SHA pattern check (`^[0-9a-f]{7,40}$` with case-lower normalization per research Decision 4), and cache-path derivation (`sha256(repository).hexdigest()[:16]` per research Decision 2) — same file `.specify/scripts/spec-resolve`

### 2d — Test-fixture builder

- [ ] T013 Write `tests/spec-resolve/fixtures/build-fixtures.sh` — deterministic (`GIT_AUTHOR_DATE`, `GIT_COMMITTER_DATE`, `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL` all fixed strings) builder that creates a `tests/spec-resolve/fixtures/.tmp/` tree with synthetic external repos: (a) `external-repo-a/` with two commits and a stable SHA per research Decision 6, (b) `consumer-with-role-only/` containing a `.haex-hive.json` with only the constitution self-ref, (c) `consumer-with-external-permitted/` containing a `.haex-hive.json` whose `harness_sources` permits `external-repo-a` broadly — output the generated SHAs to stdout for downstream test scripts to consume

**Checkpoint**: config file + schema + constitution PATCH landed; tool skeleton loads and validates configs; test fixtures buildable. User-story work can begin.

---

## Phase 3: User Story 1 — Fresh session resolves pinned constitution (Priority: P1) 🎯 MVP

**Goal**: session-start snippet + `spec-resolve` can resolve `.haex-hive.json`'s pinned constitution reference end-to-end, cold and cached, on Linux, with no local path configuration.

**Independent Test**: run [quickstart.md](./quickstart.md) Story 1 and Story 1b end-to-end from a fresh clone (or fresh cache); both produce byte-identical constitution content, second run touches no network.

### Implementation for User Story 1

- [ ] T014 [US1] Implement the `--role` mode of `spec-resolve resolve` in `.specify/scripts/spec-resolve`: locate the role-carrying entry, refuse if more than one entry shares the role, refuse if the role isn't found; delegate to the resolve-triple path
- [ ] T015 [US1] Implement the `--repository/--revision/--path` direct triple mode of `spec-resolve resolve` in `.specify/scripts/spec-resolve`: validate input against helpers from T012, then dispatch to `self`-path or external-path branch
- [ ] T016 [US1] Implement the `self`-resolution branch in `spec-resolve` (called by T014/T015): run `git -C <repo> show <sha>:<path>` via `subprocess.run` with `check=False`, exit 3 with the specific-SHA message if the object is missing, stream the resolved bytes to stdout unmodified — same file `.specify/scripts/spec-resolve`
- [ ] T017 [US1] Implement the external-resolution branch in `spec-resolve` (called by T015 and later by prefetch): cache-hit check via `git -C <cache-dir> cat-file -e <sha>^{commit}`, fetch ladder per research Decision 3 (`fetch --depth=1 <url> <sha>` → `fetch <url> <sha>` → `fetch <url>` → full mirror fetch), presence recheck, then `git show <sha>:<path>` — same file
- [ ] T018 [US1] Implement `spec-resolve prefetch`: enumerate role-carrying entries + all `specs/*/spec-ref.json` files, deduplicate references, dispatch through T017 for external and T016 for `self`, update per-cache-dir `.haex-hive-cache-meta.json` with `last_fetch` — same file
- [ ] T019 [US1] Implement `spec-resolve status` (text mode default, per contract): compact one-liner `"N refs, M cached, last update-check: <date or 'never'>"`, drawn from cache-meta files only; `--json` mode emits the structured envelope from `contracts/spec-resolve.cli.md` — same file

### Tests for User Story 1

- [ ] T020 [P] [US1] Write `tests/spec-resolve/test-resolve.sh`: run T014 mode against the `consumer-with-role-only` fixture, assert exit 0 and stdout matches the constitution's pinned content byte-for-byte via `diff`
- [ ] T021 [P] [US1] Write `tests/spec-resolve/test-status.sh`: run `spec-resolve status` in a fresh fixture, assert stdout contains the `N refs, N cached` shape and exit 0; then use `--json` mode and assert JSON envelope parses and `refs_missing == 0`
- [ ] T022 [P] [US1] Write `tests/spec-resolve/test-prefetch.sh`: run `spec-resolve prefetch --dry-run` on a fixture with an unpopulated external cache, assert `MISSING` lines for each external ref; then run without `--dry-run` (using a local file-URL fixture — wait, no, this violates Q3; use a local synthetic bare-repo instead with a real `ssh://` alias or skip and use the smoke test), assert the cache dir populates
- [ ] T023 [US1] Run the quickstart's Story 1 + Story 1b sequences by hand on the actual `.haex-hive.json`, capture the output in `specs/004-cross-repo-refs/.validation-runs/2026-08-27-story-1.md`, verify SC-001 and SC-002 both pass

**Checkpoint**: MVP works. The load-bearing claim of Phase 1 ("fresh clone → constitution resolves without path configuration") is live and testable. All subsequent user stories layer on top.

---

## Phase 4: User Story 2 — Refusal of unpermitted references (Priority: P1)

**Goal**: `spec-resolve` refuses any reference not permitted by `harness_sources`, with actionable messages naming both the refused reference and the missing/mismatching scope. All four allowlist shapes exercised.

**Independent Test**: run [quickstart.md](./quickstart.md) Story 2; observe exit 1 with a specific stderr message and zero side effects.

### Implementation for User Story 2

- [ ] T024 [US2] Implement the allowlist-matching logic in `spec-resolve` (called by resolve's external branch and by prefetch's `spec-ref.json` enumeration): iterate `harness_sources` in array order, apply the four shape rules from `data-model.md`, return the first matching entry or `None` — role-carrying entries implicitly permit their own reference per FR-009; string-exact `repository` comparison per Q1; same file `.specify/scripts/spec-resolve`
- [ ] T025 [US2] Implement the refusal path in `spec-resolve resolve`: when T024 returns `None`, exit code 1 with stderr `spec-resolve: refusing reference <repo>@<sha>:<path> — not permitted by any entry in harness_sources.`; ensure no writes to the working tree in the failure path (defensive: no partial cache dir creation, no meta-file writes) — same file

### Tests for User Story 2

- [ ] T026 [P] [US2] Write `tests/spec-resolve/test-allowlist-refusal.sh`: for each of the four shape-refusal cases (shape 1 mismatch = wrong repo; shape 2 mismatch = wrong SHA; shape 3 mismatch = wrong path; shape 4 permit = role auto-permission), run the tool and assert (a) exit code 1, (b) stderr contains the offending reference triple and the mismatching-scope description, (c) no files modified in the fixture repo (checksum the fixture root before/after)
- [ ] T027 [US2] Run quickstart's Story 2 by hand against the actual `.haex-hive.json`, capture output in `specs/004-cross-repo-refs/.validation-runs/2026-08-27-story-2.md`, verify SC-006 holds

**Checkpoint**: Principle V's mechanical enforcement is live and tested for every allowlist shape. Story 1 + Story 2 together = Principle IV + V mechanically closed.

---

## Phase 5: User Story 3 — Malformed config rejected before harness work (Priority: P2)

**Goal**: any validation error in `.haex-hive.json` causes the resolver to refuse with an error message that pinpoints the offending entry + constraint. Schema and tool agree on every curated valid/invalid sample.

**Independent Test**: run [quickstart.md](./quickstart.md) Story 3 for each of the 5 malformation cases; observe exit 2 with specific stderr messages.

### Implementation for User Story 3

- [ ] T028 [US3] Extend `spec-resolve`'s config validator (from T011) with the full targeted-check set: unknown role name (list valid values in message), missing required field in role-carrying entry (name the missing field), forbidden field combination (`paths` + `role`, `path` without `role`, `repository: "self"` in permission-only entry), invalid SHA pattern, rejected URL scheme — every check MUST identify the offending entry by array index and MUST match the schema's equivalent constraint — same file `.specify/scripts/spec-resolve`

### Tests for User Story 3

- [ ] T029 [P] [US3] Create the curated valid/invalid sample set at `tests/spec-resolve/fixtures/config-samples/`: 5 valid configs (minimum, self-only, self + broad-scope, self + narrow-scope, self + path-list-scope) and ~10 invalid configs (missing `haex_hive_version`, wrong `haex_hive_version`, unknown role, `paths` on role entry, `path` on permission entry, `self` in permission entry, bad SHA, mixed-case SHA, `file://` scheme, `http://` scheme, bare local path). Each sample is a single `.json` file with a sibling `.expected.json` giving `{"expected_result": "accept"|"reject", "expected_error_substring": "..."}` for reject cases
- [ ] T030 [P] [US3] Write `tests/spec-resolve/test-schema-tool-agreement.sh`: for each sample from T029, run both (a) a schema validator invocation using the checked-in schema — allowed to use `python3 -m jsonschema` if available, else a minimal draft-07-aware Python one-liner shipped inside the test — and (b) `spec-resolve status`; assert both agree on accept/reject; on reject, assert the tool's stderr contains the sample's `expected_error_substring`
- [ ] T031 [P] [US3] Write `tests/spec-resolve/test-config-invalid.sh`: pick 3-4 representative malformations from T029 and run `spec-resolve status` on each (the same call the session-start snippet makes per FR-022); assert exit 2, assert stderr pinpoints the offending entry (array index + field + constraint) — this proves the session would refuse to start harness work, without needing to run the snippet itself (which lives per-operator, not in this repo)
- [ ] T032 [US3] Run quickstart's Story 3 by hand for each of the 5 malformation cases, capture output in `specs/004-cross-repo-refs/.validation-runs/2026-08-27-story-3.md`, verify SC-004 holds

**Checkpoint**: config errors are always caught early and always name the specific problem. Story 3's independent test criterion satisfied.

---

## Phase 6: User Story 4 — Editor validation via JSON Schema (Priority: P3)

**Goal**: operators editing `.haex-hive.json` in VSCode or JetBrains editors get inline validation and autocomplete pointing at `haex-hive.schema.json`.

**Independent Test**: with the operator's editor mapped per docs, deliberately introduce each of Story 3's malformations; editor MUST highlight the error before saving.

### Implementation + Documentation for User Story 4

- [ ] T033 [US4] Add a "JSON Schema editor mapping" section to `docs/spec-resolve.md` with copy-pasteable VSCode `settings.json` snippet mapping `.haex-hive.json` → `.specify/schemas/haex-hive.schema.json`, and JetBrains "JSON Schema Mappings" preferences-path instructions — file `docs/spec-resolve.md`
- [ ] T034 [P] [US4] Manually verify VSCode mapping: install the mapping in a scratch VSCode profile, open this repo's `.haex-hive.json`, introduce an unknown role, screenshot or note the inline error, capture in `specs/004-cross-repo-refs/.validation-runs/2026-08-27-story-4.md`
- [ ] T035 [P] [US4] (Optional if operator lacks JetBrains) — same manual verification against a JetBrains editor OR document skip with rationale (single-operator, VSCode-only Phase 1) in the same validation-run file

**Checkpoint**: Story 4 documented and verified for the operator's actual editor. If JetBrains skipped, rationale is captured; not a failure.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: complete the documentation surface, exercise the real-external-repo smoke test, integrate the snippet-extension text, and reset the feature pointer.

- [ ] T036 [P] Write `docs/spec-resolve.md`'s full content: introduction, command surface (copy from `contracts/spec-resolve.cli.md` as the source of truth), cache location + wipe safety, JSON Schema editor mapping (from T033), snippet extension text (see T037), how-to for a consuming repo to wire an external `harness_sources` entry — file `docs/spec-resolve.md`
- [ ] T037 [P] In `docs/spec-resolve.md`, add the "Snippet extension" section with the exact Step 8 text an operator copy-pastes into their user-level `CLAUDE.md`/`AGENTS.md` to gain `spec-resolve status` verification at session start — cite design doc §"Snippet extension" — same file
- [ ] T038 Run the manual smoke test against a real `secana-specs` SHA in a scratch checkout OUTSIDE this repo (never modify `haex-hive`'s own `.haex-hive.json` per FR non-goals): document the scratch-checkout layout, the exact SHA used, the resolved content hash, and cleanup in `specs/004-cross-repo-refs/.validation-runs/2026-08-27-smoke-test.md`; the smoke test's success is FR-026's acceptance
- [ ] T039 Run `tests/spec-resolve/run-all.sh`, capture the full pass/fail report in `specs/004-cross-repo-refs/.validation-runs/2026-08-27-run-all.md`; must be 100% pass before merge
- [ ] T040 Verify SC-008 mechanically: run `git grep external_sources` on the tip of this branch and confirm the only remaining matches are in `docs/adr/`, `docs/plans/`, and `specs/00[12]-*` historical files (ADRs and this design doc explicitly cite the old name for traceability); capture the grep output in `.validation-runs/2026-08-27-sc-008.md`
- [ ] T041 Verify SC-007 mechanically: `.specify/memory/constitution.md`'s version line reads `**Version**: 1.1.1 | ...` and Principle V's body cites `.haex-hive.json` (not `.specify/system.yaml`); note in `.validation-runs/2026-08-27-sc-007.md`
- [ ] T042 Update the constitution's `revision` in `.haex-hive.json` (final time this branch) to the SHA of the final polish commit — same as T009 but confirming the pin matches the actual landing SHA
- [ ] T043 Reset `.specify/feature.json`'s `feature_directory` to `null` (post-merge feature-pointer reset, matching the Spec 002 T028/T029 pattern) — this task ticks only in the merge commit; do NOT tick it before merge

**Checkpoint**: everything Spec 004 promised is on disk, verified, and traceable. Ready to merge to `main` and advance the design roadmap's Phase 1 status to "in daily use".

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; three tasks, T002/T003 parallel.
- **Phase 2 (Foundational)**: depends on Phase 1. Within Phase 2:
  - T004 (schema) is independent; can start immediately.
  - T005 depends on the current constitution SHA — its `revision` field
    will be re-pinned by T009 after T008 lands, so T005 uses the OLD
    SHA initially and T009 overwrites it. Two-step is intentional; a
    single-step re-pin would require pinning to a SHA that doesn't
    exist yet.
  - T006 depends on T005 landing (otherwise the `system.yaml`
    references in migrated code point at a deleted file).
  - T007 (ADR) is independent; can start alongside T004.
  - T008 (constitution PATCH) depends on nothing else in Phase 2;
    the version bump is a wording change that stands alone.
  - T009 depends on T005 + T008 (needs new constitution SHA and the
    already-migrated `.haex-hive.json`).
  - T010–T012 (tool skeleton) are independent of the config-migration
    tasks; can run parallel to T004–T009.
  - T013 (fixture builder) depends on T010–T012 being at least
    stub-level so it can smoke-test invocation.
- **Phase 3 (US1)**: depends on Phase 2 checkpoint (needs config + skeleton + fixtures).
- **Phase 4 (US2)**: depends on Phase 3 (US2 extends the resolve subcommand).
- **Phase 5 (US3)**: depends on Phase 2 config validator; MAY start in parallel with Phase 4 (US3's extensions to the validator don't collide with US2's changes to the matcher).
- **Phase 6 (US4)**: depends on Phase 2's schema file (T004); may start in parallel with US1/US2/US3 (docs task).
- **Phase 7 (Polish)**: depends on Phases 3–6 all being complete.

### Within Each User Story

- Within US1: T014–T019 are sequential on the same file (`spec-resolve`); T020–T022 are parallel among themselves (separate test files) but depend on T014–T019 being at least skeleton-complete; T023 depends on the whole chain.
- Within US2: T024 → T025 sequential (same file, matcher then refusal); T026 depends on T024/T025; T027 depends on T024–T026.
- Within US3: T028 (validator extension) is sequential; T029 (samples) is [P] with T028; T030/T031 depend on T028 + T029; T032 depends on the chain.
- Within US4: T033 is the doc addition; T034/T035 are manual verifications in parallel.

### Parallel Opportunities

- Phase 1: T002 + T003.
- Phase 2: {T004, T007, T008} in parallel; {T010, T011, T012} sequential (same file) but the block runs parallel to the T004/T007/T008 block.
- Phase 3: T020 + T021 + T022 parallel.
- Phase 5: T029 + T030 + T031 parallel (once T028 lands).
- Phase 6: T034 + T035 parallel.
- Phase 7: T036 + T037 parallel; T040 + T041 parallel; T038 sequential (needs the tool green).
- Cross-phase: **US3 and US4 can proceed in parallel with US2 after US1 lands** — US3's validator changes and US4's docs/manual-verification touch different files from US2's matcher changes.

---

## Implementation Strategy

### MVP scope

Phases 1 + 2 + 3 alone = MVP. If the operator ships nothing else, they have:
- The new `.haex-hive.json` shape landed and validated.
- The constitution at v1.1.1 with correct Principle V wording.
- A working `spec-resolve` tool that resolves the pinned constitution
  end-to-end, cold and cached, offline-safe on the second run.

That closes the load-bearing claim of Phase 1 in the design roadmap.
US2 (refusal), US3 (malformed-config UX), and US4 (editor validation)
harden it — necessary before calling Spec 004 complete, but not blocking
the "the mechanism works" verdict.

### Incremental delivery

1. Phases 1–3 → MVP works, commit, take stock.
2. Phase 4 (US2) → Principle V mechanical enforcement complete.
3. Phase 5 (US3) → config error UX polished.
4. Phase 6 (US4) → editor mapping documented + verified.
5. Phase 7 (Polish) → smoke test against real external SHA + full doc pass + SC-007/008 verified.
6. Merge feature branch to `main`. Advance design roadmap Phase 1 to "in daily use".

### Solo strategy (this project's expected mode)

You are the only operator. Sequential execution phase by phase. The
`[P]` markers indicate where solo-serial can be re-ordered without
dependency risk — useful for interleaving doc-writing with code-writing
if you need a change of gears.

---

## Notes

- Every code change should trace to a specific FR in `spec.md`. If a
  task's diff doesn't map to at least one FR, either the task is out
  of scope or an FR is missing.
- Commits after each Phase are recommended so a failure in a later
  phase can be diagnosed against a known-good earlier state.
- Do not mark Phase 7 tasks complete until every earlier task's tests
  pass in T039's `run-all.sh` output.
- Constitution version stamp v1.1.1 MUST be in place BEFORE the branch
  merges to `main`; the design roadmap Phase 1 status remains blocked
  until then.
