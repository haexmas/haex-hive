---
description: "Task list for Spec 007 Unified Manifest v2 + Migration + Constitution Assemble"
---

# Tasks: Unified Manifest v2 + Migration + Constitution Assemble

**Input**: Design documents from `/specs/007-unified-manifest-v2/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because the spec repeatedly mandates them — FR-035 requires interruption-boundary integration tests, FR-027 requires a full framed-stdio integration test, FR-038 requires source/pending/candidate/lock/migrated-secret unit tests, plan.md §Testing pins `pytest` with contract/integration/unit layout, and `SC-001..SC-008` are only observable through tests. Every user story therefore ships with tests-first tasks.

**Checkbox freshness is load-bearing.** When a task is completed, tick its checkbox in the same commit as the task's output — or at the latest in the next commit, before starting the next task. See [ADR 0004](../../docs/adr/0004-eager-checkbox-update-rule.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. Setup and Foundational precede all stories; Polish follows.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable — different files, no dependencies on incomplete tasks in the same phase.
- **[Story]**: `[US1]`/`[US2]`/`[US3]`/`[US4]` for user-story tasks; omitted from Setup, Foundational, and Polish.

## Path Conventions

Single-project Python CLI. Source under [src/haex_hive/](../../src/haex_hive/), tests under [tests/](../../tests/), packaged schemas under [src/haex_hive/schema/data/](../../src/haex_hive/schema/data/). Paths in tasks are repo-root-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bootstrap the Python package layout, packaging metadata, dependencies, and tooling.

- [X] T001 Create the package skeleton under [src/haex_hive/](../../src/haex_hive/) matching plan.md §"Project Structure" (empty `__init__.py` files for `haex_hive`, `haex_hive.cli`, `haex_hive.schema`, `haex_hive.model`, `haex_hive.git`, `haex_hive.migrate`, `haex_hive.constitution`, `haex_hive.io`, `haex_hive.util`; empty `haex_hive.schema.data/` directory reserved for packaged JSON Schemas).
- [X] T002 Author [pyproject.toml](../../pyproject.toml) declaring the `haex-hive` distribution, Python `>=3.10`, runtime dependency `jsonschema>=4.18`, `[project.scripts] haex = "haex_hive.cli.main:main"`, and inclusion of `haex_hive/schema/data/*.json` as package data.
- [X] T003 [P] Configure lint/format tooling (add `ruff` and `mypy` to `project.optional-dependencies.dev`, plus `[tool.ruff]` and `[tool.mypy]` blocks in [pyproject.toml](../../pyproject.toml); commit a minimal `.editorconfig` if absent — LF, UTF-8, final newline).
- [X] T004 [P] Configure pytest layout in [pyproject.toml](../../pyproject.toml) `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["src"]`, tmp fixture support, registered `slow` marker, and default `addopts` excluding `slow`) and add `pytest` + `pytest-subprocess` to `project.optional-dependencies.dev` so `pip install -e '.[dev]'` installs every checkpoint and CI test dependency.
- [X] T005 [P] Add the GitHub Actions matrix workflow at [.github/workflows/spec-007-ci.yml](../../.github/workflows/spec-007-ci.yml) running the default `pytest` selection, `pytest -o addopts="" -m slow`, and `ruff check` on Linux, macOS, and Windows (research.md §"Deferred / open technical questions" — cross-platform coverage is a hard requirement of D15/FR-035).

**Checkpoint**: `pip install -e '.[dev]'` succeeds and `pytest -q` runs (with zero collected tests) on all three OSes.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Value objects, deterministic serialization, atomic-write / journal primitives, schema packaging, git adapters, and the CLI dispatcher. Every user story depends on these.

**CRITICAL**: No US1/US2/US3/US4 tasks may begin before this phase's `Checkpoint` line.

### Errors, exit codes, diagnostics

- [X] T006 Implement the typed exception hierarchy in [src/haex_hive/util/errors.py](../../src/haex_hive/util/errors.py) with `HaexError` base; each subclass declares its canonical `diagnostic_key` and exit code consumed by `emit_refuse`. Cover every CLI-contract diagnostic path, including `NoSourcesDeclaredError` (`no-sources-declared`), `ConstitutionNotAssembledError` (`constitution-not-assembled`), `InstallLockMissingError` (`install-lock-missing`, show exit 3), `PublisherCloneUnavailableError` (`publisher-clone-unavailable`, assemble exit 3), `PinnedRevisionNotFoundError` (`pinned-revision-not-found`, assemble exit 3), `ContributionFileNotFoundError` (`contribution-file-not-found`, assemble exit 3), and `PostWriteValidationError` (`post-write-validation-failed`, assemble exit 6), alongside `CredentialInUrlError`, `UnsupportedSchemeError`, `PermissionOnlyEntryError`, `IdentityMismatchError`, `MissingRemoteOriginError`, `MissingPublisherManifestError`, `MissingAtomManifestError`, `AtomIdCollisionError`, `VersionBelowMinError`, `PlaintextSecretDetectedError`, `TerminalUnsafeContributionError`, `ConstitutionConcealmentInstructionError`, `MergeNotConfirmedError`, `PendingMergeInputsMismatchError`, `ConstitutionWriterBusyError`, `LlmRequiredForMultiSourceError`, `ConstitutionIntegrityMismatchError`, `InstallLockSchemaInvalidError`, `InstallLockSourcesNotCanonicalError`, and `IncompleteAssemblyTransactionError`.
- [X] T007 Implement canonical exit-code constants in [src/haex_hive/util/exit_codes.py](../../src/haex_hive/util/exit_codes.py) matching [contracts/haex-migrate.cli.md](contracts/haex-migrate.cli.md), [contracts/haex-constitution-assemble.cli.md](contracts/haex-constitution-assemble.cli.md), and [contracts/haex-constitution-show.cli.md](contracts/haex-constitution-show.cli.md) (`SUCCESS=0`, plus every code 2–13 and `USAGE=64`, with cross-command overlaps re-exported once so callers cannot pick divergent values).
- [X] T008 Implement [src/haex_hive/cli/diagnostics.py](../../src/haex_hive/cli/diagnostics.py) with a single `emit_refuse(exc, *, extra: dict[str, str] | None = None)` that formats stderr lines exactly as shown under "Diagnostics" in each CLI contract (`error: exit=<code> key=<slug> ...`), never echoing secret payload values (FR-038).

### Value objects (grammars, canonicalization)

- [X] T009 [P] Implement [src/haex_hive/model/atom_id.py](../../src/haex_hive/model/atom_id.py) with `AtomId.parse(s)` enforcing research.md §R8 (regex + 253-char / 63-per-segment caps + trailing-alphanumeric rule) and `AtomId.parse_identity(s)` reusing the same grammar.
- [X] T010 [P] Implement [src/haex_hive/model/source_url.py](../../src/haex_hive/model/source_url.py) with `canonicalize(url)` implementing research.md §R9 (SCP → `ssh://`, lowercase scheme+host, strip trailing `/`, strip terminal `.git`, refuse userinfo except transport-user `git@` for SSH, refuse every non-`https`/`ssh` scheme) and a strict `CanonicalSourceUrl.validate(s)` used at read time.
- [X] T011 [P] Implement [src/haex_hive/model/version_constraint.py](../../src/haex_hive/model/version_constraint.py) with the `VersionConstraint` dataclass (`operator: Literal["==",">="]`, `version: tuple[int,int,int]`) and `parse(s)` enforcing FR-006 grammar exactly, plus `satisfied_by(installed: tuple[int,int,int]) -> bool`.
- [X] T012 [P] Implement [src/haex_hive/model/repo_relative_path.py](../../src/haex_hive/model/repo_relative_path.py) with `RepoRelativePath.validate(s)` refusing absolute paths, backslashes, drive prefixes, control characters, empty segments, `.`, and `..` (data-model.md §RepoRelativePath).

### Deterministic serialization, atomic writes, journal

- [X] T013 Implement [src/haex_hive/io/json_deterministic.py](../../src/haex_hive/io/json_deterministic.py) exposing `dumps(obj) -> bytes` (research.md §R2: `sort_keys=True`, `indent=2`, `ensure_ascii=False`, LF-only, trailing `\n`).
- [X] T014 Implement [src/haex_hive/io/atomic.py](../../src/haex_hive/io/atomic.py) `write_replace(target: Path, data: bytes)` (write-to-same-directory-tempfile via `mkstemp`, `fsync`, `os.replace`, parent-directory `fsync` on POSIX; explicit `MoveFileExW` write-through + `FlushFileBuffers` on Windows) with mandatory cleanup on error (research.md §R6).
- [X] T015 Implement [src/haex_hive/io/file_hash.py](../../src/haex_hive/io/file_hash.py) `d15_one_file_tree_digest(body: bytes) -> str` producing `sha256-<base64>` over the exact `haex-hive-tree-v1` framing from research.md §R11.
- [X] T016 Implement [src/haex_hive/io/writer_lock.py](../../src/haex_hive/io/writer_lock.py) with a `ConstitutionWriterLock` context manager using non-blocking `fcntl.flock(LOCK_EX|LOCK_NB)` on POSIX and `LockFileEx(LOCKFILE_EXCLUSIVE_LOCK|LOCKFILE_FAIL_IMMEDIATELY)` on Windows; on contention raise `ConstitutionWriterBusyError` without touching the journal or its targets. The POSIX contention indicator is `OSError.errno == errno.EWOULDBLOCK` (aliased to `EAGAIN` on some platforms); the Windows indicator is `GetLastError() == ERROR_LOCK_VIOLATION` (winerror 33) — any other error is re-raised untouched (research.md §R6, FR-035).
- [X] T017 Implement [src/haex_hive/io/transaction.py](../../src/haex_hive/io/transaction.py) with `publish_pair(constitution_body, install_lock_bytes, *, post_write_verify: Callable[[], None] | None = None, ...)` and `recover_if_journaled(...)` executing the FR-035 durable-journal protocol at `.haex-hive/constitution-transaction.json` (stage-and-fsync both files + backups, record `existed`/`absent` per target with backup paths, replace targets, invoke `post_write_verify` while the journal is still on disk — any exception it raises triggers restore-from-backups-or-remove-if-absent-then-remove-journal and is re-raised — otherwise remove journal + fsync directory). Depends on T014 and T016.

### Safety guards

- [X] T018 [P] Implement [src/haex_hive/constitution/safety.py](../../src/haex_hive/constitution/safety.py) `validate_no_plaintext_secrets(payload: bytes, *, location: str)` (private-key blocks, provider-token prefixes, credential-in-URL, `password`/`secret`/`token`/`api_key` assignments) raising `PlaintextSecretDetectedError` without echoing matches (FR-038, research.md §R7).
- [X] T019 [P] Extend [src/haex_hive/constitution/safety.py](../../src/haex_hive/constitution/safety.py) with `validate_terminal_safe_display(body: bytes)` (LF and TAB only in the C0 range; refuse ESC, CR, BS, C1, bidi and other invisible controls) and `validate_no_concealment_instructions(candidate: bytes)` (Principle VIII — invisible/bidi controls, hidden markup, agent-facing conceal directives).

### JSON Schema packaging + validation

- [X] T020 Copy the four Draft 2020-12 schemas from [contracts/](contracts/) into the packaged data directory [src/haex_hive/schema/data/](../../src/haex_hive/schema/data/) (`haex-hive.v2.schema.json`, `publisher-manifest.v2.schema.json`, `atom-manifest.v2.schema.json`, `install-lock.v2.schema.json`), verifying `additionalProperties: false` per FR-004 for consumer-facing objects and preserved forward-compatibility for `install.lock` per FR-030.
- [X] T021 Implement [src/haex_hive/schema/loader.py](../../src/haex_hive/schema/loader.py) `load(name: str) -> dict` reading the packaged JSON via `importlib.resources.files("haex_hive.schema.data")`, and [src/haex_hive/schema/validator.py](../../src/haex_hive/schema/validator.py) `validate(data, schema_name)` wrapping `jsonschema.Draft202012Validator` with error paths formatted for FR-034/SC-006 diagnostics.

### Model dataclasses

- [X] T022 [P] Implement [src/haex_hive/model/consumer_manifest.py](../../src/haex_hive/model/consumer_manifest.py) with `ConsumerManifest`, `AtomEntry`, `ConfigEntry` dataclasses, `ConsumerManifest.from_json(raw)` that runs JSON-Schema validation followed by post-schema semantic checks (`AtomEntry.source` canonicalization idempotence, `revision` `^[0-9a-f]{40}$`, unique `includes`, `config` keys resolvable via `includes`), and `to_json_bytes()` calling `json_deterministic.dumps`; depends on T013 and T021.
- [X] T023 [P] Implement [src/haex_hive/model/publisher_manifest.py](../../src/haex_hive/model/publisher_manifest.py) with `PublisherManifest`, `PublisherAtomEntry`, and post-schema checks (publisher-prefix rule for each atom-id key per data-model.md §PublisherManifest); depends on T021.
- [X] T024 [P] Implement [src/haex_hive/model/atom_manifest.py](../../src/haex_hive/model/atom_manifest.py) with `AtomManifest`, `ContributesBlock`, and the D13 type-by-shape validation (`contributes` XOR/AND `includes`, forbid `type`, enforce `id` reverse-DNS and `config_schema` top-level MUST NOT declare `priority`); depends on T021.
- [X] T025 [P] Implement [src/haex_hive/model/install_lock.py](../../src/haex_hive/model/install_lock.py) with `InstallLock`, `ConstitutionLockSection`, `ConstitutionSource`, and `AssembledBy` dataclasses per data-model.md — the persisted-lock surface only. `InstallLock.from_json` preserves unknown top-level fields (FR-030 forward-compat) and applies the `constitution.sources[]` uniqueness + bytewise-UTF-8 ID sort check after schema validation. `PendingMerge`/`PendingContribution` are owned by T060 (`constitution/pending.py`); `MergeResult` is owned by T059 (`constitution/llm.py`). Depends on T021.

### Git adapters

- [X] T026 [P] Implement [src/haex_hive/git/show.py](../../src/haex_hive/git/show.py) `show_bytes(repo_dir, sha, path) -> bytes` via `git -C <repo_dir> show <sha>:<path>` capturing raw stdout bytes and raising the caller-selected exact typed failure on non-zero exit: `MissingPublisherManifestError` or `MissingAtomManifestError` for manifest resolution, and `ContributionFileNotFoundError` only when an already-declared contribution path is absent at a verified pinned SHA. The caller distinguishes an absent clone (`PublisherCloneUnavailableError`) and absent SHA (`PinnedRevisionNotFoundError`) before this invocation (research.md §R3).
- [X] T027 [P] Implement [src/haex_hive/git/remote.py](../../src/haex_hive/git/remote.py) `origin_url(repo_dir) -> str` via `git -C <repo_dir> remote get-url origin`; raise `MissingRemoteOriginError` on non-zero exit.
- [X] T028 [P] Implement [src/haex_hive/git/revparse.py](../../src/haex_hive/git/revparse.py) `full_sha(repo_dir, maybe_short) -> str` via `git -C <repo_dir> rev-parse <maybe_short>^{commit}`; returns 40-char lowercase hex or raises the appropriate error.

### CLI dispatcher

- [X] T029 Implement [src/haex_hive/cli/main.py](../../src/haex_hive/cli/main.py) with `argparse` root and subparsers (`migrate`, `constitution assemble`, `constitution show`), a top-level `haex_hive_min_version` gate that reads `.haex-hive.json` (when present) and refuses via `VersionBelowMinError` before dispatch (FR-006, FR-034), and dispatch calling command handlers to be added under [src/haex_hive/cli/migrate.py](../../src/haex_hive/cli/migrate.py) and [src/haex_hive/cli/constitution.py](../../src/haex_hive/cli/constitution.py) (stubs initially).
- [X] T030 Add `python -m haex_hive` support via [src/haex_hive/__main__.py](../../src/haex_hive/__main__.py) delegating to `haex_hive.cli.main.main`.

### Foundational tests

- [X] T031 [P] Contract-test all four JSON Schemas in [tests/contract/test_schemas.py](../../tests/contract/test_schemas.py) with per-schema valid/invalid fixture pairs under [tests/fixtures/schemas/](../../tests/fixtures/schemas/) (haex_hive, publisher_manifest, atom_manifest, install_lock). Every invalid fixture MUST also assert that the raised diagnostic carries the offending field's JSON Pointer path (e.g. `/atoms/0/source`, `/constitution/sources/1/id`) so SC-006's "names the field path" guarantee is verified, not only implied.
- [X] T032 [P] Unit tests for value objects in [tests/unit/test_atom_id.py](../../tests/unit/test_atom_id.py), [tests/unit/test_source_url.py](../../tests/unit/test_source_url.py), [tests/unit/test_version_constraint.py](../../tests/unit/test_version_constraint.py), [tests/unit/test_repo_relative_path.py](../../tests/unit/test_repo_relative_path.py) — cover grammar acceptance, rejection edges (`com.example-`, `com.example--`, uppercase, userinfo, `git://`, `.git`-suffix, 254-char id, leading-zero versions, `>= X.Y.Z` with space). Plus an [tests/unit/test_install_lock_semantics.py](../../tests/unit/test_install_lock_semantics.py) that feeds `InstallLock.from_json` a schema-valid payload with (a) duplicate `constitution.sources[].id` and (b) mis-sorted (non-bytewise-UTF-8) sources, asserting each raises `InstallLockSourcesNotCanonicalError` (FR-030 uniqueness/sort semantic check).
- [X] T033 [P] Unit tests for deterministic JSON in [tests/unit/test_json_deterministic.py](../../tests/unit/test_json_deterministic.py) (byte-identity across two calls with nested dicts and non-ASCII strings; trailing newline).
- [X] T034 [P] Unit tests for D15 tree digest in [tests/unit/test_file_hash.py](../../tests/unit/test_file_hash.py) covering empty and non-empty body bodies against a hand-computed reference vector.
- [X] T035 [P] Unit tests for the safety guards in [tests/unit/test_constitution_safety.py](../../tests/unit/test_constitution_safety.py) — plaintext-secret, terminal-unsafe display, concealment-instruction — with fixtures for private-key blocks, provider tokens, `password=…`, bidi controls, and ordinary visible content.
- [X] T036 Unit tests for the transaction/journal in [tests/unit/test_transaction.py](../../tests/unit/test_transaction.py) covering FR-035 recovery boundaries (interruption immediately after journal creation and after each of the two target replacements) for both existing and absent initial targets, plus mixed-pair and concurrent-writer refusal via `ConstitutionWriterLock`.
- [X] T037 [P] Unit tests for the raw-bytes `git show` boundary in [tests/unit/test_git_show_raw_bytes.py](../../tests/unit/test_git_show_raw_bytes.py) using a temp git repo whose `.gitattributes` declares a filter, asserting `show_bytes` returns unfiltered blob bytes (research.md §R3 alternative-rejection rationale).

**Checkpoint**: Foundation ready. Every value object, primitive, schema, and adapter passes its unit/contract tests. User-story phases can now begin.

---

## Phase 3: User Story 1 — Migrate haex-hive from v1 to v2 (Priority: P1) MVP

**Goal**: Deliver the review-gated `haex migrate` command and the three-commit haex-hive self-migration so this repo becomes its own first v2 publisher.

**Independent Test**: In this repo, `haex migrate --dry-run` produces the expected v1→v2 diff for the design-doc migration table with exit 0. A subsequent `haex migrate` writes `.haex-hive.json.migrated`, leaves `.haex-hive.json` untouched, and the sidecar validates against `haex-hive.v2.schema.json`. Re-running `haex migrate` on a v2 file reports `already migrated to v2` and exits 0. Every negative acceptance scenario (SC-005) refuses with the exact diagnostic keys listed in the migration table.

### Tests for US1 (write first; ensure they FAIL before implementation)

- [X] T038 [P] [US1] Contract test in [tests/contract/test_migration_table.py](../../tests/contract/test_migration_table.py) freezing the design-doc migration table: for every documented v1 shape (single `role: "constitution"` + `self`, permission-only bare `repository`, `repository`+`revision`, `repository`+`paths`, credential-URL, non-GitHub identity, short SHA, missing publisher manifest, missing atom manifest) drive `haex_hive.migrate.transform` and assert either the exact v2 output bytes or the exact `(exit_code, key)` refusal.
- [X] T039 [P] [US1] Unit test [tests/unit/test_transform.py](../../tests/unit/test_transform.py) for identity lowercasing + reverse-DNS conversion, `self`-resolution from a fixture repo, full-SHA expansion from a short SHA, sorted `includes[]` after grouping same-`(source, revision)` v1 entries, and FR-038 refusal on secrets in the original `.haex-hive.json` bytes plus in the produced v2 sidecar bytes.
- [X] T040 [P] [US1] Integration test [tests/integration/test_migrate.py](../../tests/integration/test_migrate.py) invoking `subprocess.run(["haex","migrate", ...])` end-to-end for every US1 Acceptance Scenario (1 through 7) using a fixture-repo tree with a pre-cloned bare publisher under a `HAEX_HIVE_STATE` tmp path; assert exit codes, stdout diff shape, and filesystem state (sidecar present/absent, tempfile absent, original untouched).
- [X] T041 [P] [US1] Integration test [tests/integration/test_migrate_preview_modes.py](../../tests/integration/test_migrate_preview_modes.py) covering FR-018 (`--dry-run` and `--check` byte-identical stdout, no sidecar side-effect, both-flags → exit 64) and FR-014 (write-mode invalidates stale sidecar; preview preserves it).
- [X] T042 [P] [US1] Integration test [tests/integration/test_migrate_haex_hive_self.py](../../tests/integration/test_migrate_haex_hive_self.py) that reconstructs the FR-023 three-commit fixture (`A` root+atom manifests, `B` v1 revision bump, `C` migrated v2) and asserts that migrating `B`'s input yields `C`'s v2 bytes pinned to `A` (SC-001).

### Implementation for US1

- [X] T043 [P] [US1] Implement [src/haex_hive/migrate/detect.py](../../src/haex_hive/migrate/detect.py) `detect_version(raw: bytes) -> Literal[1, 2]` reading `haex_hive_version` and rejecting unknown values via `FR-034` (raises the CLI-mapped error).
- [X] T044 [US1] Implement [src/haex_hive/migrate/transform.py](../../src/haex_hive/migrate/transform.py) `migrate_v1_to_v2(raw_v1: bytes, repo_root: Path, state_root: Path) -> bytes` executing every rule in the design-doc migration table (identity conversion, `self`→canonical URL via `git.remote`, short-SHA expansion via `git.revparse`, publisher-manifest lookup via `git.show`, atom selection under D3 uniqueness, grouping by `(source, revision)` with sorted `includes`); depends on T009–T012, T022–T024, T026–T028, T043.
- [X] T045 [US1] Implement [src/haex_hive/migrate/sidecar.py](../../src/haex_hive/migrate/sidecar.py) `publish_sidecar(repo_root, v2_bytes)` and `invalidate_stale_sidecar(repo_root)` implementing FR-014–FR-016 (write mode: delete stale sidecar before evaluation; atomic replace via `atomic.write_replace`; on failure remove tempfile and ensure sidecar absent); depends on T014.
- [X] T046 [US1] Implement the `haex migrate` handler in [src/haex_hive/cli/migrate.py](../../src/haex_hive/cli/migrate.py) wiring flag parsing (`--dry-run`, `--check`, mutually exclusive → exit 64), FR-038 guard over both the original and proposed bytes before printing any diff, `difflib.unified_diff` printing to stdout (FR-017), the already-v2 early-exit (FR-012), and every documented exit code from [contracts/haex-migrate.cli.md](contracts/haex-migrate.cli.md); depends on T017 (transaction module reused for atomic write helpers only if needed) and T044/T045.
- [X] T047 [US1] FR-023 self-migration commit A: create the root manifest at [manifest.json](../../manifest.json) mapping `com.github.haexmas.haex-hive.constitution` to `.specify/memory` with `version: "1.3.0"` and the atom manifest at [.specify/memory/manifest.json](../../.specify/memory/manifest.json) with `id: "com.github.haexmas.haex-hive.constitution"`, `version: "1.3.0"`, `priority: 10`, `contributes.constitution: "constitution.md"` — validated by `test_schemas.py` and `test_migrate_haex_hive_self.py`. **Rationale for root placement**: FR-021 permits repo-root or "another well-known location documented alongside"; root is chosen because publisher discovery via `git show <sha>:manifest.json` matches the design-doc convention (D11) with a single fixed lookup path per publisher and no extra indirection, and the repo currently has no file at that path (verified pre-commit). If a future publisher chooses a non-root location, they document it in their own README; haex-hive commits to the root convention as the reference case.
- [X] T048 [US1] FR-023 self-migration commit B: bump `.haex-hive.json` `harness_sources[0].revision` to commit A's full SHA in [.haex-hive.json](../../.haex-hive.json); the commit message references FR-023 so reviewers can trace the sequence.
- [X] T049 [US1] FR-023 self-migration commit C: run `haex migrate` in the repo, `mv .haex-hive.json.migrated .haex-hive.json`, and commit the v2 result; verify the committed `atoms[0].revision` equals commit A's SHA (never C's).

**Checkpoint**: US1 is independently functional. SC-001 passes; running `haex migrate` in this repo produces the v2 form matching commit C of the self-migration fixture.

---

## Phase 4: User Story 2 — Single-source `haex constitution assemble` (Priority: P2)

**Goal**: Deliver the deterministic straight-copy path of `haex constitution assemble` including install-lock provenance, so a consumer with exactly one constitution atom gets a byte-for-byte copy plus recorded content-hash.

**Independent Test**: In a fixture repo with a v2 `.haex-hive.json` pointing at one constitution atom, `haex constitution assemble` writes `.haex-hive/constitution.md` byte-identical to the source at the pinned SHA, and `.haex-hive/install.lock`'s `constitution.content_integrity` equals the D15 one-file-tree digest of that body. Running the command twice produces byte-identical outputs (SC-002, FR-031, FR-036).

### Tests for US2

- [X] T050 [P] [US2] Integration test [tests/integration/test_assemble_single_source.py](../../tests/integration/test_assemble_single_source.py) covering US2 acceptance scenarios 1–4: successful straight-copy, determinism across two runs, unavailable pinned SHA refusal with `exit=3 key=pinned-revision-not-found` and untouched outputs, declared contribution file absent at a verified pinned SHA with `exit=3 key=contribution-file-not-found`, and interaction with `haex constitution show` (deferred stub for T063 to reuse).
- [X] T051 [P] [US2] Unit test [tests/unit/test_resolve.py](../../tests/unit/test_resolve.py) for D11 two-step lookup (`PublisherManifest → PublisherAtomEntry → AtomManifest`), including publisher-key/atom-id mismatch, version mismatch, atom-id collision under two different `(source, revision)` pairs, and canonicalization-idempotence refusal.
- [X] T052 [P] [US2] Integration test [tests/integration/test_install_lock_forward_compat.py](../../tests/integration/test_install_lock_forward_compat.py) writes an install.lock carrying an unknown top-level `atoms` field (simulating a future Spec-008 write), runs `haex constitution assemble`, and asserts the unknown field survives verbatim (FR-030 forward-compat).

### Implementation for US2

- [X] T053 [P] [US2] Implement [src/haex_hive/constitution/resolve.py](../../src/haex_hive/constitution/resolve.py) with the in-memory-only `ResolvedConstitutionContribution` dataclass (per data-model.md §ResolvedConstitutionContribution — `source: ConstitutionSource`, `body: bytes`; not persisted) co-located in this module because it is only produced here and consumed by T054/T059/T060/T061, and `resolve_constitution_contributions(manifest: ConsumerManifest, state_root: Path) -> list[ResolvedConstitutionContribution]` performing D11 two-step lookup for every atom-id in every `atoms[].includes[]`, canonicalizing sources by D3 first, filtering to atoms declaring `contributes.constitution`, loading their raw bytes via `git.show`, and raising the exact exception → exit-code mapping in [contracts/haex-constitution-assemble.cli.md](contracts/haex-constitution-assemble.cli.md); depends on T010, T022–T025 (`ConstitutionSource`), T026.
- [X] T054 [US2] Implement [src/haex_hive/constitution/assemble.py](../../src/haex_hive/constitution/assemble.py) `assemble_single_source(contribution, repo_root)` that runs the FR-038 secret guard, computes the D15 content-integrity, builds the `InstallLock` (populating `constitution.sources[]`, `assembled_by`, `content_integrity`; preserving unknown top-level fields when re-writing an existing lock), and calls `io.transaction.publish_pair` to atomically write both files. Pass a `post_write_verify` callback to `io.transaction.publish_pair` that runs after target replacement but **before journal removal** (backups must still exist for rollback): the callback re-reads the on-disk `constitution.md`, re-computes the D15 one-file-tree digest, and compares it with the just-recorded `content_integrity`. On mismatch the callback raises `PostWriteValidationError`; `publish_pair` restores both targets from their journaled backups (or removes them when the recorded prior state is `absent`), removes the journal, and re-raises so the CLI maps to contract exit 6. Depends on T015, T017 (post-write hook), T018, T025, T053.
- [X] T055 [US2] Wire the `haex constitution assemble` handler for the single-source path in [src/haex_hive/cli/constitution.py](../../src/haex_hive/cli/constitution.py) (writer-lock acquisition via T016, transaction recovery via T017 before resolution, no-source zero-count refusal `exit=2 key=no-sources-declared`, single-source dispatch to T054, exit-code mapping per contract).

**Checkpoint**: US2 is independently functional. SC-002 and FR-031/FR-036 pass with byte-identical outputs on repeat runs.

---

## Phase 5: User Story 3 — Multi-source `haex constitution assemble` with LLM merge (Priority: P2)

**Goal**: Deliver the LLM-merge path with `stdio`, `file`, and `none` methods, framed candidate/confirmation protocol, pending-merge JSON with `pending_id` binding, and post-candidate safety validation before the pair publishes.

**Independent Test**: In a fixture repo with two constitution atoms, `haex constitution assemble --llm=stdio` under a mocked stdio adapter (framed `Content-Length` candidate + `--haex-confirm: yes\n`) produces the expected merged `constitution.md` and install.lock (SC-003). `--llm=file` writes a pending JSON containing `body_base64` and a bound `pending_id`, exits 5, and only accepts a candidate through `--accept-merged` after the pending/current derivations agree. `--llm=none` and non-TTY-default refuse in under 1 second with `key=llm-required-for-multi-source` (SC-007).

### Tests for US3

- [X] T056 [P] [US3] Integration test [tests/integration/test_assemble_multi_source.py](../../tests/integration/test_assemble_multi_source.py) covering: (a) the complete framed stdio flow from source display through `confirmed=True` and pair publication (FR-027 explicit "an integration test MUST simulate the complete framed stdio response"); (b) `--llm=file` writing the pending JSON and exiting 5; (c) `--accept-merged` acceptance with matching derivations; (d) pending/current mismatch → exit 12 `key=pending-merge-inputs-mismatch` with pending file retained; (e) `--llm=none` and non-TTY default → exit 4 `key=llm-required-for-multi-source`; (f) concealment-instruction refusal → exit 8 `key=constitution-concealment-instruction`; (g) `--accept-merged` combined with `--llm` → exit 64.
- [X] T057 [P] [US3] Unit test [tests/unit/test_stdio_protocol.py](../../tests/unit/test_stdio_protocol.py) for the ASCII framing: candidate `Content-Length: <N>\n` + exact N UTF-8 bytes → validated + displayed → separate `--haex-confirm: yes\n` sets `confirmed=True`; malformed length, wrong byte count, EOF between records, any confirmation other than the exact literal → `confirmed=False`.
- [X] T058 [P] [US3] Unit test [tests/unit/test_pending_merge.py](../../tests/unit/test_pending_merge.py) for FR-039: canonical `haex-hive-constitution-pending-v1` length-prefixed serialization; `pending_id` computed identically from (a) decoded pending JSON and (b) freshly resolved current contributions; any drift in a source's `id`/`revision`/`source`/`body` bytes → mismatch.

### Implementation for US3

- [X] T059 [P] [US3] Implement [src/haex_hive/constitution/llm.py](../../src/haex_hive/constitution/llm.py) with the `MergeLLM` protocol (`merge(contributions, task_prompt) -> MergeResult`), the `MergeResult` dataclass (per data-model.md §MergeResult — `candidate: bytes`, `confirmed: bool`; owned here because it is only produced by adapters in this module and consumed by T061), and three registered implementations: `StdioMergeLLM` (runs `validate_no_plaintext_secrets` and `validate_terminal_safe_display` on every source and final candidate before displaying it, then uses framed candidate + framed confirmation and returns `confirmed=False` on any protocol violation), `FileMergeLLM` (uses T060's canonical `serialize_pending(...)` and `derive_pending_id(...)` helpers to write pending JSON, then raises the explicitly defined normal-control-flow signal `PendingMergeWritten`; this is the sole non-`MergeResult` protocol outcome and carries no candidate), and `NoneMergeLLM` (unconditionally raises `LlmRequiredForMultiSourceError`). T061 must run `validate_no_plaintext_secrets` for an accepted-file candidate and `validate_no_concealment_instructions` for every confirmed stdio or accepted-file candidate before publication; depends on T018, T019, T025 (`ConstitutionSource` transitively via T053's contribution type), and T060.
- [X] T060 [US3] Implement pending-merge helpers in [src/haex_hive/constitution/pending.py](../../src/haex_hive/constitution/pending.py): the `PendingMerge` and `PendingContribution` dataclasses (per data-model.md §PendingMerge / §PendingContribution — owned here because they only appear in the `--llm=file` on-disk representation and are consumed by T059's `FileMergeLLM` plus T061's `--accept-merged` path), `serialize_pending(contributions, task_prompt) -> bytes` producing the FR-039 canonical byte sequence, `derive_pending_id(...)`, `load_pending(repo_root)` for phase two, and `verify_pending_matches_current(pending, freshly_resolved) -> None` raising `PendingMergeInputsMismatchError` on any drift; depends on T053.
- [X] T061 [US3] Extend [src/haex_hive/constitution/assemble.py](../../src/haex_hive/constitution/assemble.py) with `assemble_multi_source(contributions, method, accept_merged_path, ...)` that: first rejects simultaneous `--accept-merged` and `--llm` with exit 64 before any method/adapter selection; otherwise selects the phase-two `--accept-merged` path, or resolves the adapter by explicit `--llm` > `HAEX_LLM` > TTY-auto-detect; runs the FR-038 guard over every source and every serialized payload; on `stdio` invokes the adapter, requires `confirmed=True`, runs `validate_no_concealment_instructions`, and publishes through `publish_pair` with T054's post-write D15 verification callback; catches `PendingMergeWritten` from `FileMergeLLM` and returns the explicit pending-state exit 5 after its atomic pending-file write (not the pair transaction); on `--accept-merged` reads and secret-validates the candidate, decodes the pending JSON, and requires `stored_pending_id == derive_pending_id(decoded_pending) == derive_pending_id(freshly_resolved_current_contributions)` before running `validate_no_concealment_instructions` and publishing through the same post-write callback. A `PostWriteValidationError` must restore both targets through the live journal and map to exit 6; on every validation or publication failure retain the pending file. Delete `.haex-hive/constitution.merge.pending.json` only after `publish_pair` has returned successfully (after verification and journal removal), never the caller-supplied candidate path; depends on T017, T018, T019, T053, T059, T060.
- [X] T062 [US3] Extend the `haex constitution assemble` handler in [src/haex_hive/cli/constitution.py](../../src/haex_hive/cli/constitution.py) to route the multi-source path to T061, add `--llm` and `--accept-merged` flags with mutual-exclusion (exit 64), map every FR-027/FR-028/FR-038/FR-039 error to the exact exit codes 2/4/5/6/8/9/10/11/12/13 in [contracts/haex-constitution-assemble.cli.md](contracts/haex-constitution-assemble.cli.md).

**Checkpoint**: US3 is independently functional alongside US2. SC-003 and SC-007 pass; the byte-identical multi-source constitution can be pulled and verified on a second device without re-running the LLM.

---

## Phase 6: User Story 4 — `haex constitution show` (Priority: P3)

**Goal**: Read-only inspection command that verifies content-integrity before emitting output, synthesizes a source-attribution preface from `install.lock`, and refuses cleanly when preconditions are missing.

**Independent Test**: After US2 or US3 populates `.haex-hive/constitution.md` and `.haex-hive/install.lock`, `haex constitution show` prints the preface (one line per source in bytewise UTF-8 ID order with short-SHA and canonical URL), a `---` separator, and the byte-for-byte body. `--no-preface` prints only the body. Missing constitution → exit 2; missing lock → exit 3; corrupt lock → exit 4; integrity mismatch → exit 6; live journal present → exit 7.

### Tests for US4

- [X] T063 [P] [US4] Integration test [tests/integration/test_show.py](../../tests/integration/test_show.py) covering: preface + body byte-identity, `--no-preface` scripting mode, missing-constitution refusal (exit 2 `key=constitution-not-assembled`), missing-lock refusal (exit 3), install-lock schema-invalid vs. sources-not-canonical refusals (exit 4 with distinct keys), integrity-mismatch refusal (exit 6 `key=constitution-integrity-mismatch`), live-journal refusal (exit 7 `key=constitution-transaction-incomplete`).

### Implementation for US4

- [X] T064 [US4] Implement [src/haex_hive/constitution/show.py](../../src/haex_hive/constitution/show.py) `show(repo_root, *, no_preface: bool) -> None`: refuse if a live transaction journal exists (T017 has an `is_journaled` helper); load and validate `install.lock` (schema + `constitution.sources[]` uniqueness/sort — reusing T025); recompute D15 digest of `constitution.md` and compare against `content_integrity`; on a match, synthesize the "Assembled from" preface (unless `--no-preface`) followed by `---` and the byte-for-byte body; depends on T015, T017, T025.
- [X] T065 [US4] Wire the `haex constitution show` handler in [src/haex_hive/cli/constitution.py](../../src/haex_hive/cli/constitution.py) with a `--no-preface` flag and the exact exit-code mapping in [contracts/haex-constitution-show.cli.md](contracts/haex-constitution-show.cli.md).

**Checkpoint**: All four user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, cross-platform smoke, and documentation touch-ups.

- [ ] T066 [P] End-to-end quickstart validation: run every command block in [quickstart.md](quickstart.md) Path 1–4 on Linux, macOS, and Windows CI runners and record the outputs in [tests/integration/test_quickstart.py](../../tests/integration/test_quickstart.py) — this exercises SC-001 through SC-008 in one pass.
- [ ] T067 [P] SC-008 crash-safety sweep: an integration test [tests/integration/test_crash_safety.py](../../tests/integration/test_crash_safety.py) that induces a POSIX `SIGKILL` or, on Windows, terminates the child process with `Popen.kill()`/`TerminateProcess` at every FR-035 boundary (after durable journal creation and after each target replacement). For each platform path and both existing-target and absent-target starting states, assert a subsequent `haex constitution assemble` converges to either the pre-command or fully-successful state, never a mixed pair.
- [ ] T068 [P] SC-004 performance smoke: benchmark `haex migrate --dry-run` on the haex-hive self-fixture (a well-formed v1 file with the fully populated publisher clone) and assert wall-clock under 5 seconds; mark it `@pytest.mark.slow`, rely on T004's registered marker/default exclusion so plain `pytest` skips it, and require CI to include it with `pytest -o addopts="" -m slow` as specified by T005.
- [ ] T069 [P] SC-007 refusal-latency smoke: benchmark `haex constitution assemble` with `--llm=none` in a multi-source fixture and assert refusal in under 1 second.
- [ ] T070 [P] Update the [README.md](../../README.md) `haex` CLI section with installation via `pip install haex-hive` and one-line examples for the three commands defined by T029 — `haex migrate`, `haex constitution assemble`, and `haex constitution show` — pointing at [quickstart.md](quickstart.md); no marketing prose.
- [ ] T071 [P] Update the constitution memory doc set: add a pointer in [.specify/memory/constitution.md](../../.specify/memory/constitution.md) or an accompanying README noting the atom-manifest FR-022 landed alongside it, and cross-link the FR-023 self-migration commits.
- [ ] T072 Run the default test suite (`pytest -q`) and the slow selection (`pytest -q -o addopts="" -m slow`) on Linux, macOS, and Windows via the workflow from T005 and confirm every acceptance-scenario / SC-00X test passes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001–T005)**: No deps — start immediately.
- **Foundational (T006–T037)**: Depends on Setup. BLOCKS every user story.
- **US1 (T038–T049)**: Depends on Foundational; can start once Phase 2 checkpoint is met.
- **US2 (T050–T055)**: Depends on Foundational; independent of US1 code but shares fixture repo utilities.
- **US3 (T056–T062)**: Depends on US2 (extends `constitution/assemble.py` and the CLI handler introduced in T054/T055).
- **US4 (T063–T065)**: Depends on either US2 or US3 having produced install.lock + constitution.md so its integration test has inputs; source code depends only on Foundational.
- **Polish (T066–T072)**: Depends on all user stories.

### Within Each User Story

- Tests are authored first and MUST fail before implementation lands (spec.md testing mandate + plan.md §Testing).
- Models before services; services before CLI wiring.
- FR-023 self-migration commits (T047–T049) land after `haex migrate` code passes T038–T042 in a fixture repo.

### Parallel Opportunities

- Every `[P]` task inside a phase can run in parallel with other `[P]` tasks in that phase provided its dependencies are met.
- Phase 2 value-object tasks (T009–T012) and their unit tests (T032) are all independent — a small team can knock them out concurrently.
- Phase 2 model dataclasses (T022–T025) are independent files only after the shared schema loader and validator in T021 are complete.
- Phase 2 git adapters (T026–T028) are independent files.
- Every user story's tests (T038/T040/T041/T042 for US1; T050/T051/T052 for US2; T056/T057/T058 for US3; T063 for US4) can be authored in parallel.

---

## Parallel Example: Foundational Phase (Phase 2)

```bash
# Value objects — four files, no cross-deps:
Task: "Implement src/haex_hive/model/atom_id.py"           # T009
Task: "Implement src/haex_hive/model/source_url.py"        # T010
Task: "Implement src/haex_hive/model/version_constraint.py" # T011
Task: "Implement src/haex_hive/model/repo_relative_path.py" # T012

# Model dataclasses (after T021 has authored the shared schema loader and validator):
Task: "Implement src/haex_hive/model/consumer_manifest.py"  # T022
Task: "Implement src/haex_hive/model/publisher_manifest.py" # T023
Task: "Implement src/haex_hive/model/atom_manifest.py"      # T024
Task: "Implement src/haex_hive/model/install_lock.py"       # T025

# Git adapters — three files, no cross-deps:
Task: "Implement src/haex_hive/git/show.py"     # T026
Task: "Implement src/haex_hive/git/remote.py"   # T027
Task: "Implement src/haex_hive/git/revparse.py" # T028
```

## Parallel Example: US1 Test Suite

```bash
Task: "Contract test the migration table in tests/contract/test_migration_table.py"    # T038
Task: "Unit test transform in tests/unit/test_transform.py"                             # T039
Task: "Integration test haex migrate CLI in tests/integration/test_migrate.py"          # T040
Task: "Integration test preview modes in tests/integration/test_migrate_preview_modes.py" # T041
Task: "Integration test self-migration in tests/integration/test_migrate_haex_hive_self.py" # T042
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 (T001–T005).
2. Complete Phase 2 (T006–T037) — non-negotiable; every downstream task depends on it.
3. Complete Phase 3 (T038–T049).
4. **STOP and VALIDATE**: run US1 integration tests + `haex migrate --dry-run` in the repo; confirm SC-001, SC-004, SC-005 pass.
5. Land the FR-023 self-migration PR (commits A/B/C from T047–T049) and merge.

### Incremental Delivery

1. MVP as above.
2. Add US2 (T050–T055) → verify SC-002, FR-031, FR-036 → optionally cut a beta release.
3. Add US3 (T056–T062) → verify SC-003, SC-007 → second beta.
4. Add US4 (T063–T065) → verify SC-008 preface + `--no-preface` → third beta.
5. Run Phase 7 polish (T066–T072) → tag `haex-hive 2.0.0`.

### Parallel Team Strategy

- Two developers: dev A carries value objects + models + migrate; dev B carries io/transaction + safety + constitution assemble. Merge at the CLI wiring tasks (T029, T046, T055, T062, T065).
- Three developers: split by user story after Phase 2 (US1 → dev A, US2+US3 → dev B, US4 → dev C once US2 lands).

---

## Notes

- Every task in this list traces back to a specific FR / SC / User-Story acceptance scenario in [spec.md](spec.md) or a design decision (D-*) referenced through [research.md](research.md) and [data-model.md](data-model.md).
- No task introduces a dependency, framework, or abstraction beyond what plan.md §"Technical Context" already commits to (Python 3.10+ stdlib + `jsonschema`).
- [P] tasks touch different files with no incomplete dependencies in their own phase; the checkpoint lines between phases are firm gates.
- Tests are written first per US and MUST fail before implementation is merged.
- Commit each task's output eagerly with an updated checkbox; do not batch checkbox ticks across multiple tasks.
- Avoid: vague tasks, same-file conflicts across [P] tasks, cross-story code coupling that would break the "independently testable" property claimed in each user story.
