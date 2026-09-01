# Tasks: Install Transaction Contract for `haex install`

**Input**: Design documents from `/specs/008-install-transaction/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included. Spec 008 mandates a conformance suite covering FR-013–FR-017 as a landing requirement, and every artefact under `contracts/` requires a schema-level contract test — so both contract and conformance tests are part of the task list.

**Checkbox freshness is load-bearing.** When a task is completed, tick its checkbox in the same commit as the task's output — or at the latest in the next commit, before starting the next task. Handoff queries ("what was just done, what remains, what is the next step?") read this file's checkbox state as the primary state document. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4). Setup, Foundational, and Polish tasks carry no story label.
- Include exact file paths in descriptions.

## Path Conventions

Single-project Python CLI (Spec 007 baseline). Source lives under [src/haex_hive/](../../src/haex_hive/); tests under [tests/](../../tests/). Spec 008 adds a new `install/` subpackage plus a `tests/install/` subtree; no restructure elsewhere. See [plan.md §Project Structure](./plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Wire the new install subpackage and its test tree into the existing tree so that later phases can land into pre-created skeletons without one-off scaffolding.

- [x] T001 Create install subpackage skeleton at [src/haex_hive/install/__init__.py](../../src/haex_hive/install/__init__.py) with empty module docstring; add sibling stub files `plan.py`, `commit_snapshot.py`, `stage.py`, `overlay.py`, `visibility.py`, `lock.py`, `journal.py`, `delta.py`, `digest.py`, `errors.py` — each with only a module docstring — so that later phases only import-and-implement.
- [x] T002 Create install test tree directories: `tests/install/`, `tests/install/contract/`, `tests/install/integration/`, `tests/install/conformance/`, `tests/install/unit/`. **Deviation from original wording**: the tasks doc asked for an `__init__.py` in each; the repo convention (verified against `tests/contract/`, `tests/unit/`, `tests/integration/`) is to omit them because the presence of `tests/install/*/__init__.py` makes pytest compute the module qualified name as `install.contract.test_*`, which collides with the real `haex_hive.install` package at collection time. The `__init__.py` files were removed in the T008–T011 batch when the first real test modules landed and triggered the collision.
- [x] T003 Register the `install` subcommand in [src/haex_hive/cli/main.py](../../src/haex_hive/cli/main.py) and add a handler stub at [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py) that prints a `not-yet-implemented` sentinel and exits non-zero — later phases replace the body.
- [x] T004 Extend [src/haex_hive/util/exit_codes.py](../../src/haex_hive/util/exit_codes.py) with the exit codes named in [contracts/haex-install.cli.md](./contracts/haex-install.cli.md): `install-lock-busy` (9) and `incomplete-transaction` (7). Reuse existing codes for input/IO/validation/system/post-write/concealment/plaintext-secret refusals — verify the CLI contract's exit-code table matches the existing enum before landing.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shape all cross-story primitives (schemas, dataclasses, error types, journal + lock + digest helpers, extended transaction envelope). Every user story depends on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Schemas and their contract tests

- [x] T005 [P] Vendor [contracts/install-lock.v2.schema.json](./contracts/install-lock.v2.schema.json) into [src/haex_hive/schema/data/install-lock.v2.schema.json](../../src/haex_hive/schema/data/install-lock.v2.schema.json) and register it in the existing [schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS` set alongside the existing Spec 007 loaders. Path/naming follows the repo's actual kebab-case `schema/data/*.schema.json` convention rather than the task-doc's original `schema/install_lock_v2.schema.json` suggestion.
- [x] T006 [P] Vendor [contracts/install-journal.v1.schema.json](./contracts/install-journal.v1.schema.json) into [src/haex_hive/schema/data/install-journal.v1.schema.json](../../src/haex_hive/schema/data/install-journal.v1.schema.json) and register it in the existing [schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS` set.
- [x] T007 [P] Vendor [contracts/visibility-marker.v1.schema.json](./contracts/visibility-marker.v1.schema.json) into [src/haex_hive/schema/data/visibility-marker.v1.schema.json](../../src/haex_hive/schema/data/visibility-marker.v1.schema.json) and register it in the existing [schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS` set.
- [x] T008 [P] Contract test for install-lock v2 in [tests/install/contract/test_install_lock_schema.py](../../tests/install/contract/test_install_lock_schema.py): load the schema, assert a minimal Spec-008 constitution-only shape (explicit v2 fields, no install atoms) validates, assert a full Spec-008 shape validates, and cover negative cases (missing `atoms[i].source`, padded-base64 digest, path-ownership `previous` shape).
- [x] T009 [P] Contract test for install-journal v1 in [tests/install/contract/test_journal_schema.py](../../tests/install/contract/test_journal_schema.py): validate one entry per `entry_type` enum value, assert a well-formed but mis-chained `tail_hash` still passes schema (chain integrity is runtime), and cover negative cases (unknown entry_type, padded digest, missing required field, unknown top-level field).
- [x] T010 [P] Contract test for visibility-marker v1 in [tests/install/contract/test_visibility_marker_schema.py](../../tests/install/contract/test_visibility_marker_schema.py): validate `.haex-hive/`-only MVP and `.haex-hive/` + `.claude/` mixed-overlay shapes; assert both digest fields require the base64url-nopad `sha256-<43 chars>` shape; cover unknown-field rejection at root and per-root, empty `participating_roots`, bad `generation_id`.
- [x] T011 [P] Contract test for owner-token format in [tests/install/contract/test_owner_token_format.py](../../tests/install/contract/test_owner_token_format.py): round-trip parse/serialise, hostname sanitisation (`[A-Za-z0-9.-]` only, 64-char cap, `unknown` fallback), 128-byte length ceiling, negative cases (wrong field count, uppercase UUID). Skipped at module level until T013 lands `OwnerToken` in [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py); the skip guard drops automatically once the class exists.

### Dataclasses and small helpers

- [x] T012 [P] Implement `PlanStep` (with `StepType` `Literal` of all 6 values), `PlanSnapshot`, and `CommitSnapshot` frozen dataclasses in [src/haex_hive/install/plan.py](../../src/haex_hive/install/plan.py). `PlanSnapshot.seal(...)` computes `plan_snapshot_digest` from canonical UTF-8 JSON of all fields except `sealed_at_ns` — determinism and drift-detection verified via ad-hoc round-trip. `__post_init__` rejects non-monotonic step ids and empty step lists. `CommitSnapshot.matches(plan)` returns True iff all three digest fields agree.
- [x] T013 [P] Implement `OwnerToken` dataclass with parse/serialise + hostname validation in [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py) per research §R4. `OwnerToken.emit()` sanitises the hostname per contract (drops non-`[A-Za-z0-9.-]` chars, truncates to 64, falls back to `"unknown"`); serialisation refuses tokens over the 128-byte cap. Unblocks T011 (`test_owner_token_format.py`).
- [x] T014 [P] Implement `JournalEntry` (frozen dataclass), `EntryType` `Literal` covering all 12 enum values, `canonical_json`, `compute_tail_hash`, `make_entry`, `append_entry`, `read_entries`, and `verify_chain` in [src/haex_hive/install/journal.py](../../src/haex_hive/install/journal.py) per research §R7. Write discipline is `append → fsync(fd) → fsync(parent_dir) → return`. `verify_chain` re-derives each entry's tail hash from `canonical_json(entry - tail_hash) + b"\n" + prev_tail_hash.encode("ascii")` and refuses on mismatch or non-monotonic `entry_id`.
- [x] T015 [P] Implement `VisibilityMarker` and `RootDigest` frozen dataclasses + `to_dict` / `to_json_bytes` (via `json_deterministic.dumps`) in [src/haex_hive/install/visibility.py](../../src/haex_hive/install/visibility.py) per data-model.md. `VisibilityMarker.__post_init__` rejects empty and duplicate `participating_roots`; `RootDigest.overlay_paths=None` for haex-owned roots, exhaustive allowlist for mixed-ownership roots.
- [x] T016 [P] Implement `InstallLock` v2 model + serialiser in [src/haex_hive/model/install_lock.py](../../src/haex_hive/model/install_lock.py). Promoted `atoms`, `participating_roots`, `visibility_marker`, and `ownership` to first-class fields per research §R9 as new frozen dataclasses (`AtomInstallRecord`, `RootRecord`, `VisibilityMarkerRef`, `OwnershipSet`, `PathOwnershipRecord`, `OwnerResource`, `PreviousPathState`). `InstallLock` is now `@dataclass(frozen=True)` and applies the PR #32 review pattern: `Mapping[str, Any]` for `unknown_top_level` normalised via `freeze_json` in `__post_init__`, tuple normalisation for `atoms`/`participating_roots`, and constructor validation for duplicate root names and duplicate ownership paths. `unknown_top_level` still preserves genuinely-unknown fields for future schema evolution, but no longer carries `visibility_marker`. Under pre-user policy a Spec 007-vintage record refuses at schema validation. `constitution/assemble.py` now writes `visibility_marker` and `participating_roots` as first-class fields (removed the `unknown_top_level["visibility_marker"] = marker_ref` working-buffer pattern).
- [x] T017 [P] Implement `HaexInstallError` and subclasses (`InstallLockBusy` → `INSTALL_LOCK_BUSY` 9, `IncompleteTransaction` → `INCOMPLETE_TRANSACTION` 7, `CommitSnapshotMismatch` → `VALIDATION_REFUSE` 4, `OverlayUnsupported` → `SYSTEM_REFUSE` 5, `SealMismatch` → `POST_WRITE_VALIDATION` 6) in [src/haex_hive/install/errors.py](../../src/haex_hive/install/errors.py). Every subclass carries a diagnostic key matching the CLI contract's exit-code table.
- [x] T018 [P] Implement `compute_root_digest(root_dir, root_name, overlay_paths=None)` in [src/haex_hive/install/digest.py](../../src/haex_hive/install/digest.py) per research §R5. Byte-sorted enumeration, `<repo-relative-path>:<hex>\n` concatenation, SHA-256 → base64url-nopad. `.haex-hive/` (`overlay_paths=None`) walks the tree and excludes `visibility.json` + `install.lock`; mixed-ownership roots receive an explicit allowlist and never enumerate siblings.

### Extended shared IO

- [ ] T019 Extend [src/haex_hive/io/writer_lock.py](../../src/haex_hive/io/writer_lock.py) with shared device-local path helpers and exclusive-with-owner-metadata locking (`fcntl.flock(LOCK_EX | LOCK_NB)` on POSIX, Win32 `LockFileEx` with `LOCKFILE_EXCLUSIVE_LOCK` on Windows) that reads/writes the `install.mutex` layout defined in data-model.md, including in-place wall-clock heartbeat updates. Derive the canonical project identity from the git remote or `.harness-id`, hash it to the filesystem-safe `<repo-key>`, derive a device-local `<checkout-key>` from the resolved checkout path, and store the full identity in `repo-identity.v1.json`. Existing constitution-writer callsites use only these new paths. New callers pass an `OwnerToken` (from T013) at acquisition. Depends on T013 and T017.
- [ ] T020 Generalise [src/haex_hive/io/transaction.py](../../src/haex_hive/io/transaction.py) to accept a multi-participant plan (list of per-file staged writes) instead of a single-file assemble; use the shared device-local journal path and recover the checkout-scoped journal before opening a new transaction. The constitution-assemble callsite remains a single-participant special case per research §R9. Depends on T014 and T018.

The device-local state root owns the mutex, identity record, journal, and other
durable transaction metadata. Staging and rollback/pre-image trees remain
same-filesystem siblings of their checkout targets as required by FR-003;
they are transaction-owned temporary content, not alternate state-root
artifacts, and are removed by journaled cleanup after publication.

**Checkpoint**: Foundation ready — the install subpackage compiles, schemas validate against their fixtures, and constitution assemble still passes its existing tests. User story implementation can now begin.

---

## Phase 3: User Story 1 — Happy-path install (Priority: P1) 🎯 MVP

**Goal**: Running `haex install` on a satellite with a valid `.haex-hive.json` publishes a byte-perfect new generation: `.haex-hive/constitution.md`, `.haex-hive/install.lock`, and `.haex-hive/visibility.json` all agree; re-running is a no-op.

**Independent Test**: Per [spec.md §US1 Independent Test](./spec.md) — on a satellite adopting two atoms from `github.com/haexmas/haex-hive`, run `haex install`; verify constitution assembly, install.lock digests, marker digests, and a second no-op run.

### Tests for User Story 1

- [ ] T021 [P] [US1] Integration test at [tests/install/integration/test_happy_path.py](../../tests/install/integration/test_happy_path.py): using a fixture repo under `tests/install/fixtures/` (create as part of this task) with two atoms, assert (a) constitution.md content, (b) install.lock records both atoms' content_integrity, (c) visibility.json names a fresh generation ID and lists `.haex-hive/`'s digest matching the on-disk digest, (d) recomputed per-root digest equals the marker's.
- [ ] T022 [P] [US1] Integration test at [tests/install/integration/test_idempotent_no_op.py](../../tests/install/integration/test_idempotent_no_op.py): install once, capture `stat` of every output; install again; assert zero mtime changes, zero byte differences, and stdout reports "no changes" (SC-003).
- [ ] T023 [P] [US1] Unit test at [tests/install/unit/test_plan_snapshot_digests.py](../../tests/install/unit/test_plan_snapshot_digests.py): PlanSnapshot seals deterministic digests for `.haex-hive.json`, publisher manifests, and atom manifests; a byte-change in any input changes the plan_snapshot_digest.

### Implementation for User Story 1

- [ ] T024 [P] [US1] Implement plan-build in [src/haex_hive/install/plan.py](../../src/haex_hive/install/plan.py): read `.haex-hive.json` (reuse Spec 007's `atoms[]` loader), resolve atoms against publisher clones under `$HAEX_HIVE_STATE/repos/`, seal a PlanSnapshot with all input digests and the planned versioned ownership set, and emit an ordered PlanStep list (`stage_file` per contributed file, `delete_orphan` per removed owned path, one `seal_install_lock`, one `publish_marker`). Depends on T012, T018.
- [ ] T025 [P] [US1] Implement commit-snapshot re-read + digest match in [src/haex_hive/install/commit_snapshot.py](../../src/haex_hive/install/commit_snapshot.py) per FR-006: re-open the same input files, hash again, compare with PlanSnapshot, seal the matching bytes into an immutable transaction-owned input snapshot, and ensure supported writers cannot acquire the shared input fence before the first swap; on mismatch raise `CommitSnapshotMismatch` (T017). Depends on T012.
- [ ] T026 [P] [US1] Implement staged-root writer in [src/haex_hive/install/stage.py](../../src/haex_hive/install/stage.py): for each `stage_file` step, write bytes into `<root>.staging.<gen>/` sibling of the target root, fsync file + parent, journal `stage_file` entry, then `os.replace()` into the canonical path. Depends on T014, T020.
- [ ] T027 [US1] Implement the time-based generation ID (`g_<UTC-ISO8601-basic>_<sha256-prefix4>`) helper in [src/haex_hive/install/plan.py](../../src/haex_hive/install/plan.py) per research §R8. The timestamp is the UTC allocation time, the hash prefix identifies the sealed plan, and allocation MUST advance past an equal existing generation ID so IDs are unique and lexicographically time-ordered. Depends on T012 and is serialized with T024 because both modify `plan.py`.
- [ ] T028 [US1] Implement pipeline orchestration in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py) (replacing the T003 stub): acquire exclusive lock (T019) → recover the checkout-scoped journal before planning (T042 when available) → build plan (T024) → verify and seal commit inputs (T025) → resolve/hydrate from the sealed snapshot → stage all outputs (T026), including ownership-based deletes → seal install.lock via T020 → publish visibility.json marker (T030) → journal and perform idempotent cleanup. Report "no changes" when the pre-install marker's `install_lock_content_integrity` equals a dry-run recomputation. Depends on T019, T020, T024, T025, T026, T027, T029, T030, and T042 for recovery-aware constitution routing.
- [ ] T029 [US1] Implement `seal_install_lock` step in [src/haex_hive/install/stage.py](../../src/haex_hive/install/stage.py) or in [src/haex_hive/model/install_lock.py](../../src/haex_hive/model/install_lock.py): compose the InstallLock v2 record from sealed staged bytes + PlanSnapshot outputs, journal `install_lock_sealed`, and atomic-write it as the last non-marker file per FR-009. Depends on T016, T018.
- [ ] T030 [US1] Implement visibility-marker publish step in [src/haex_hive/install/visibility.py](../../src/haex_hive/install/visibility.py): compute per-root digests over the just-sealed on-disk bytes (T018), assemble `VisibilityMarker`, journal `commit_marker_published`, `os.replace()` the marker into `.haex-hive/visibility.json`. Depends on T015, T018.
- [ ] T031 [US1] Route existing `haex constitution assemble` through the install pipeline as a constitution-only plan filter in [src/haex_hive/cli/constitution.py](../../src/haex_hive/cli/constitution.py) per research §R9: the CLI shortcut still exists but internally invokes the T028 pipeline with a scope filter, uses the shared device-local lock/journal helpers, and recovers only the checkout-scoped journal. Verify existing constitution unit + integration tests pass unchanged. Depends on T028.

**Checkpoint**: User Story 1 is fully functional. Running `haex install` on a fresh checkout publishes a valid generation; a second run is a no-op. Constitution assemble still passes.

---

## Phase 4: User Story 2 — Concurrent installs safely serialised (Priority: P2)

**Goal**: Two concurrent `haex install` invocations against the same checkout never both succeed; the loser exits with owner detail (PID, hostname, start time) per FR-001. `haex verify` shares reads; `haex verify --recover` takes the same exclusive lock.

**Independent Test**: Per [spec.md §US2 Independent Test](./spec.md) — script two `haex install` invocations starting simultaneously; assert exactly one succeeds and the other names the winner.

### Tests for User Story 2

- [ ] T032 [P] [US2] Unit test at [tests/install/unit/test_fenced_lease.py](../../tests/install/unit/test_fenced_lease.py): heartbeat thread refreshes the UTC `heartbeat_at` every 5s (fake monotonic scheduler); TTL of 60s plus the 5s safety margin is honoured; a live OS lock blocks reclaim regardless of age; revalidation-before-reclaim aborts when the owner token or heartbeat changes between the two reads per research §R4.
- [ ] T033 [P] [US2] Conformance test at [tests/install/conformance/test_concurrent_installs.py](../../tests/install/conformance/test_concurrent_installs.py) (FR-013): use `multiprocessing.Process` to fire two `haex install` invocations simultaneously; assert exactly one exit code 0 and one exit code 9 with the winner's PID/hostname/start-time in stderr (SC-002).

### Implementation for User Story 2

- [ ] T034 [US2] Implement fenced-lease heartbeat thread + revalidation-before-reclaim in [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py) per research §R4: 5s cadence, 60s TTL, 5s safety margin, UTC expiry, same exclusive OS-lock fence, and revalidation ordering (read stale → exclusive-re-read stale-and-unchanged → reclaim). Uses `time.monotonic_ns()` only for scheduling and token diagnostics. Depends on T013, T019.
- [ ] T035 [US2] Add shared-read (`fcntl.flock(LOCK_SH | LOCK_NB)` on POSIX / Win32 `LockFileEx` without `LOCKFILE_EXCLUSIVE_LOCK` on Windows) support in [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py) so `--verify-only` acquires shared while `install`/`verify --recover` acquire exclusive per FR-001. Add a Windows concurrency test proving two readers coexist while a writer is excluded until both release. Depends on T019.
- [ ] T036 [US2] Implement busy-lock diagnostic formatter in [src/haex_hive/install/errors.py](../../src/haex_hive/install/errors.py): on `InstallLockBusy`, format the operator-facing message from the mutex file's contents per [contracts/haex-install.cli.md](./contracts/haex-install.cli.md) exit-code table. Depends on T017, T034.
- [ ] T037 [US2] Add `--verify-only` flag handling in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py): shared-read lock, load marker, recompute per-root digests, exit 0 on match or exit 6 on mismatch. Depends on T028, T035.

**Checkpoint**: Concurrent installs are safely serialised; the loser diagnostic names the winner; `haex install --verify-only` reads under a shared lock.

---

## Phase 5: User Story 3 — Crash recovery preserves consistency (Priority: P2)

**Goal**: A crash at any journal state either completes the interrupted install to a valid new generation or rolls back to the previous marker-consistent generation. Unowned files under `.claude/`/`.codex/` survive recovery byte-identically.

**Independent Test**: Per [spec.md §US3 Independent Test](./spec.md) — scripted-kill at each of the six journal states in FR-014 (after lock, staging, `install.lock`, marker, `cleanup_started`, and `cleanup_completed`); after each, run `haex verify --recover` and assert one of the two allowed outcomes, preserving a verified published generation for the two post-marker cleanup states.

### Tests for User Story 3

- [ ] T038 [P] [US3] Unit test at [tests/install/unit/test_journal_replay.py](../../tests/install/unit/test_journal_replay.py): tail-hash chain integrity check, replay path selection per data-model.md state machine (after `commit_marker_published` → cleanup; after `install_lock_sealed` → publish marker; earlier → rollback).
- [ ] T039 [P] [US3] Conformance test at [tests/install/conformance/test_crash_matrix.py](../../tests/install/conformance/test_crash_matrix.py) (FR-014): parametrise over the crash points (after lock, after staging, after install.lock, after marker, after `cleanup_started`, and after `cleanup_completed`); each case runs an install, injects `SystemExit(137)` at the target state, then runs `haex verify --recover` and asserts the outcome matches one of the two allowed per FR-011 (SC-001), preserving the published generation for the two post-marker cleanup points.
- [ ] T040 [P] [US3] Conformance test at [tests/install/conformance/test_mid_install_mutation.py](../../tests/install/conformance/test_mid_install_mutation.py) (FR-015): a background thread rewrites `.haex-hive.json` between PlanSnapshot seal and commit-snapshot re-hash; assert the install aborts with `CommitSnapshotMismatch` and no output is published (SC-004).
- [ ] T041 [P] [US3] Conformance test at [tests/install/conformance/test_unowned_files_survive.py](../../tests/install/conformance/test_unowned_files_survive.py) (FR-017): pre-populate `.claude/` and `.codex/` with unowned files (not in `overlay_paths`); run install, crash mid-way, recover; assert those files are byte-identical throughout (SC-006).

### Implementation for User Story 3

- [ ] T042 [US3] Implement journal replay/rollback state machine in [src/haex_hive/install/journal.py](../../src/haex_hive/install/journal.py) per data-model.md: verify tail-hash chain, walk entries, dispatch to complete-forward or roll-back per last consistent state. Depends on T014.
- [ ] T043 [US3] Implement rollback + prior-generation restore in [src/haex_hive/install/stage.py](../../src/haex_hive/install/stage.py): for each `stage_file` entry with a completed replace, restore the pre-image (kept under the same-filesystem `<root>.rollback.<prev-gen>/` sibling); on marker roll-back, restore prior `visibility.json`. These temporary trees are not durable state-root artifacts and are removed by journaled cleanup. Depends on T026, T042.
- [ ] T044 [US3] Add `--recover` handling to `haex verify` in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py): acquires exclusive lock (T019), replays or rolls back via T042/T043, reports "recovered generation `<gen>`" (either completed or rolled back), exit 0. Depends on T028, T042.
- [ ] T045 [US3] Implement stale-staging cleanup at the start of every successful exclusive-lock acquisition in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py) or [src/haex_hive/install/stage.py](../../src/haex_hive/install/stage.py): discover leftover `<root>.staging.<gen>/` and `<root>.rollback.<prev-gen>/` from a pre-lock crash, `rmtree` those not referenced by a journal-in-flight. Depends on T042.

**Checkpoint**: Every crash point in FR-014 resolves to complete-new or rollback-to-previous. Unowned files survive. `haex verify --recover` is functional.

---

## Phase 6: User Story 4 — Removing an atom cleans up in-transaction (Priority: P3)

**Goal**: Removing an atom from `.haex-hive.json` causes the next `haex install` to delete its contributed files atomically with any new writes. Interrupted deletes roll back cleanly per FR-011.

**Independent Test**: Per [spec.md §US4 Independent Test](./spec.md) — install two atoms, drop one, re-install, verify orphans are gone; interrupt mid-delete, recover, verify no partial state.

### Tests for User Story 4

- [ ] T046 [P] [US4] Integration test at [tests/install/integration/test_delete_orphans.py](../../tests/install/integration/test_delete_orphans.py): install two atoms, drop one, re-install, assert removed atom's files are gone from every participating root and install.lock reflects the reduced atom set.
- [ ] T047 [P] [US4] Unit test at [tests/install/unit/test_delta_computation.py](../../tests/install/unit/test_delta_computation.py): given a previous install.lock and a new PlanSnapshot, compute the delta (adds, keeps, deletes); assert the deletes cover exactly the files owned by removed atoms and no others.
- [ ] T048 [P] [US4] Conformance test at [tests/install/conformance/test_partial_delete_rollback.py](../../tests/install/conformance/test_partial_delete_rollback.py) (FR-016): inject `SystemExit(137)` during a delete-orphans install after some deletes have been journalled but before install.lock is sealed; recover; assert either all deletes applied and new generation published, or all reverted and the old generation intact.

### Implementation for User Story 4

- [ ] T049 [US4] Implement delta computation in [src/haex_hive/install/delta.py](../../src/haex_hive/install/delta.py): compare previous install.lock's versioned `ownership.paths` with the new plan's ownership set; emit `delete_orphan` PlanSteps for each removed owned path while preserving unowned mixed-root entries. Include prior-generation metadata and journal pre-image references for rollback. Depends on T012, T016.
- [ ] T050 [US4] Extend plan-build in [src/haex_hive/install/plan.py](../../src/haex_hive/install/plan.py) to invoke the T049 delta and interleave `delete_orphan` steps with `stage_file` steps in the ordered PlanStep list (deletes before install.lock seal). Depends on T024, T049.
- [ ] T051 [US4] Extend staged writer in [src/haex_hive/install/stage.py](../../src/haex_hive/install/stage.py) to handle `delete_orphan` steps atomically-with-writes: move the target to `<root>.rollback.<prev-gen>/` (preserving the pre-image), journal the entry, then confirm the move. Rollback restores from the same rollback tree. Depends on T026, T043, T050.

**Checkpoint**: Delete-orphans installs are atomic-and-recoverable. All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T052 [P] Implement mixed-ownership overlay primitives in [src/haex_hive/install/overlay.py](../../src/haex_hive/install/overlay.py) per research §R3: POSIX `os.symlink()`, Windows directory junction via `CreateSymbolicLinkW(SYMBOLIC_LINK_FLAG_DIRECTORY)` or `mklink /J`, file-scoped-on-Windows-non-DevMode refusal with `OverlayUnsupported`. Add unit test at [tests/install/unit/test_overlay_primitives.py](../../tests/install/unit/test_overlay_primitives.py) exercising the platform-selection matrix under a `platform` monkeypatch. Not needed on the US1 hot path (`.haex-hive/` is haex-owned) but required for FR-003 and SC-005 conformance ahead of Spec 010 landing.
- [ ] T053 [P] Refresh public surface in [src/haex_hive/install/__init__.py](../../src/haex_hive/install/__init__.py): re-export the small set of entry points other modules import (pipeline entry, error classes, `OwnerToken`); keep everything else module-private.
- [ ] T054 Run [specs/008-install-transaction/quickstart.md](./quickstart.md) end-to-end on a fresh clone with `$HAEX_HIVE_STATE` pointing at a scratch dir: exercise steps 1–7 (first install, no-op re-install, `--verify-only`, concurrent-refusal, `--recover` after scripted kill, delete-orphan install, reader consistency helper). Record SC-001..SC-007 verification outcomes in the phase closing commit message.
- [ ] T055 Full pytest run (`pytest tests/install/` + full suite for regression) and prune any transient imports the install subpackage no longer needs. No code-style refactor beyond removing dead symbols the story tasks left behind.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. Note that T019 depends on T013+T017, and T020 depends on T014+T018; the rest of the phase runs in parallel.
- **User Story 1 (Phase 3)**: Depends on Foundational. MVP boundary.
- **User Story 2 (Phase 4)**: Depends on Foundational; touches [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py) and [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py) — parallel with US3/US4 only if editors coordinate on those two files.
- **User Story 3 (Phase 5)**: Depends on Foundational AND on US1's pipeline (T028) since `--recover` and stale-staging cleanup live in the same handler. In practice US3 starts after US1.
- **User Story 4 (Phase 6)**: Depends on Foundational AND on US3's rollback infrastructure (T043) since the atomic delete uses the same rollback tree.
- **Polish (Phase 7)**: Depends on the desired user stories being complete. T052 (overlay primitives) is safe to land earlier if `.claude`/`.codex` overlay tests are demanded by Spec 010 landing sooner.

### Within Each User Story

- Tests first — they must FAIL against the T003 stub before the story's implementation tasks land.
- Data model / small helpers before the pipeline integration task.
- Every task in a story references a single file where reasonable; parallelism is called out explicitly with [P].

### Parallel Opportunities

- Phase 2 schemas + contract tests + dataclasses + small helpers all run in parallel (T005–T018). Only T019 and T020 serialise on their listed dependencies.
- Within US1, T021/T022/T023 (tests) and T024/T025/T026/T027 (independent modules) all run in parallel. T028 gates on all of them.
- US3 conformance tests (T038–T041) all run in parallel — different files, no shared state.
- US4 tests (T046/T047/T048) all run in parallel.
- Polish T052 and T053 run in parallel.

---

## Parallel Example: Phase 2 Foundational

```bash
# Kick off schema vendoring + contract tests + dataclass modules together:
Task: "Vendor install-lock v2 schema into src/haex_hive/schema/"
Task: "Vendor install-journal v1 schema into src/haex_hive/schema/"
Task: "Vendor visibility-marker v1 schema into src/haex_hive/schema/"
Task: "Contract test tests/install/contract/test_install_lock_schema.py"
Task: "Contract test tests/install/contract/test_journal_schema.py"
Task: "Contract test tests/install/contract/test_visibility_marker_schema.py"
Task: "Contract test tests/install/contract/test_owner_token_format.py"
Task: "Dataclasses in src/haex_hive/install/plan.py"
Task: "OwnerToken in src/haex_hive/install/lock.py"
Task: "JournalEntry in src/haex_hive/install/journal.py"
Task: "VisibilityMarker in src/haex_hive/install/visibility.py"
Task: "InstallLock v2 model in src/haex_hive/model/install_lock.py"
Task: "Errors in src/haex_hive/install/errors.py"
Task: "Per-root digest in src/haex_hive/install/digest.py"

# T019 (writer_lock extension) and T020 (transaction extension) run after their deps land.
```

## Parallel Example: User Story 1

```bash
# Tests in parallel:
Task: "Integration test tests/install/integration/test_happy_path.py"
Task: "Integration test tests/install/integration/test_idempotent_no_op.py"
Task: "Unit test tests/install/unit/test_plan_snapshot_digests.py"

# Independent implementation modules in parallel:
Task: "Plan-build in src/haex_hive/install/plan.py"
Task: "Commit-snapshot re-hash in src/haex_hive/install/commit_snapshot.py"
Task: "Staged writer in src/haex_hive/install/stage.py"
Task: "Generation-ID helper in src/haex_hive/install/plan.py"

# Then T028 (pipeline orchestration), then T029/T030/T031 finalise.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: Run [quickstart.md](./quickstart.md) steps 1 and 2 (first install, idempotent re-install). Constitution assemble regression checked.
5. Deploy/demo if ready.

### Incremental Delivery

1. Setup + Foundational → shared machinery landed.
2. US1 → single-invocation happy path + no-op re-install (MVP).
3. US2 → concurrent-safe (SC-002).
4. US3 → crash-safe (SC-001, SC-006).
5. US4 → delete-orphans in-transaction (SC-005 scoping via T052).
6. Polish → overlay primitives + quickstart end-to-end validation covering SC-001..SC-007.

### Parallel Team Strategy

Foundational (Phase 2) is broad and its [P] tasks distribute well across engineers. After foundational lands:

- Engineer A drives US1 → US3 (they share the pipeline).
- Engineer B drives US2 (lock + `--verify-only` land into files that US1 has stubbed).
- Engineer C picks up overlay primitives (T052) and quickstart validation (T054) once US1+US3 are green.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps a task to its user story for traceability; Setup/Foundational/Polish tasks carry no label.
- Every user story is independently completable and testable per its **Independent Test** section in [spec.md](./spec.md).
- Verify tests fail against the T003 stub before implementing the story.
- Commit after each task or logical group; keep this file's checkboxes fresh — see [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).
- Stop at any checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts across concurrent tasks, cross-story dependencies that break independence.
