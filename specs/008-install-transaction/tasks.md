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

- [x] T001 Create install subpackage skeleton at [src/haex_hive/install/__init__.py](../../src/haex_hive/install/__init__.py) with empty module docstring; add the active helper stubs `overlay.py`, `visibility.py`, `lock.py`, `delta.py`, and `errors.py` — each with only a module docstring — so that later phases only import-and-implement. The retired plan, commit-snapshot, journal, stage, and digest modules are not part of the amended design.
- [x] T002 Create install test tree directories: `tests/install/`, `tests/install/contract/`, `tests/install/integration/`, `tests/install/conformance/`, `tests/install/unit/`. **Deviation from original wording**: the tasks doc asked for an `__init__.py` in each; the repo convention (verified against `tests/contract/`, `tests/unit/`, `tests/integration/`) is to omit them because the presence of `tests/install/*/__init__.py` makes pytest compute the module qualified name as `install.contract.test_*`, which collides with the real `haex_hive.install` package at collection time. The `__init__.py` files were removed in the T008–T011 batch when the first real test modules landed and triggered the collision.
- [x] T003 Register the `install` subcommand in [src/haex_hive/cli/main.py](../../src/haex_hive/cli/main.py) and add a handler stub at [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py) that prints a `not-yet-implemented` sentinel and exits non-zero — later phases replace the body.
- [x] T004 Extend [src/haex_hive/util/exit_codes.py](../../src/haex_hive/util/exit_codes.py) with the exit codes named in [contracts/haex-install.cli.md](./contracts/haex-install.cli.md): `install-lock-busy` (9) and `incomplete-transaction` (7). Reuse existing codes for input/IO/validation/system/post-write/concealment/plaintext-secret refusals — verify the CLI contract's exit-code table matches the existing enum before landing.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shape all cross-story primitives (schemas, dataclasses, error types, in-flight recovery and lock helpers, and the extended transaction envelope). Every user story depends on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Schemas and their contract tests

