---

description: "Tasks for Spec 006 — Multi-Spec External-Ref (Multi-Item Cross-Repo References)"
---

# Tasks: Multi-Spec External-Ref

**Input**: Design documents from `specs/006-multi-spec-external-refs/`
**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required for user stories), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: The spec explicitly requests shell tests under
`tests/multi-spec-external-ref/` mirroring the Spec 005 `tests/haex-init/`
pattern (see spec.md §Testing strategy — 14 named test files). Test tasks
are therefore included.

**Checkbox freshness is load-bearing.** When a task is completed, tick its
checkbox in the same commit as the task's output — or at the latest in the
next commit, before starting the next task. Handoff queries ("what was just
done, what remains, what is the next step?") read this file's checkbox
state as the primary state document; stale ticks systematically drift the
answers toward pending items that are secretly done. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: Tasks grouped by user story from [spec.md](spec.md).
US1 (P1) is the MVP; US2, US3 (both P2) harden the mechanism; US4 (P3)
adds the DX-critical `add-source` interactive + `--from-repo` bootstrap.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 / US4 in Phases 3–6
- Setup, Foundational, Polish: no story label

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test-suite scaffolding + fixture bootstrap for every subsequent phase.

- [ ] T001 Create test root directory `tests/multi-spec-external-ref/` with subdirectories `fixtures/`, `lib/`, and top-level runner scaffolding
- [ ] T002 [P] Add `tests/multi-spec-external-ref/lib/common.sh` shared helpers (temp-dir setup, cleanup traps, XDG_STATE_HOME + XDG_CACHE_HOME isolation, `mktemp`-based `$HAEX_HIVE_STATE` override — mirrors `tests/haex-init/lib/`)
- [ ] T003 [P] Add `tests/multi-spec-external-ref/lib/fixture-producer.sh` — bootstraps a bare-repo local "producer" with speckit-shaped layout (`.specify/memory/constitution.md`, `.specify/workflows/`, `.specify/templates/`, `.specify/schemas/`, `tools/some-tool/`), commits multiple revisions for SHA-bump tests
- [ ] T004 Add `tests/multi-spec-external-ref/run-all.sh` — sequentially executes every `test-*.sh`, aggregates pass/fail, exits non-zero on any failure (mirrors `tests/haex-init/run-all.sh`)
- [ ] T005 [P] Add `tests/multi-spec-external-ref/lib/assertions.sh` — helpers for `assert_exit_code`, `assert_file_exists`, `assert_file_mode`, `assert_json_key_equals`, `assert_no_stderr_pattern`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + shared code paths that every user story consumes. NO user story work begins until this phase is complete.

**⚠️ CRITICAL**: All Phase 3–6 tasks depend on Phase 2 completion.

### Schemas

- [ ] T006 Extend `.specify/schemas/haex-hive.schema.json` with discriminated `harness_sources[]` entry variants per [contracts/haex-hive.schema.json.patch.md](contracts/haex-hive.schema.json.patch.md) — adds `ExternalHarnessEntry` and `ItemDeclaration` `$defs`, preserves existing `ConstitutionEntry` and `PermissionOnlyEntry` shapes
- [ ] T007 [P] Create `.specify/schemas/haex-hive-local.schema.json` per [contracts/haex-hive-local.schema.json.md](contracts/haex-hive-local.schema.json.md) — full schema for the device-local resolution table

### Shared validators (single-file additions to haex-init CLI module)

- [ ] T008 Add URL-validation helper in `.specify/scripts/haex-init` — HTTPS-userinfo rejection via `urllib.parse.urlparse` per FR-007 and Research §10
- [ ] T009 Add SHA-validation helper in `.specify/scripts/haex-init` — regex `^[0-9a-f]{40}$` per FR-002
- [ ] T010 Add storage-name-validation helper in `.specify/scripts/haex-init` — regex `^[A-Za-z0-9._-]+$` plus reserved-name filter (`.`, `..`, `CON`, `PRN`, `AUX`, `NUL`, `COM1`-`COM9`, `LPT1`-`LPT9`, case-insensitive) per FR-008
- [ ] T011 Add alias-slug-validation helper in `.specify/scripts/haex-init` — regex `^[a-z0-9][a-z0-9-]*$` per FR-006
- [ ] T012 [P] Add repo-relative-path validation helper — reject absolute paths, reject `..` traversal, per FR-005 and data-model §RepoRelativePath

### State-area management (single-file additions to haex-init CLI module)

- [ ] T013 Add `$HAEX_HIVE_STATE` resolver in `.specify/scripts/haex-init` — checks `HAEX_HIVE_STATE` env var, then `$XDG_STATE_HOME/haex-hive` (Linux/WSL2), then `~/Library/Application Support/haex-hive` (macOS), then `%LOCALAPPDATA%\haex-hive` (Windows), per Research §1
- [ ] T014 Add state-area directory creator with `0700` mode on Unix — creates `$HAEX_HIVE_STATE`, `$HAEX_HIVE_STATE/repos/` on demand, chmod-verified, per FR-038 and Research §4

### Git subprocess wrappers (single-file additions to haex-init CLI module)

- [ ] T015 Add git-subprocess helper module in `.specify/scripts/haex-init` — wraps `git clone`, `git fetch`, `git cat-file`, `git ls-tree`, `git remote get-url` per Research §9; each function returns `(returncode, stdout, stderr)` and never raises
- [ ] T016 Add `git ls-tree` typed-object enumeration — returns list of `(objecttype, path)` tuples for a pinned SHA, filters symlinks and non-regular per FR-005 case d

### Atomic file operations + locking (single-file additions to haex-init CLI module)

- [ ] T017 Add atomic-file-write helper in `.specify/scripts/haex-init` — writes to same-directory `.tmp-<pid>-<rand>`, fsyncs, then `os.replace`, per FR-023/FR-024 and Research §3
- [ ] T018 [P] Add directory-scoped lock in `.specify/scripts/haex-init` — `fcntl.flock` on Unix (Linux/macOS/WSL2), `msvcrt.locking` on Windows, single file `<producer-clone>/.sync.lock`, per FR-025 and Research §2
- [ ] T019 [P] Add stale-temp-file cleanup in `.specify/scripts/haex-init` — scans for `.tmp-<pid>-<rand>` siblings and removes those whose PID is no longer alive (Unix) or older than 24h (Windows)

### Structured error emission (single-file additions to haex-init CLI module)

- [ ] T020 Add structured stderr emitter in `.specify/scripts/haex-init` — formatted per haex-init-sync.cli.md contract (`<ROLE-CODE>: <problem>` + `entry:` + `detail:` + `fix:` lines); reused by all Phase 3-6 error paths

### Basic add-source foundation (single-file additions to haex-init CLI module)

- [ ] T021 Add `add-source` sub-command entry-point in `.specify/scripts/haex-init` — argparse skeleton for all documented flags (`--from-repo`, `--url`, `--revision`, `--name`, `--auto-include`, `--additional-include`, `--role`, `--replace`, `--no-sync`, `--yes`) per contracts/haex-init-add-source.cli.md
- [ ] T022 Add `.haex-hive.json` atomic-rewrite helper in `.specify/scripts/haex-init` — reads current file, applies mutator function, validates result against extended `haex-hive.schema.json` (T006), writes atomically via T017; respects operator umask (does NOT chmod)

### Sync foundation (single-file additions to haex-init CLI module)

- [ ] T023 Add `sync` sub-command entry-point in `.specify/scripts/haex-init` — argparse skeleton for `--dry-run` and `--yes` flags per contracts/haex-init-sync.cli.md
- [ ] T024 Add ExpansionPlan builder in `.specify/scripts/haex-init` — reads `.haex-hive.json`, builds in-memory `ExpansionPlan` with per-entry `EntryPlan`, per-key `ResolvedPath`, per-source `ConstitutionSource`; enforces global collision checks (FR-020 name/URL, alias, key) BEFORE any I/O

### Foundational tests

- [ ] T025 [P] Add `tests/multi-spec-external-ref/test-schema-validation.sh` — asserts extended `haex-hive.schema.json` accepts valid Spec 004 shapes AND new `external-harness` shape; rejects malformed entries (missing required fields, invalid SHA, invalid name, HTTPS with userinfo pre-write catch)
- [ ] T026 [P] Add `tests/multi-spec-external-ref/test-alias-grammar-validation.sh` — asserts alias-slug helper accepts valid slugs (`constitution`, `plan-review-workflow`, `spec-023`) and rejects invalid ones (uppercase, colon, path prefix, unicode, whitespace, empty)
- [ ] T027 [P] Add `tests/multi-spec-external-ref/test-storage-identity-and-origin.sh` — asserts storage-name validation rejects reserved names + separators + traversal; asserts origin-URL verification refuses reuse on mismatch

**Checkpoint**: Foundation ready — Phase 3 user story implementation can now begin.

---

## Phase 3: User Story 1 — Fresh consumer inherits Constitution (Priority: P1) 🎯 MVP

**Goal**: An operator can, on a fresh consumer repo, add a producer entry with one explicit `role: "constitution"` item + pinned revision, run `haex-init sync`, and end up with a Claude Code session that quotes the producer's Constitution as its governing rules.

**Independent Test**: [quickstart.md](quickstart.md) Path A steps 1–5 succeed end-to-end against a local fixture producer. Session-start snippet reads `.haex-hive.local.json`, extracts Constitution content via Path-Return, injects it into session context.

### Tests for User Story 1

- [ ] T028 [P] [US1] Add `tests/multi-spec-external-ref/test-fresh-external-harness.sh` — end-to-end US1 acceptance test: initialise consumer, add-source with constitution-only, sync, verify `.haex-hive.local.json` shape, verify extract file bytes match producer's Constitution at pinned SHA, verify `0600` file mode
- [ ] T029 [P] [US1] Add `tests/multi-spec-external-ref/test-constitution-order.sh` — asserts session-start-emission order with (a) only a nested constitution item, (b) both a top-level `role: "constitution"` AND a nested constitution item — asserts exact label text per Research §7 and byte order per FR-011
- [ ] T030 [P] [US1] Add `tests/multi-spec-external-ref/test-file-permissions.sh` — asserts `0700` dirs and `0600` files on Unix per FR-038; asserts existing tighter permissions are preserved (unchanged)
- [ ] T031 [P] [US1] Add `tests/multi-spec-external-ref/test-sync-exit-codes.sh` — asserts exit code 0 on clean sync; exit 2 on schema-invalid config; exit 3 on unreachable pinned SHA against fixture with wrong SHA

### Implementation for User Story 1

- [ ] T032 [US1] Implement `sync` from-scratch clone in `.specify/scripts/haex-init` — invokes T015 `git clone` for missing producer, sets `0700` mode via T014
- [ ] T033 [US1] Implement `sync` fetch-and-reachability in `.specify/scripts/haex-init` — `git fetch origin` on existing producer clone, then `git cat-file -e <sha>^{commit}` reachability check; falls back to `git fetch origin <sha>` on miss; exits 3 if pinned SHA still not reachable
- [ ] T034 [US1] Implement extract-content flow in `.specify/scripts/haex-init` — for each `ResolvedPath` in ExpansionPlan (from T024), runs `git cat-file blob <sha>:<path>` into temp file via T017 atomic write, then chmods `0600`; reuses existing extract file if byte-length matches
- [ ] T035 [US1] Implement `.haex-hive.local.json` regenerator in `.specify/scripts/haex-init` — serialises complete `LocalStateTable`, validates against `haex-hive-local.schema.json` (T007), atomically writes via T017, chmods `0600`; refuses to overwrite if any preflight step failed (FR-022)
- [ ] T036 [US1] Implement `.gitignore` marker-block entry for `.haex-hive.local.json` — reuses Spec 005 marker-block machinery; appends `.haex-hive.local.json` inside a `# haex-init BEGIN … END` block; detects duplicate outside-marker entries and prints a stdout warning without adding a second (FR-018, Edge Case)
- [ ] T037 [US1] Implement `constitutions[]` builder in `.specify/scripts/haex-init` — orders per FR-011 (top-level `role: "constitution"` first, then nested `items[]` in `harness_sources[]` order), generates labels per Research §7 (`self` / `<url>@<short-sha>` / `<name>:<alias>@<short-sha>`)
- [ ] T038 [US1] Extend session-start snippet template `.specify/templates/haex-hive-session-instructions.md` — when `.haex-hive.local.json` exists in the consumer, read its `constitutions[]`, emit each source's raw bytes with label line between documents; retains Spec 004 behavior when no `.haex-hive.local.json` is present
- [ ] T039 [US1] Implement basic `add-source` (non-interactive flag-only) in `.specify/scripts/haex-init` — accepts `--url` + `--revision` + `--role constitution:<path>:<alias>`, builds `ExternalHarnessEntry`, validates via T008/T009/T010/T011, appends to `harness_sources[]` via T022, triggers `sync` unless `--no-sync`

**Checkpoint**: US1 fully functional. Fresh consumer inherits Constitution end-to-end. `tests/multi-spec-external-ref/run-all.sh` green for T028-T031.

---

## Phase 4: User Story 2 — Consumer inherits additional content (Priority: P2)

**Goal**: The same operator can, on top of US1, declare `auto_include: "speckit-defaults"` and/or `additional_include: [...]` and have agents read those files via Path-Return.

**Independent Test**: [quickstart.md](quickstart.md) Path A with expanded include configuration; agent Reads a specific extracted skill file at its absolute path from `.haex-hive.local.json`.

### Tests for User Story 2

- [ ] T040 [P] [US2] Add `tests/multi-spec-external-ref/test-auto-include-speckit-defaults.sh` — asserts the preset expands to exactly `.specify/memory/**`, `.specify/workflows/**`, `.specify/templates/**`, `.specify/schemas/**` at the pinned SHA; asserts new files appearing at a later SHA appear after `sync` with new SHA
- [ ] T041 [P] [US2] Add `tests/multi-spec-external-ref/test-additional-include.sh` — asserts literal directory path expansion, literal file path selection, and `foo/*.md` glob at pinned tree; asserts sorted + deduplicated results
- [ ] T042 [P] [US2] Add `tests/multi-spec-external-ref/test-additional-include-expansion.sh` — asserts `**` glob crosses directory boundaries; asserts empty-glob refusal (exit 2 case c); asserts symlink/non-regular rejection (exit 2 case d)
- [ ] T043 [P] [US2] Add `tests/multi-spec-external-ref/test-explicit-items-aliases.sh` — asserts explicit items produce `<name>:<alias>` keys; asserts duplicate alias inside one entry refuses (exit 2); asserts alias/path-key collision on same source file resolves to alias-key only (data model tie-break)

### Implementation for User Story 2

- [ ] T044 [P] [US2] Implement `auto_include` preset expander in `.specify/scripts/haex-init` — for `speckit-defaults`, uses T016 to enumerate files under the four subtree roots at pinned SHA, filters non-regular entries, produces path-keys per data-model §Layer B
- [ ] T045 [P] [US2] Implement `additional_include` glob expander in `.specify/scripts/haex-init` — uses `fnmatch.fnmatchcase` per Research §6, iterates T016 tree listing, supports literal file / literal directory / glob including `**`, sorts + dedupes per FR-005; enforces non-empty match per FR-026 case c
- [ ] T046 [US2] Extend `ExpansionPlan` builder (T024) to consume T044 + T045 outputs — merges expanded paths into per-entry `resolved_keys`, applies tie-break (alias > path-key on same source file per data-model §Layer B tie-break)
- [ ] T047 [US2] Extend `add-source` (T039) to accept `--auto-include`, `--additional-include`, and multiple `--role` items — validates each via T008-T012, packs into `ExternalHarnessEntry`, writes via T022
- [ ] T048 [US2] Wire `.haex-hive.local.json` regenerator (T035) for multi-source scenarios — `resolved` map merges keys from every entry; global collision check (FR-020 across-entry) surfaces before any write

**Checkpoint**: US2 fully functional. Consumer can inherit arbitrary producer content via preset + explicit paths.

---

## Phase 5: User Story 3 — SHA-bump update flow (Priority: P2)

**Goal**: Operator changes `revision:` in `.haex-hive.json`, runs `haex-init sync`, and receives updated resolved paths under the new SHA. Rename detection refuses loudly.

**Independent Test**: [quickstart.md](quickstart.md) Path C — bump SHA on fixture producer to a revision that adds files (clean bump) and to one that renames an explicit item's path (refuse). Verify `.haex-hive.local.json` intact on refuse.

### Tests for User Story 3

- [ ] T049 [P] [US3] Add `tests/multi-spec-external-ref/test-sha-bump-clean.sh` — from a synced US1/US2 state, bumps `revision:` to a fixture SHA where content changed but no explicit path renamed; asserts `.haex-hive.local.json` regenerates with new paths under `.extracts/@<new-sha>/`; asserts old `.extracts/@<old-sha>/` remains (NG-5)
- [ ] T050 [P] [US3] Add `tests/multi-spec-external-ref/test-sha-bump-rename-refuses.sh` — from synced state, bumps to a fixture SHA where an explicit `items[]` path was renamed; asserts sync exits 2 case b, structured stderr diagnostic names the unresolvable path within 5 seconds (SC-007), asserts `.haex-hive.local.json` byte-identical to pre-bump state (SC-003)
- [ ] T051 [P] [US3] Add `tests/multi-spec-external-ref/test-atomic-sync-publication.sh` — injects extraction failure mid-sync (e.g., ENOSPC simulation via tmpfs full trick, or a fixture SHA that references a blob the local clone cannot fetch), asserts `.haex-hive.local.json` remains at the previous fully-successful state; asserts no partial `.extracts/@<sha>/` directory is finalised

### Implementation for User Story 3

- [ ] T052 [US3] Extend `sync` preflight (T024) with rename detection — after fetch, for each explicit `items[]` entry, verify `path:` exists as regular-file/directory at pinned SHA via T016; refuse with structured error naming each unresolvable path (FR-026 case b, exit 2)
- [ ] T053 [US3] Extend `sync` regenerator (T035) to preserve prior state on any failure — all preflight and extract failures surface BEFORE the final `.haex-hive.local.json.tmp-*` → `os.replace()` step (FR-022); best-effort cleanup of temp files on failure
- [ ] T054 [US3] Add old-SHA extract preservation policy — sync never deletes `.extracts/@<sha>/` subtrees for SHAs no longer referenced; documented as NG-5 behavior in spec, formalises in code paths
- [ ] T055 [US3] Add `--dry-run` implementation for `sync` in `.specify/scripts/haex-init` — computes ExpansionPlan, prints planned actions (clones, fetches, extract writes) to stdout in Research-§6-style structured plan; exits 0 (nothing to do) or 1 (actions pending) per contracts/haex-init-sync.cli.md

**Checkpoint**: US3 fully functional. SHA-bump flow safe; rename detection refuses loudly; dry-run available.

---

## Phase 6: User Story 4 — `haex-init add-source` interactive + `--from-repo` bootstrap (Priority: P3)

**Goal**: Operator can add a source interactively (from scratch) or bootstrap from a neighbor consumer's `.haex-hive.json`. Zero manual JSON editing (SC-009).

**Independent Test**: [quickstart.md](quickstart.md) Path B — on a device with an already-configured consumer, initialise a second consumer and run `add-source --from-repo <neighbor>`. Interactive prompt lists neighbor's entries; on accept, entry copied and `sync` succeeds without touching the neighbor's clone (reuse via origin verification).

### Tests for User Story 4

- [ ] T056 [P] [US4] Add `tests/multi-spec-external-ref/test-add-source-fresh.sh` — non-interactive full-flag `add-source`, interactive prompted `add-source` (fixture-provided TTY driver), asserts each validation refusal path (invalid SHA, HTTPS with userinfo, unsafe name, storage collision)
- [ ] T057 [P] [US4] Add `tests/multi-spec-external-ref/test-add-source-from-repo.sh` — sets up neighbor with a valid entry, runs `--from-repo <neighbor>` in fresh consumer, asserts entry byte-copied, subsequent `sync` reuses neighbor's clone (verified via T027 origin check, no re-clone)
- [ ] T058 [P] [US4] Add `tests/multi-spec-external-ref/test-auth-error-clarity.sh` — asserts structured diagnostic per FR-037 on unreachable producer (fixture uses invalid URL); asserts stderr text names repository URL AND remediation hint (SSH key / credential manager / network)
- [ ] T059 [P] [US4] Add `tests/multi-spec-external-ref/test-legacy-cache-compatibility.sh` — pre-populates `$XDG_CACHE_HOME/haex-hive/repos/<hash>/` with a Spec-004 fixture cache, runs full-flow with a legacy `role: "constitution"` entry in `.haex-hive.json`, asserts `spec-resolve resolve` reads bytes unchanged (SC-008) and `spec-resolve prefetch --dry-run` prints unchanged legacy `OK/MISSING` output

### Implementation for User Story 4

- [ ] T060 [P] [US4] Implement interactive prompts in `add-source` — sequential prompt flow per contracts/haex-init-add-source.cli.md §From-scratch mode; TTY detection; non-TTY without `--yes` refuses (exit 2); reuses validators T008-T011
- [ ] T061 [P] [US4] Implement `--from-repo <path>` mode in `add-source` — reads neighbor's `.haex-hive.json`, schema-validates (refuse if invalid per FR-031), enumerates `external-harness` entries, interactive selection, re-validates against current-consumer context (storage-name collision, duplicate-repository, updated field validations), applies via T022
- [ ] T062 [US4] Implement `--replace` semantics in `add-source` — on duplicate `repository`, refuses without `--replace`; with `--replace`, updates in-place; storage-name-URL invariant re-verified across all entries
- [ ] T063 [US4] Implement post-`add-source` `sync` trigger — subprocess-invokes `haex-init sync` from same argv[0], propagates `--yes`; `sync` exit code becomes `add-source` exit code; `--no-sync` short-circuits per FR-032

**Checkpoint**: US4 fully functional. All four user stories independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cross-platform smoke validation, final green-run.

- [ ] T064 [P] Add operator documentation `docs/multi-spec-external-ref.md` — mirrors `docs/haex-init.md` structure: install (via `haex-init` extension), command surface (`sync`, `add-source`), exit codes, common troubleshooting from quickstart.md, cross-references to Spec 004 + Spec 005 docs
- [ ] T065 [P] Add cross-platform smoke-validation document `specs/006-multi-spec-external-refs/.validation-runs/2026-XX-XX-cross-platform-smoke.md` — templated for macOS + WSL2 smoke runs (Path A + Path C from quickstart), matches the Spec 005 validation-runs pattern
- [ ] T066 [P] Extend `spec-resolve status` in `.specify/scripts/spec-resolve` — summarises `.haex-hive.local.json` freshness (SHA of source config vs `generated_from_config` field), lists state-area producer clones with `origin.url` verification status
- [ ] T067 [P] Extend `spec-resolve prefetch --dry-run` in `.specify/scripts/spec-resolve` — appends planned `external-harness` items in deterministic order after legacy `OK`/`MISSING` lines (Research §5); does not migrate legacy cache (FR-034, SC-008)
- [ ] T068 Run `tests/multi-spec-external-ref/run-all.sh` green end-to-end on Linux — records timing in `specs/006-multi-spec-external-refs/.validation-runs/2026-XX-XX-full-suite.md`, asserts SC-010 (under 2 minutes)
- [ ] T069 Final hygiene pass — validate every FR from spec.md has at least one implementing task; validate every FR has at least one test task; validate every SC has an implementing + verifying task pair; update `spec.md` if any FR turned out to be untestable during implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 completion. BLOCKS all user stories.
- **Phase 3 (US1)**: Depends on Phase 2. Minimum viable delivery — MVP checkpoint.
- **Phase 4 (US2)**: Depends on Phase 3's T039 (basic add-source) and T024/T035 (ExpansionPlan/regenerator). Extends the same file; **not fully parallel** with US1 but the tests (T040-T043) can be authored in parallel with US1 implementation.
- **Phase 5 (US3)**: Depends on Phase 3 (has synced state to bump) + T024/T035. Rename detection extends T024's preflight.
- **Phase 6 (US4)**: Depends on Phase 3's T039 (add-source foundation). US4's interactive + `--from-repo` implementations extend that same code path.
- **Phase 7 (Polish)**: Depends on Phases 3-6 all being complete.

### User Story Dependencies

- **US1**: independent (only Phase 2 required)
- **US2**: extends US1 code paths (add-source flags + expansion in ExpansionPlan); tests independent
- **US3**: extends US1 code paths (preflight rename detection, dry-run); tests independent
- **US4**: extends US1's add-source (from-scratch flag-only becomes interactive + `--from-repo`); tests independent

### Within Each User Story

- Tests SHOULD be written first per project convention. Not TDD-rigid — tests may be authored in parallel with implementation but MUST fail before the corresponding implementation lands.
- Within US1: T032 → T033 → T034 → T035 sequential (same file, extending same code paths); T036, T037, T038 semi-independent (touch different logical areas); T039 depends on T022 (Phase 2) + T024
- Within US2: T044 || T045 parallel (different helper functions); T046 depends on both; T047, T048 sequential after
- Within US3: T052 → T053 → T054 → T055 mostly sequential in same file
- Within US4: T060 || T061 (different modes); T062 depends on both; T063 stitches

### Parallel Opportunities

- Phase 1: T002 + T003 + T005 (T004 depends on T002-T003 for helpers)
- Phase 2: T006 + T007 parallel; T008-T012 parallel among each other (single-file additions but different functions — merge conflict risk minimal); T015-T016 sequential; T017 + T018 + T019 parallel; T025-T027 parallel among themselves
- Phase 3: T028-T031 parallel test authoring; implementation T032-T038 mostly sequential (same file); T039 blocks on Phase 2's T022 + T024
- Phase 4-6 tests all `[P]` parallel among themselves
- **Cross-phase**: Phase 4 tests + Phase 5 tests + Phase 6 tests can be authored in parallel with US1 implementation as long as fixture producer (T003) is ready

---

## Parallel Example: User Story 1

```bash
# Author all US1 tests in parallel (different files, no dependencies among themselves):
Task: "Add tests/multi-spec-external-ref/test-fresh-external-harness.sh"
Task: "Add tests/multi-spec-external-ref/test-constitution-order.sh"
Task: "Add tests/multi-spec-external-ref/test-file-permissions.sh"
Task: "Add tests/multi-spec-external-ref/test-sync-exit-codes.sh"

# Phase 3 implementation is largely sequential on the same file
# (.specify/scripts/haex-init), so T032-T039 serialise.
# Session-start template extension (T038) touches a different file
# and can proceed in parallel with T032-T037.
```

---

## Implementation Strategy

### MVP scope

**Phases 1 + 2 + 3** alone = MVP. If the operator ships nothing else, they have:

- Test infrastructure fixture producer + shared helpers
- Schema extension + shared validators + state-area + git wrappers + atomic file ops + lock module + basic error emitter
- `haex-init add-source` in non-interactive flag-only mode (enough to add a constitution-only entry)
- `haex-init sync` for constitution-only case, full extract flow with atomicity guarantees
- Session-start snippet reads `.haex-hive.local.json`

That closes the load-bearing claim of "secure-web-frontend inherits secana-specs' Constitution end-to-end" — the real Phase 1 acceptance test.

### Incremental delivery

1. Phases 1–3 → MVP works. Commit checkpoint per phase, PR after each user story concludes.
2. Phase 4 (US2) → auto_include + additional_include live. Consumer can inherit arbitrary content.
3. Phase 5 (US3) → SHA-bump update flow + rename detection + `--dry-run`.
4. Phase 6 (US4) → `add-source` interactive + `--from-repo` bootstrap. DX-critical for onboarding second consumer.
5. Phase 7 (Polish) → operator docs + cross-platform smoke + final green run.
6. Merge feature branch to `main`. Advance design roadmap Phase 1 to "cross-repo multi-spec external-ref in daily use" (extension of the current 2026-08-28 status).

### Solo strategy (this project's expected mode)

You are the only operator. Sequential execution phase by phase. The `[P]` markers indicate where solo-serial can be re-ordered without dependency risk — useful for interleaving test authoring (T028+, T040+, T049+, T056+) with implementation work if you need a change of gears.

Commits per phase-checkpoint are recommended so a failure in a later phase can be diagnosed against a known-good earlier state. Constitution v1.2.0 requires PR flow — commit locally on feature branch, push, PR per phase or per checkpoint (operator choice).

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Every code change should trace to a specific FR in spec.md. If a task's diff doesn't map to at least one FR, either the task is out of scope or an FR is missing.
- Commits after each Phase are recommended so a failure in a later phase can be diagnosed against a known-good earlier state.
- Do not mark Phase 7 tasks complete until every earlier task's tests pass in T068's `run-all.sh` output.
- Non-Goals from spec.md MUST remain out of scope through Phase 7: no live catalog, no spec creation from consumer, no speckit template overriding, no `--fetch-latest`, no cache eviction, no worktree-per-SHA. If a task starts creeping toward one of these, split it into a separate spec-scoped task instead.
- Backwards compat with Spec 004 (FR-033, FR-034, SC-008) MUST hold at every checkpoint: a consumer whose `harness_sources[]` contains only Spec-004-shaped entries must behave exactly as before across all Phase 3-6 changes.
