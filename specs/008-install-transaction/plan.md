# Implementation Plan: Install Transaction Contract for `haex install`

**Branch**: `008-install-transaction` | **Date**: 2026-08-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/008-install-transaction/spec.md`
**Authoritative requirements source**: [docs/plans/2026-08-29-spec-008-install-transaction-requirements.md](../../docs/plans/2026-08-29-spec-008-install-transaction-requirements.md)

## Summary

Deliver `haex install` end-to-end as the single consumer-side entrypoint for turning `.haex-hive.json`'s adopted atoms into their resolved, installed state on a satellite, with correctness under concurrency and interruption guaranteed. The invariants come from the pre-extracted transaction contract; this plan chooses the concrete Python-level mechanisms and file layouts that implement them and reserves specific extension points for Spec 009 (hook boundary) and Spec 010 (compiler + agent adapters).

Technical approach (from research): extend the existing Python 3.10+ stdlib-first `haex` CLI (Spec 007) with a new `haex install` subcommand plus supporting modules under `src/haex_hive/install/`. Reuse the durable-journal + atomic-write primitives already present in `src/haex_hive/io/` for constitution assembly rather than parallel-implementing them — the constitution assemble path becomes the first participant of a generalised install transaction. Device-local transaction artefacts (`install.mutex`, `install.journal`) live under `$HAEX_HIVE_STATE/locks/<repo-identity>/` per FR-021; `<repo-identity>` uses the Spec-007 identity, filesystem-safed by percent-encoding path-unsafe characters. Same-filesystem staging next to each output root; per-file `os.replace()` for atomic file publication; visibility marker publication is the final atomic file write in the journal. Mixed-ownership overlay uses OS-native pointer primitives (POSIX symlink, Windows directory junction); refusal on platforms lacking a supported primitive per FR-003.

## Technical Context

**Language/Version**: Python 3.10+ (matches Spec 007's baseline).
**Primary Dependencies**: `jsonschema>=4.18` (already in Spec 007), Python stdlib for everything else — `json`, `hashlib`, `pathlib`, `os` (`replace`, `fsync`, `open`), `fcntl` (POSIX exclusive advisory lock), `msvcrt` (Windows exclusive advisory lock), `subprocess` (for `git show`, already used by Spec 007), `dataclasses`, `contextlib`, `secrets` (for owner-token generation). No new external dependency.
**Storage**: Filesystem-only. Reads and writes: `.haex-hive.json` (input, Spec 007 schema), publisher-cloned git objects under `$HAEX_HIVE_STATE/repos/<clone-hash>/` (input, Spec 007's convention), staged bytes under `<root>.staging.<gen>/` siblings of each participating output root, and the participating output roots themselves (`.haex-hive/`, `.claude/`, `.codex/`, plus any Spec 010 adapter roots). Device-local: `install.mutex` and `install.journal` under `$HAEX_HIVE_STATE/locks/<repo-identity>/` per FR-021.
**Testing**: `pytest`. Contract tests cover journal schema, visibility marker schema, and `install.lock` v2 schema. Integration tests exercise `haex install` end-to-end against fixture repos on a real filesystem with `$HAEX_HIVE_STATE` redirected to a tmpdir. The FR-013–FR-017 conformance suite is a dedicated pytest subpackage.
**Target Platform**: Linux, macOS, Windows. Windows requires Developer Mode for symlink-based mixed-ownership overlay; Windows without Developer Mode falls back to directory junctions (native, no elevation) where the overlay target is a directory; per-file overlays are refused per FR-003 on Windows-non-DevMode until a launcher-indirection scheme lands in a future revision.
**Project Type**: Single-project Python CLI (unchanged from Spec 007). New subcommand + modules; no restructure.
**Performance Goals**: `haex install` completes under 3 seconds on an unchanged state (SC-003 idempotent no-op path). Full install with ≤10 atoms and ≤50 output files completes under 30 seconds on a warm satellite. Lock acquisition returns owner detail under 200 ms on a busy checkout.
**Constraints**: Deterministic output (byte-identical across runs on identical inputs; digests match `install.lock`). Cross-platform correctness with no OS-specific filesystem primitives outside `os.replace`, `os.fsync`, `fcntl.flock`/`msvcrt.locking`, and OS-specific pointer primitives selected per platform (`os.symlink`, Windows junction via `mklink /J` or `CreateJunction`). No plaintext secrets in any staged output, journal entry, or lockfile row (Principle I; runtime scan mirrors Spec 007's fail-closed guard). Every publication is atomic-per-file; the visibility marker's `.haex-hive/` view swap is the sole publication event; readers verify marker + digests before treating a root as available.
**Scale/Scope**: Per-repo tool. A consumer's `.haex-hive.json` v2 typically declares 1–10 atom entries; ≤50 output files per install for haex-hive's own self-adoption. Participating output roots: `.haex-hive/`, plus optional `.claude/` and `.codex/` overlays populated by Spec 010 adapters when they land — the transaction envelope accepts arbitrary many roots without hard limit.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version at plan time: **1.3.0** (ratified 2026-08-26, last amended 2026-08-29).

| Principle | Status | Justification |
|---|---|---|
| I. No Secrets in Git (NON-NEGOTIABLE) | PASS | The install pipeline never accepts, transports, or writes secret material. `$HAEX_HIVE_STATE` per FR-022 explicitly excludes secrets; keychain interaction is by identity alias only. Journal entries and `install.lock` rows are scanned by the same fail-closed plaintext-secret guard used in Spec 007 before any fsync. |
| II. No Local Absolute Paths in Versioned Config (NON-NEGOTIABLE) | PASS | Every path recorded in `install.lock` is repo-relative (POSIX with `/`). `$HAEX_HIVE_STATE` is device-local, resolved per-OS at runtime, never versioned. `.haex-hive/visibility.json` records only repo-relative output-root names plus digests. |
| III. Project Identity Is Device-Independent (NON-NEGOTIABLE) | PASS | `<repo-identity>` in the state root path (FR-021) uses the Spec-007 identity (git remote URL → reverse-DNS or `.harness-id`), never a satellite-specific path. Multiple checkouts of the same repo on one satellite collide safely on the same lock. |
| IV. Cross-Repo References Pin Immutable Revisions (NON-NEGOTIABLE) | PASS | The install resolves every atom through Spec 007's `atoms[].revision` full-SHA. FR-006's plan/commit snapshot pair re-verifies bytes against those SHAs before publication; a source drift aborts the install. Non-SHA references are rejected at input validation, matching Spec 007. |
| V. External Sources Are Opt-in Per Project (NON-NEGOTIABLE) | PASS | `haex install` refuses cleanly when `.haex-hive.json` is missing or its `atoms[]` is empty — the existing Spec 007 refusal path is reused. The install pipeline never inherits from sources not in the allowlist. |
| VI. Self-Modifying Instructions Are Always Review-Gated (NON-NEGOTIABLE) | PASS | `haex install` writes device-local state and staged output through the transaction; it does not rewrite `.haex-hive.json`, `constitution.md`, or any versioned config file in place. Constitution assembly still flows through `haex constitution assemble`'s `--llm=file` review gate (Spec 007). Schema migrations remain under `haex migrate` (Principle VI v1.3.0). |
| VII. Relay Unavailability Never Blocks Local Work (NON-NEGOTIABLE) | PASS | `haex install` is fully offline against local git objects; no Nostr-relay code path in Spec 008. |
| VIII. No Concealment Instructions in Agent Output (NON-NEGOTIABLE) | PASS | `haex install` produces operator-facing diagnostics (lock owner detail, refusal reasons, unowned-file summaries) and no agent-consumable prose. The R7 concealment-instruction guard from Spec 007 remains in force for any constitution-adjacent output that could reach a downstream agent. |

**Result**: Zero violations. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/008-install-transaction/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # /speckit-specify output
├── research.md          # Phase 0 output (/speckit-plan)
├── data-model.md        # Phase 1 output (/speckit-plan)
├── quickstart.md        # Phase 1 output (/speckit-plan)
├── contracts/           # Phase 1 output (/speckit-plan)
│   ├── install-lock.v2.schema.json     # Extension of Spec 007's install-lock schema
│   ├── install-journal.v1.schema.json  # Durable journal entry schema
│   ├── visibility-marker.v1.schema.json # .haex-hive/visibility.json schema
│   ├── owner-token.v1.md               # Fenced-lease owner-token format
│   └── haex-install.cli.md             # CLI surface
├── checklists/
│   └── requirements.md  # /speckit-specify output (already present)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

Single-project Python CLI extension. Reuses existing `src/haex_hive/` package; adds a subcommand and supporting modules. No restructure of Spec 007's landed layout.

```text
src/
└── haex_hive/
    ├── cli/
    │   ├── main.py                    # extend: register `install` subcommand
    │   └── install.py                 # NEW: `haex install` handler
    ├── install/                        # NEW: transaction pipeline
    │   ├── __init__.py
    │   ├── plan.py                    # plan-build (FR-006 plan snapshot)
    │   ├── commit_snapshot.py         # commit-time re-read + digest match
    │   ├── stage.py                   # staged-root writer (FR-003)
    │   ├── overlay.py                 # mixed-ownership overlay primitives (FR-003)
    │   ├── visibility.py              # marker computation + publication (FR-004, FR-005)
    │   ├── lock.py                    # exclusive advisory lock + fenced-lease (FR-001, FR-010)
    │   ├── journal.py                 # durable journal + recovery (FR-002, FR-011)
    │   ├── delta.py                   # delete-orphans delta computation (FR-008)
    │   ├── digest.py                  # per-root Merkle-tree digest (FR-005)
    │   └── errors.py                  # install-specific HaexError subclasses
    ├── io/
    │   ├── atomic.py                  # existing (Spec 007) — reused for per-file writes
    │   ├── writer_lock.py             # existing (Spec 007) — generalised for install lock
    │   └── transaction.py             # existing (Spec 007) — extended for multi-file plans
    └── model/
        └── install_lock.py            # NEW: install.lock v2 dataclass + serializer