- [x] T005 [P] Vendor [contracts/install-lock.v2.schema.json](./contracts/install-lock.v2.schema.json) into [src/haex_hive/schema/data/install-lock.v2.schema.json](../../src/haex_hive/schema/data/install-lock.v2.schema.json) and register it in the existing [schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS` set alongside the existing Spec 007 loaders. Path/naming follows the repo's actual kebab-case `schema/data/*.schema.json` convention rather than the task-doc's original `schema/install_lock_v2.schema.json` suggestion.
- [x] ~~T006~~ [P] ~~Vendor `contracts/install-journal.v1.schema.json` into `src/haex_hive/schema/data/install-journal.v1.schema.json` and register it in the existing `schema/loader.py` `_KNOWN_SCHEMAS` set.~~ **Retired by the R1/R7 amendment (2026-09-01)**: the JSONL journal is replaced by three-directory recovery state; there is no on-disk journal shape to schematise. Schema file under `contracts/`, runtime copy under `schema/data/`, and the loader registration were removed in the code-cleanup PR that followed the amendment.
- [x] T007 [P] Vendor [contracts/visibility-marker.v1.schema.json](./contracts/visibility-marker.v1.schema.json) into [src/haex_hive/schema/data/visibility-marker.v1.schema.json](../../src/haex_hive/schema/data/visibility-marker.v1.schema.json) and register it in the existing [schema/loader.py](../../src/haex_hive/schema/loader.py) `_KNOWN_SCHEMAS` set.
- [x] T008 [P] Contract test for install-lock v2 in [tests/install/contract/test_install_lock_schema.py](../../tests/install/contract/test_install_lock_schema.py): load the schema, assert a minimal Spec-008 constitution-only shape (explicit v2 fields, no install atoms) validates, assert a full Spec-008 shape validates, and cover negative cases (missing `atoms[i].source`, malformed revision, unknown ownership fields).
- [x] ~~T009~~ [P] ~~Contract test for install-journal v1 in `tests/install/contract/test_journal_schema.py`: validate one entry per `entry_type` enum value, assert a well-formed but mis-chained `tail_hash` still passes schema (chain integrity is runtime), and cover negative cases (unknown entry_type, padded digest, missing required field, unknown top-level field).~~ **Retired by the R1/R7 amendment (2026-09-01)** with T006. Test file removed in the code-cleanup PR that followed the amendment.
- [x] T010 [P] Contract test for visibility-marker v1 in [tests/install/contract/test_visibility_marker_schema.py](../../tests/install/contract/test_visibility_marker_schema.py): validate `.haex-hive/`-only MVP and `.haex-hive/` + `.claude/` mixed-overlay shapes; cover unknown-field rejection, empty or duplicate `participating_roots`, invalid root names, and bad `generation_id`.
- [x] T011 [P] Contract test for owner-token format in [tests/install/contract/test_owner_token_format.py](../../tests/install/contract/test_owner_token_format.py): round-trip parse/serialise, hostname sanitisation (`[A-Za-z0-9.-]` only, 64-char cap, `unknown` fallback), 128-byte length ceiling, negative cases (wrong field count, uppercase UUID). Skipped at module level until T013 lands `OwnerToken` in [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py); the skip guard drops automatically once the class exists.

### Dataclasses and small helpers

- [x] ~~T012~~ [P] ~~Implement `PlanStep`, `PlanSnapshot`, and `CommitSnapshot` frozen dataclasses in `src/haex_hive/install/plan.py` with plan_snapshot_digest, ad-hoc round-trip verification, non-monotonic step-id rejection, and `matches()` comparison.~~ **Retired by the trust-git amendment (2026-09-01)** together with FR-006 and the whole PlanSnapshot/CommitSnapshot defence-in-depth layer. The three dataclasses plus the `build_plan` entry point were deleted in the post-amendment code-cleanup PR; the `install()` orchestration composes the three fixed-shape files (`constitution.md`, `install.lock`, `visibility.json`) directly and hands them to `publish_generation`.
- [x] T013 [P] Implement `OwnerToken` dataclass with parse/serialise + hostname validation in [src/haex_hive/install/lock.py](../../src/haex_hive/install/lock.py) per research §R4. `OwnerToken.emit()` sanitises the hostname per contract (drops non-`[A-Za-z0-9.-]` chars, truncates to 64, falls back to `"unknown"`); serialisation refuses tokens over the 128-byte cap. Unblocks T011 (`test_owner_token_format.py`).
- [x] ~~T014~~ [P] ~~Implement `JournalEntry` (frozen dataclass), `EntryType` `Literal` covering all 12 enum values, `canonical_json`, `compute_tail_hash`, `make_entry`, `append_entry`, `read_entries`, and `verify_chain` in `src/haex_hive/install/journal.py` per research §R7.~~ **Retired by the R1/R7 amendment (2026-09-01):** the JSONL journal + tail-hash chain design was replaced by the rename-swap contract in §R1 and the three-directory recovery state in §R7. The code-cleanup PR that followed the amendment deleted `install/journal.py` outright; the sole helper it exposed to other modules (`canonical_json`) was renamed to `compact_json` and moved to `haex_hive.io.json_deterministic` where it lives alongside the pretty-print `dumps`. The R7 state-table dispatcher lands as new `install/inflight.py` under T042.
- [x] T015 [P] Implement the `VisibilityMarker` frozen dataclass + `to_dict` / `to_json_bytes` (via `json_deterministic.dumps`) in [src/haex_hive/install/visibility.py](../../src/haex_hive/install/visibility.py) per data-model.md. `VisibilityMarker.__post_init__` rejects empty and duplicate `participating_roots`; generation compatibility of mixed-root pointers is validated by the reader contract and remains a Spec 010 adapter concern.
- [x] T016 [P] Implemented `InstallLock` v2 model + serialiser in [src/haex_hive/model/install_lock.py](../../src/haex_hive/model/install_lock.py). Promoted `atoms`, `participating_roots`, `visibility_marker` to first-class fields; kept the review-fix immutability pattern (Mapping + freeze_json + constructor validation for duplicate root names). **Trust-git amendment (2026-09-01)** simplifies the follow-on code-cleanup: `content_integrity` fields are removed from `AtomInstallRecord`, `RootRecord` becomes a plain `participating_roots: tuple[str, ...]`, `VisibilityMarkerRef` keeps only `generation_id`, and the whole `OwnershipSet` / `PathOwnershipRecord` / `PreviousPathState` / `OwnerResource` shape retires. `constitution/assemble.py` composes the slimmed lock; the retired-field contract tests were removed in the post-amendment review-fix commits.
- [x] T017 [P] Implement `HaexInstallError` and subclasses (`InstallLockBusy` → `INSTALL_LOCK_BUSY` 9, `IncompleteTransaction` → `INCOMPLETE_TRANSACTION` 7, `OverlayUnsupported` → `SYSTEM_REFUSE` 5, `SealMismatch` → `POST_WRITE_VALIDATION` 6) in [src/haex_hive/install/errors.py](../../src/haex_hive/install/errors.py). Every subclass carries a diagnostic key matching the CLI contract's exit-code table; snapshot-mismatch errors are retired with FR-006.
- [x] ~~T018~~ [P] ~~Implement `compute_root_digest(root_dir, root_name, overlay_paths=None)` in `src/haex_hive/install/digest.py` per research §R5. Byte-sorted enumeration, `<repo-relative-path>:<hex>\n` concatenation, SHA-256 → base64url-nopad.~~ **Retired by the trust-git amendment (2026-09-01)** with §R5. `install/digest.py` was deleted in the post-amendment code-cleanup PR; git tree hashes provide the byte-identity guarantee that `content_integrity` was reproducing.

### Extended shared IO

- [x] T019 Extended [src/haex_hive/io/writer_lock.py](../../src/haex_hive/io/writer_lock.py) — `ConstitutionWriterLock` now accepts an optional `OwnerToken` (T013). When supplied, `__enter__` writes the R4 `install.mutex` payload (owner token + `acquired_at` + `heartbeat_at` + `heartbeat_at_ns_wallclock` + `heartbeat_interval_ns=5s` + `ttl_ns=60s` + `safety_margin_ns=5s`) through the already-locked handle; `heartbeat()` rewrites `heartbeat_at`/`heartbeat_at_ns_wallclock` in place via `os.lseek+os.ftruncate+os.write+os.fsync` (POSIX) or `SetFilePointerEx+SetEndOfFile+WriteFile+FlushFileBuffers` (Windows) so the pathname and inode remain stable. Omitting the token preserves the pre-Spec-008 no-metadata behaviour for callsites that have not migrated yet. Path helpers (`transaction_paths.mutex`) are already provided by `io/state.py`. [cli/constitution.py::run_assemble](../../src/haex_hive/cli/constitution.py) now emits an `OwnerToken` on every acquisition. The background heartbeat thread + revalidation-before-reclaim protocol land in T034 on top of the primitives here.
- [x] T020 Replaced [src/haex_hive/io/transaction.py](../../src/haex_hive/io/transaction.py) with `publish_generation(live, files, *, post_write_verify=None, state_root=None, repo_root=None)` per research §R1. The primitive writes every `StagedFile` into `<root>.next/`, fsyncs each file plus the staging directory, then performs `os.rename(<root>, <root>.prev)` (skipped when `<root>/` does not exist) followed by `os.rename(<root>.next, <root>)`, with a parent-directory fsync after each rename. `post_write_verify` runs after the swap; on failure the swap is best-effort rolled back (`<root>` renamed back to `<root>.next`, then `<root>.prev` renamed back to `<root>` when it existed before). `<root>.prev/` is removed as the transaction's final step. The `_crash_after` seams (`rename_a`, `rename_b`) are preserved for FR-014 conformance kills. constitution-assemble's `_publish_constitution` in [constitution/assemble.py](../../src/haex_hive/constitution/assemble.py) is the first consumer.

The device-local state root owns only the mutex and the identity record. All
per-install pre-images and staged bytes live in `<root>.next/` and
`<root>.prev/` beside each participating output root; there is no separate
journal file to write, fsync, or clean up. The three directory names are the
durable in-flight state, and cleanup after a successful swap is a single
`rmtree(<root>.prev/)`.

**Checkpoint**: Foundation ready — the install subpackage compiles, schemas validate against their fixtures, and constitution assemble still passes its existing tests. User story implementation can now begin.

---

## Phase 3: User Story 1 — Happy-path install (Priority: P1) 🎯 MVP

**Goal**: Running `haex install` on a satellite with a valid `.haex-hive.json` publishes a byte-perfect new generation: `.haex-hive/constitution.md`, `.haex-hive/install.lock`, and `.haex-hive/visibility.json` all agree; re-running is a no-op.

**Independent Test**: Per [spec.md §US1 Independent Test](./spec.md) — on a satellite adopting two atoms from `github.com/haexmas/haex-hive`, run `haex install`; verify constitution assembly, the slim install-lock and visibility-marker shapes, and a second no-op run.

### Tests for User Story 1

- [x] T021 [P] [US1] Integration test at [tests/install/integration/test_happy_path.py](../../tests/install/integration/test_happy_path.py). **Deviation**: MVP is constitution-only (single-source atom); the existing `single_source_constitution_fixture` in `tests/conftest.py` is reused instead of a new two-atom fixture under `tests/install/fixtures/`. The two-atom happy-path lands with US1 delta support (T046 landing atoms end-to-end) — this MVP test asserts the three-file publication contract (constitution body byte-for-byte, install.lock records the atom's `(id, source, revision, contributed_paths)` with no `content_integrity`, visibility.json names a fresh generation ID and `.haex-hive/` in `participating_roots`, and both generation IDs match).
- [x] T022 [P] [US1] Integration test at [tests/install/integration/test_idempotent_no_op.py](../../tests/install/integration/test_idempotent_no_op.py): installs once, captures `stat` and bytes of every output, installs again, asserts zero mtime changes, zero byte differences, and stdout reports "no changes" (SC-003). Idempotence detection is byte-comparison of the composed constitution body plus recorded source `(id, revision)` vs. the on-disk generation, per the trust-git amendment.

### Implementation for User Story 1

- [x] ~~T024~~ [P] [US1] ~~`build_plan(repo_root, state_root) -> PlanBuildResult` in `install/plan.py` — MVP three-step plan with content_integrity payloads.~~ **Retired by the trust-git amendment (2026-09-01)** together with T012 and T025. The install-side entry point moves to a thin `install()` in `cli/install.py` that composes the fixed three files directly and calls `publish_generation`; no typed plan intermediate needed for a fixed-shape publication. `install/plan.py` + `test_build_plan.py` were deleted in the post-amendment code-cleanup PR.
- [ ] ~~T025~~ [P] [US1] ~~Implement commit-snapshot re-read + digest match in `install/commit_snapshot.py` per FR-006…~~ **Retired by the trust-git amendment (2026-09-01)** together with FR-006. `install/commit_snapshot.py` was never populated; the stub file was deleted in the post-amendment code-cleanup PR.
- [ ] ~~T026~~ [P] [US1] ~~Implement staged-root writer in `src/haex_hive/install/stage.py`…~~ **Retired by the trust-git amendment (2026-09-01)**. The T020 `publish_generation(live, files, ...)` primitive already writes every `StagedFile` into `<root>.next/` and fsyncs; no separate staged-writer module needed for the constitution-only MVP. The stub file `install/stage.py` was deleted in the post-amendment code-cleanup PR.
- [x] T027 [US1] Implemented `allocate_generation_id(body, existing_generation_id)` in [src/haex_hive/install/generation.py](../../src/haex_hive/install/generation.py). Timestamp is UTC allocation time; suffix is `sha256(body)[:4]`; when the candidate is not strictly greater than the existing ID, allocation advances by one second past the existing timestamp so IDs remain lexicographically monotonic. `constitution/assemble.py` migrated from its local `_allocate_generation_id` to this shared helper.
- [x] T028 [US1] Implemented the slim `install()` entry point in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py) replacing the T003 stub. Pipeline: `ConstitutionWriterLock(paths.mutex, OwnerToken.emit())` → `inflight.resolve(repo_root / HAEX_HIVE_DIR)` → `ConsumerManifest.from_json` → `resolve_constitution_contributions` → single-source no-op check (`_is_no_op_single_source` compares live constitution body byte-for-byte plus recorded `(id, revision)`) → on match report "no changes" with no writes and no generation-ID allocation, otherwise delegate to `assemble_single_source` which allocates the generation ID and publishes via `publish_generation`. Multi-source delegates to `assemble_multi_source` unchanged (no MVP idempotence for adapter-produced content). **Deviation**: the byte composition of `install.lock` and `visibility.json` (T029/T030) is not inlined in `cli/install.py`; it stays in `constitution/assemble.py::_publish_constitution` where it was already implemented, reviewed, and covered. `cli/install.py` is currently the caller, not the composer. T031 (assemble-shim through install) will invert this direction and consolidate the composition once the multi-source idempotence question is answered.
- [x] T029 [US1] `install.lock` byte composition lives in [src/haex_hive/constitution/assemble.py](../../src/haex_hive/constitution/assemble.py)::`_publish_constitution` (not inlined in `cli/install.py` — see T028 deviation). Builds a slimmed `InstallLock` from resolved `constitution.sources` + validated `generation_inputs` (sorted by `(kind, id)` and re-validated via `InstallLock.from_json(lock_bytes)` before staging) + `participating_roots=(".haex-hive/",)` + `visibility_marker.generation_id` shared byte-for-byte with T030. Post-write verification asserts the published lock's root list and generation cross-reference.
- [x] T030 [US1] `visibility.json` byte composition lives in [src/haex_hive/constitution/assemble.py](../../src/haex_hive/constitution/assemble.py)::`_publish_constitution` (not inlined in `cli/install.py` — see T028 deviation). Composes `{"haex_hive_version": "2", "generation_id": <T027>, "participating_roots": [".haex-hive/"]}` via `json_deterministic.dumps`. **Deviation**: `written_at` is not emitted; the marker holds only content-identity fields under the trust-git amendment. Post-write verification asserts the marker's `generation_id` equals the lock's cross-reference. Idempotence in T028 short-circuits before allocation, so no `generation_id` is ever produced for an unchanged publication.
- [ ] T031 [US1] Route existing `haex constitution assemble` through the new `install()` (T028): the CLI shortcut still exists but internally calls the same `install()` entry point. The current standalone `_publish_constitution` in `constitution/assemble.py` collapses into a thin shim that forwards to `install()`. Verify existing constitution unit + integration tests pass unchanged. Depends on T028.

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
- [ ] T037 [US2] Add `--verify-only` flag handling in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py): acquire the shared-read lock, load and validate the marker, require every named root and active overlay pointer to be available for the marker's `generation_id`, and exit 0 only for that generation-compatible view. Exit 6 on a missing, incomplete, or mismatched view. Depends on T028, T035.

**Checkpoint**: Concurrent installs are safely serialised; the loser diagnostic names the winner; `haex install --verify-only` reads under a shared lock.

---

## Phase 5: User Story 3 — Crash recovery preserves consistency (Priority: P2)

**Goal**: A crash at any legal in-flight state either completes the interrupted install to a valid new generation (rows 3 and 7 of §R7) or restores the previous generation (rows 4 and 5). Unowned files under `.claude/`/`.codex/` survive recovery byte-identically.

**Independent Test**: Per [spec.md §US3 Independent Test](./spec.md) — scripted-kill at each of the four in-flight states in FR-014 (pre-staging, staged pre-swap, mid-swap between rename A and rename B, post-swap pre-cleanup); after each, run `haex verify --recover` and assert the §R7 state table's outcome.

### Tests for User Story 3

- [ ] T038 [P] [US3] Unit test at [tests/install/unit/test_inflight_recovery.py](../../tests/install/unit/test_inflight_recovery.py): construct each of the eight `<root>{,.next,.prev}` combinations from the §R7 state table under a `tmp_path` root and assert the dispatcher (T042) reaches the specified outcome — steady state, forward completion, cleanup, restoration from an available `.prev`, or refusal for illegal/unavailable states. The fixtures MUST also assert the root-availability contract: `pre_swap` requires the live prior generation while discarding `.next`; `mid_swap` requires a valid candidate `.next` plus prior `.prev` before completing forward; `orphan_next` requires a valid `.next` candidate and all of its participating roots before completing forward; `post_swap` with an unavailable live root requires an available `.prev`, restores candidate-named pointers to the prior generation before replacing live, and refuses without deletion if classification fails; and `absent/absent/present` restores only an available `.prev` generation. Every successful outcome must assert matching marker/lock generation IDs and participating-root availability. T038 MUST cover both previous-generation restoration scenarios explicitly.
- [ ] T039 [P] [US3] Conformance test at [tests/install/conformance/test_crash_matrix.py](../../tests/install/conformance/test_crash_matrix.py) (FR-014): parametrise over the four in-flight crash points (after lock before staging, staged and metadata-validated before rename A, between rename A and rename B, and after rename B before `.prev` cleanup); each case runs the install in a child process and terminates it with `SIGKILL` or the platform-equivalent abrupt termination at the target boundary, then runs `haex verify --recover` and asserts the §R7 outcome (forward completion, restoration of an available previous generation, or explicit refusal) (SC-001). Do not use `SystemExit` as the crash mechanism.
- [ ] T040 [P] [US3] Conformance test at [tests/install/conformance/test_coordinated_input_writer.py](../../tests/install/conformance/test_coordinated_input_writer.py) (FR-015): a background writer attempts to rewrite `.haex-hive.json` while install holds the exclusive lock; assert the writer waits or is refused and cannot change the inputs used by the install (SC-004).
- [ ] T041 [P] [US3] Conformance test at [tests/install/conformance/test_unowned_files_survive.py](../../tests/install/conformance/test_unowned_files_survive.py) (FR-017): pre-populate `.claude/` and `.codex/` with unowned files outside the adapter-owned path allowlist; run install, crash mid-way, recover; assert those files are byte-identical throughout (SC-006).

### Implementation for User Story 3

- [ ] T042 [US3] Complete the implementation in [src/haex_hive/install/inflight.py](../../src/haex_hive/install/inflight.py) before marking this task done. `InflightState.inspect`/`resolve` MUST validate schema-compatible marker and lock metadata, the lock/marker generation cross-reference, availability of every participating root, and active mixed-root pointer generations before cleanup, publication, or forward completion. They MUST restore candidate pointers to the live prior generation before acting on a pre-marker crash, retain pointers matching the authoritative published marker, treat `ORPHAN_NEXT` as recoverable only after validating its staged generation and completing it forward, and preserve/refuse any unclassifiable or invalid state without deleting evidence. Parent-directory fsync is required after every rename/removal. Add the corresponding unit/conformance coverage in T038–T041; only then tick T042. The availability matrix is explicit: `STEADY` requires the live marker and all live roots/pointers; `UNINITIALIZED` has no recovery candidate; `PRE_SWAP` requires a valid live prior generation, restores prior pointers, then discards `.next`; `MID_SWAP` requires valid candidate `.next` and prior `.prev` generations plus all participating roots before completing forward; `POST_SWAP` requires the live candidate and pointers, or (if live is unavailable) a valid `.prev` prior generation and pointer restoration before replacing live; `ORPHAN_PREV` (`absent/absent/present`) restores only a validated `.prev` generation and its prior pointers; `ORPHAN_NEXT` requires a validated `.next` candidate and all of its roots before completing forward; `ILLEGAL_ALL` refuses and preserves all evidence. T038 MUST assert both `.prev` restoration paths and every successful marker/lock/pointer generation match.
- [ ] T043 [US3] Rollback is a direct consequence of the R1 rename-swap contract: `<root>.prev/` retained beside the live `<root>/` is the pre-image. T042 may restore it only for R7's `present/absent/present` row after validating `.prev` and restoring every candidate-named mixed-root pointer to the previous generation, or the `absent/absent/present` row when the staged generation is absent and `.prev` is available. A present but unavailable `.next` in the `absent/present/present` row must be refused without publication. The pointer restoration, removal, and subsequent `os.rename(<root>.prev, <root>)` each fsync the parent; a crash between them re-enters the `absent/absent/present` row. No separate rollback module lands. Depends on T042.
- [ ] T044 [US3] Add `--recover` handling to `haex verify` in [src/haex_hive/cli/install.py](../../src/haex_hive/cli/install.py): acquires exclusive lock (T019), dispatches the in-flight recovery state via T042, propagates an unavailable-state refusal and its non-zero diagnostic unchanged, and reports "recovered generation `<gen>`" with exit 0 only after complete-forward, cleanup, or restoration of an available previous generation. Depends on T028, T042.
- [ ] T045 [US3] Stale-directory cleanup at the start of every successful exclusive-lock acquisition is subsumed by T042's dispatcher — the §R7 state table already prescribes how to treat leftover `<root>.next/` or `<root>.prev/` in every legal combination. Task-slot retained for traceability; no separate implementation. Depends on T042.

**Checkpoint**: Every crash point in FR-014 resolves to complete-new or rollback-to-previous. Unowned files survive. `haex verify --recover` is functional.

---

## Phase 6: User Story 4 — Removing an atom cleans up in-transaction (Priority: P3)

**Goal**: Removing an atom from `.haex-hive.json` causes the next `haex install` to delete its contributed files atomically with any new writes. Interrupted deletes roll back cleanly per FR-011.

**Independent Test**: Per [spec.md §US4 Independent Test](./spec.md) — install two atoms, drop one, re-install, verify orphans are gone; interrupt mid-delete, recover, verify no partial state.

### Tests for User Story 4

- [ ] T046 [P] [US4] Integration test at [tests/install/integration/test_delete_orphans.py](../../tests/install/integration/test_delete_orphans.py): install two atoms, drop one, re-install, assert removed atom's files are gone from every participating root and install.lock reflects the reduced atom set.
- [ ] ~~T047~~ [P] [US4] ~~Unit test at `tests/install/unit/test_delta_computation.py`: compute a per-path ownership delta from a previous `install.lock` and a new `PlanSnapshot`.~~ **Deferred by the trust-git amendment:** Spec 008 no longer defines per-path ownership or a PlanSnapshot; omission from the complete staged haex-owned directory provides delete-orphan semantics. Mixed-root delta rules belong to Spec 010.
- [ ] T048 [P] [US4] Conformance test at [tests/install/conformance/test_partial_delete_rollback.py](../../tests/install/conformance/test_partial_delete_rollback.py) (FR-016): run the delete-orphans install in a child process and terminate it with `SIGKILL` or the platform-equivalent abrupt termination after rename A on `.haex-hive/` and before rename B; assert before recovery that `.haex-hive/` is absent while `.haex-hive.next/` and `.haex-hive.prev/` are present (R7's `absent/present/present` row), then recover via T042 and assert the metadata-validated staged generation is completed forward, the removed atom's files are absent from the new `.haex-hive/`, and `.haex-hive.prev/` is cleaned up. Do not accept rollback for this state. Under R1 there is no per-delete atomicity concern — the whole generation is materialised in `.haex-hive.next/` and committed by the swap.

### Implementation for User Story 4

- [ ] ~~T049~~ [US4] ~~Implement per-path delta computation in `src/haex_hive/install/delta.py`.~~ **Deferred by the trust-git amendment:** Spec 008 has no persisted ownership set; the complete staged haex-owned directory is the current output set, while mixed-root ownership is a Spec 010 concern.
- [ ] ~~T050~~ [US4] ~~Extend plan-build to retain a `RemovedPathSet` in ownership metadata.~~ **Retired by the trust-git amendment:** there is no plan or ownership metadata in the fixed-shape Spec 008 MVP.
- [ ] T051 [US4] Under R1 there is no separate delete step to implement — removed paths simply do not appear in `.haex-hive.next/`, and the retained `.haex-hive.prev/` is the whole-generation rollback pre-image. Depends on T028.

**Checkpoint**: Delete-orphans installs are atomic-and-recoverable. All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T052 [P] Implement mixed-ownership overlay primitives in [src/haex_hive/install/overlay.py](../../src/haex_hive/install/overlay.py) per research §R3: POSIX `os.symlink()`, Windows true directory junction via `mklink /J` or a native `CreateJunction` helper using the reparse-point API, file-scoped-on-Windows-non-DevMode refusal with `OverlayUnsupported`. Do not substitute `CreateSymbolicLinkW(..., SYMBOLIC_LINK_FLAG_DIRECTORY)` for a junction. Add unit test at [tests/install/unit/test_overlay_primitives.py](../../tests/install/unit/test_overlay_primitives.py) exercising the platform-selection matrix under a `platform` monkeypatch. Not needed on the US1 hot path (`.haex-hive/` is haex-owned) but required for FR-003 and SC-005 conformance ahead of Spec 010 landing.
- [ ] T053 [P] Refresh public surface in [src/haex_hive/install/__init__.py](../../src/haex_hive/install/__init__.py): re-export the small set of entry points other modules import (pipeline entry, error classes, `OwnerToken`); keep everything else module-private.
- [ ] T054 Run [specs/008-install-transaction/quickstart.md](./quickstart.md) end-to-end on a fresh clone with `$HAEX_HIVE_STATE` pointing at a scratch dir: exercise steps 1–7 (first install, no-op re-install, `--verify-only`, concurrent-refusal, `--recover` after scripted kill, delete-orphan install, reader consistency helper). Record SC-001..SC-007 verification outcomes in the phase closing commit message.
- [ ] T055 Full pytest run (`pytest tests/install/` + full suite for regression) and prune any transient imports the install subpackage no longer needs. No code-style refactor beyond removing dead symbols the story tasks left behind.
- [ ] T056 [deferred] Make the adapter `revision` in `generation_input_identities()` at [src/haex_hive/constitution/llm.py:67-91](../../src/haex_hive/constitution/llm.py#L67-L91) stable across install methods. The current implementation hashes `Path(__file__).read_bytes()` as a git blob SHA1, which matches `git hash-object` only under source install (`pip install -e .`). Under wheel, PyInstaller, or Nuitka distributions the on-disk bytes differ from the git-committed source (line-ending normalisation, docstring rewrites, bundled stubs), so the recorded `git:<sha1>` silently drifts and the sealed generator identity becomes diagnostic-only for those installs. Pick one: (a) embed a build-time constant produced from the canonical source-tarball SHA, (b) fall back to `sha256:<hex>` of a bundled canonical adapter payload when the file is not under a git checkout, or (c) document that the field is authoritative only for source installs and demote it explicitly under non-source installs. Not a blocker while haex-hive ships source-only, but must be resolved before the first wheel/bundle release. Add a regression test that asserts the recorded revision equals `git hash-object` on the committed adapter module for a source-checkout install.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. Note that T019 depends on T013+T017; the rest of the phase runs in parallel.
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
- Within US1, T021/T022 and T027 (independent modules) run in parallel. T028 gates on the active prerequisites.
- US3 conformance tests (T038–T041) all run in parallel — different files, no shared state.
- US4 tests (T046/T048) run in parallel; the per-path delta test T047 is deferred to Spec 010.
- Polish T052 and T053 run in parallel.

---

## Parallel Example: Phase 2 Foundational

```bash
# Kick off schema vendoring + contract tests + dataclass modules together:
Task: "Vendor install-lock v2 schema into src/haex_hive/schema/"
Task: "Vendor visibility-marker v1 schema into src/haex_hive/schema/"
Task: "Contract test tests/install/contract/test_install_lock_schema.py"
Task: "Contract test tests/install/contract/test_visibility_marker_schema.py"
Task: "Contract test tests/install/contract/test_owner_token_format.py"
Task: "OwnerToken in src/haex_hive/install/lock.py"
Task: "VisibilityMarker in src/haex_hive/install/visibility.py"
Task: "InstallLock v2 model in src/haex_hive/model/install_lock.py"
Task: "Errors in src/haex_hive/install/errors.py"

# T019 (writer_lock extension) and T020 (rename-swap primitive) run after their deps land.
# T006, T009, T014, and the trust-git snapshot/digest tasks are retired; no journal,
# plan-snapshot, or per-root-digest module or schema is needed.
```

## Parallel Example: User Story 1

```bash
# Tests in parallel:
Task: "Integration test tests/install/integration/test_happy_path.py"
Task: "Integration test tests/install/integration/test_idempotent_no_op.py"
# Independent implementation module:
Task: "Generation-ID helper in src/haex_hive/install/generation.py"

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