tests/
└── install/                            # NEW: pytest subpackage
    ├── contract/
    │   ├── test_install_lock_schema.py
    │   ├── test_journal_schema.py
    │   ├── test_visibility_marker_schema.py
    │   └── test_owner_token_format.py
    ├── integration/
    │   ├── test_happy_path.py         # US1
    │   ├── test_idempotent_no_op.py   # SC-003
    │   └── test_delete_orphans.py     # US4
    ├── conformance/                    # FR-013–FR-017 conformance suite
    │   ├── test_concurrent_installs.py
    │   ├── test_crash_matrix.py       # 4+ journal-state kills
    │   ├── test_mid_install_mutation.py
    │   ├── test_partial_delete_rollback.py
    │   └── test_unowned_files_survive.py
    └── unit/
        ├── test_plan_snapshot_digests.py
        ├── test_overlay_primitives.py
        ├── test_fenced_lease.py
        └── test_delta_computation.py
```

**Structure Decision**: Reuse Spec 007's existing `src/haex_hive/` package. All new install machinery lives under `src/haex_hive/install/` as a self-contained subpackage. Existing `io/atomic.py`, `io/writer_lock.py`, and `io/transaction.py` are extended (not duplicated) so that constitution assemble's transaction becomes a special-case single-file participant of the generalised install transaction. Test tree mirrors the existing `tests/` layout; conformance suite is a dedicated pytest subpackage under `tests/install/conformance/` because those tests exercise crash-injection matrices and take longer.

## Phase 0 — Research summary

Complete details in [research.md](./research.md). Load-bearing decisions:

1. **Atomic per-file publication**: `os.replace(src, dst)` on all three OSes. On Linux/macOS it is `rename(2)` — atomic if same filesystem. On Windows it is `MoveFileExW(..., MOVEFILE_REPLACE_EXISTING)`. No exotic directory-exchange primitive (`renameat2(RENAME_EXCHANGE)`, `renamex_np(RENAME_SWAP)`) is required — the transaction sequences per-file replaces via the journal; the final `.haex-hive/visibility.json` write is one `os.replace()` and constitutes the sole publication event (FR-004).
2. **Same-filesystem staging**: staged bytes live at `<root>.staging.<gen>/…` next to each participating output root, guaranteeing `os.replace()` stays on the same filesystem (device number preserved).
3. **Mixed-ownership overlay** for `.claude/`, `.codex/`, and future Spec 010 adapter roots:
   - **Directory-scoped overlay** (e.g. `.claude/skills/`, `.claude/agents/`) — POSIX: `os.symlink()`. Windows: directory junction via `mklink /J`. Both work without elevation on their respective platforms. This is the MVP mechanism.
   - **File-scoped overlay** (e.g. `.claude/settings.json`) — POSIX: `os.symlink()`. Windows without Developer Mode: **refused** per FR-003. Launcher-indirection is a future revision; not in Spec 008 scope.
   - **Overlay owner-set enumeration** is read from `install.lock`'s per-root `overlay_paths` field. The publication step touches exactly those paths and never enumerates siblings, per FR-003.
4. **Fenced-lease numeric contract** (FR-010):
   - **Owner token format**: `<pid>:<hostname>:<start_ns>:<uuid4>` — pid + hostname + monotonic-start-nanoseconds + random UUID4. All fields are ASCII-safe; total length ≤ 128 bytes. Uniqueness is guaranteed by UUID4; the other fields are for operator diagnostics on lock conflict.
   - **Heartbeat cadence**: 5-second refresh interval. The lock owner rewrites the `heartbeat_at_ns` field of `install.mutex` every 5 seconds via a background thread.
   - **TTL**: 60 seconds — 12× the heartbeat interval, sized for the worst case of a satellite pausing under GC / VM freeze / spinning-rust IO stalls without wrongly recovering a live install.
   - **Revalidation ordering**: recovery first reads `install.mutex`, waits until `now_ns - heartbeat_at_ns > TTL`, then atomically opens `install.mutex` for read-modify-write, re-verifies the owner token is unchanged and the heartbeat is still stale, and only then reclaims the lease.
   - `mtime` is never treated as sufficient signal; the fenced token+heartbeat pair is the sole ownership evidence, per FR-010.
5. **Per-root digest scheme** (FR-005):
   - **Algorithm**: SHA-256, matches Spec 007's `content_integrity` field format.
   - **Normalisation per root**: enumerate the root's owned paths in POSIX-byte-sorted order; for each path, compute `SHA-256(bytes-of-file)`; concatenate `<path>:<hex-digest>\n` for each; final digest is `SHA-256` of that concatenation.
   - **Mixed-ownership root**: enumerate ONLY the overlay-owned paths recorded in `install.lock`, never sibling entries.
   - **`.haex-hive/` root**: digest covers every file under `.haex-hive/` EXCEPT `visibility.json` itself (to avoid self-reference), per FR-005. `install.lock` is included in that digest.
   - **Emission format**: `sha256-<base64url(digest)>`, matching Spec 007's SRI-style representation.
6. **Lock primitive selection**: POSIX `fcntl.flock(LOCK_EX | LOCK_NB)` on Linux/macOS; Windows `msvcrt.locking(fd, LK_NBLCK, 1)` on Windows. Both non-blocking so lock conflict returns the owner-token payload immediately for the "who has the lock" diagnostic.
7. **Journal replay semantics**: journal is append-only, entries are one JSON-per-line, each entry ends with a SHA-256 tail hash of `<line-content>\n<prev-tail-hash>` for tamper-detection. On recovery, replay forwards from the last committed marker or roll back to the last known-good marker generation.

## Phase 1 — Design outputs

- **[data-model.md](./data-model.md)** — dataclass shapes for `PlanSnapshot`, `CommitSnapshot`, `JournalEntry`, `VisibilityMarker`, `InstallLock`, `OwnerToken`; relationships between them; state transitions of a running install.
- **[contracts/install-lock.v2.schema.json](./contracts/install-lock.v2.schema.json)** — extends Spec 007's `install-lock.v2` schema with `overlay_paths` per root, `visibility_marker` block, and per-root `content_integrity` map.
- **[contracts/install-journal.v1.schema.json](./contracts/install-journal.v1.schema.json)** — JSON-per-line schema for `install.journal` entries.
- **[contracts/visibility-marker.v1.schema.json](./contracts/visibility-marker.v1.schema.json)** — `.haex-hive/visibility.json` schema with `generation_id`, per-root `content_integrity`, `install_lock_content_integrity`.
- **[contracts/owner-token.v1.md](./contracts/owner-token.v1.md)** — narrative doc for the fenced-lease owner token format, since it's a small-enough contract to not need JSON schema.
- **[contracts/haex-install.cli.md](./contracts/haex-install.cli.md)** — CLI surface for `haex install`: flags, exit codes, diagnostic messages, refusal semantics.
- **[quickstart.md](./quickstart.md)** — operator-facing walkthrough: from a fresh satellite with `.haex-hive.json` adopted, install two atoms; observe the transaction artefacts; interrupt and recover; verify concurrent-install refusal.

## Downstream-spec compatibility (FR-020)

- **Spec 009 (Hook Boundary)**: publisher hooks execute inside the install transaction, between plan-build and commit-snapshot phases. Hook outputs stage into the same `<root>.staging.<gen>/` tree as native atom outputs; the journal records hook-step boundaries so recovery can re-run or roll back a hook cleanly. Spec 009 will land the sandbox + invocation semantics; Spec 008's transaction envelope reserves the extension point without changes to FR-001–FR-009.
- **Spec 010 (Compiler + Agent Adapters)**: per-agent adapters emit their outputs (e.g. `.claude/settings.json`, `.codex/config.toml`, per-tool prose files) as native install outputs. Each adapter declares its `overlay_paths` at plan-build time; Spec 008 records those in `install.lock` and enforces the "touch only overlay-owned paths" invariant. Spec 010 will land the adapter-loading mechanism and the per-adapter emission code; Spec 008 does not need to know what each adapter emits.

## Re-check gate

Re-evaluate Constitution Check after Phase 1 outputs are complete. If Phase 1's contracts introduce a principle violation (e.g. an accidental absolute path in the visibility marker schema, or a journal entry format that could carry a secret), block Phase 2 and revise.
