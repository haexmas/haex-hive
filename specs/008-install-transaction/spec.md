# Feature Specification: Install Transaction Contract for `haex install`

**Feature Branch**: `008-install-transaction`
**Created**: 2026-08-31
**Status**: Draft
**Input**: User description: "Spec 008 delivers `haex install` end-to-end as the single consumer-side entrypoint for turning `.haex-hive.json`'s adopted atoms into their resolved, installed state on a satellite, with correctness under concurrency and interruption guaranteed. Authoritative source of requirements: [docs/plans/2026-08-29-spec-008-install-transaction-requirements.md](../../docs/plans/2026-08-29-spec-008-install-transaction-requirements.md)."

**Authoritative requirements source**: This spec's transaction invariants are extracted from [docs/plans/2026-08-29-spec-008-install-transaction-requirements.md](../../docs/plans/2026-08-29-spec-008-install-transaction-requirements.md). Where the source doc's phrasing carries the load-bearing detail, this spec references it rather than restating it verbatim, so a change to one does not silently diverge from the other. The source doc's phrases (e.g. "repository lock ordering", "journal + startup recovery", "repository-wide visibility commit") are the anchor names used below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operator installs adopted atoms with byte-perfect, atomic results (Priority: P1) 🎯 MVP

An operator has edited `.haex-hive.json` on a satellite (adding an atom, bumping a pinned revision, or removing an adoption) and runs `haex install` from that satellite's project checkout. On success, `.haex-hive/`, `.claude/`, `.codex/` and any other participating output roots reflect the new atom set exactly — no old files that should be gone, no missing files that should be present, `install.lock` reflects the final sealed bytes, and `.haex-hive/visibility.json` names the newly-published generation.

**Why this priority**: This is the MVP — without a working happy path, none of the other guarantees matter. Every downstream spec (009 hook boundary, 010 compiler, and every atom adoption in the future) requires that `haex install` works correctly on the good-weather case.

**Independent Test**: On a satellite with a valid `.haex-hive.json` naming two atoms from `github.com/haexmas/haex-hive`, run `haex install`. Verify (a) `.haex-hive/constitution.md` is the byte-for-byte assembled output; (b) `.haex-hive/install.lock` records both `atoms[].content_integrity` values over the actually-sealed bytes; (c) `.haex-hive/visibility.json` names a fresh generation ID and lists the participating roots' digests; (d) re-running `haex install` with no changes is a no-op and reports "no changes".

**Acceptance Scenarios**:

1. **Given** a satellite with `.haex-hive.json` adopting two atoms at pinned SHAs, **When** the operator runs `haex install`, **Then** all outputs listed in the source doc's "Every side effect through the transaction" section appear at their canonical paths with correct content, `install.lock` is the last file sealed, and `visibility.json` publishes the new generation with all participating-root digests present.
2. **Given** a satellite with an already-installed generation matching the current `.haex-hive.json`, **When** the operator runs `haex install` a second time, **Then** the transaction is a no-op: no file is rewritten, `install.lock` is byte-identical, and the run reports "no changes".
3. **Given** the operator changes one atom's pinned revision in `.haex-hive.json`, **When** `haex install` runs, **Then** the new revision's contributed files replace the old ones and files owned by resources that disappeared are deleted in the same transaction (see US4).

---

### User Story 2 — Concurrent installs are safely serialised (Priority: P2)

A satellite may end up running two `haex install` invocations at once — a git hook fires while the operator manually runs it, or two shell sessions race. The transaction must guarantee that exactly one installs at a time; the other either waits or refuses with a diagnostic naming the current owner (PID, hostname, start time). A concurrent `haex verify` must not observe a torn state: it either sees the pre-install generation or the post-install generation, never a mix.

**Why this priority**: Necessary for correctness on any real satellite (hooks + operator + editor extensions all share the repo). Without it, US1's outputs can be corrupted by races and the system is unusable in practice.

**Independent Test**: Start two `haex install` invocations at the same instant against the same checkout. Verify one succeeds and the other either waits for the lock or exits with a diagnostic naming the winner's PID+hostname+start-time. Verify `haex verify` run concurrently sees a single consistent generation throughout.

**Acceptance Scenarios**:

1. **Given** a `haex install` is running on process A, **When** process B invokes `haex install` on the same checkout, **Then** B either waits for A's exclusive lock or exits with a "lock owned by A (PID X, host Y, started at T)" message, per the source doc's "Repository lock ordering" clause.
2. **Given** a `haex install` is running, **When** a third-party reader loads `.haex-hive/visibility.json` and then reads the participating output roots, **Then** it sees exactly one consistent generation — every root's digest matches the marker's, or the marker is absent (installation unavailable). No mixed-generation state may be observable.
3. **Given** a `haex verify --recover` invocation, **When** it runs while any other `haex install` is in flight, **Then** it acquires the same exclusive lock as `haex install` before reading the journal — it never upgrades a shared lock to modify state.

---

### User Story 3 — Crashes and interruptions do not leave partial state (Priority: P2)

Any `haex install` invocation may crash, be killed, or lose power at any point. The next successful `haex install` (or an explicit `haex verify --recover`) must either complete the interrupted install to a valid new generation, or roll it back to the previous marker-consistent generation. At no point may a reader see a partially-applied state.

**Why this priority**: Guarantees the durability half of the transaction contract. Without it, a single power loss or Ctrl-C can turn a satellite's harness state into unrecoverable garbage — the exact failure mode `haex install` exists to prevent.

**Independent Test**: With a running `haex install` on a satellite, kill the process (SIGKILL) at each of these journal states: (a) after the exclusive lock is acquired but before any staging; (b) after staging some outputs but before `install.lock` is sealed; (c) after `install.lock` is sealed but before `visibility.json` is published; (d) after `visibility.json` is published but during post-publication cleanup. In each case, run `haex install` again and verify recovery either completes the new generation or rolls back to the previous one; after marker publication, recovery MUST retain the valid new generation and finish cleanup. Verify no reader observed a torn state at any point.

**Acceptance Scenarios**:

1. **Given** an interrupted install left an incomplete journal, **When** the operator runs `haex install` (or `haex verify --recover`), **Then** the transaction replays or rolls back the journal before building any new plan, per the source doc's "Journal + startup recovery" clause.
2. **Given** an install was interrupted mid-staging, **When** it is recovered, **Then** the previous marker-consistent generation remains intact — the participating-root digests still match `visibility.json`, and no reader observed a mixed state.
3. **Given** an install was interrupted after `install.lock` was sealed but before `visibility.json` was published, **When** it is recovered, **Then** the final `.haex-hive/` view-swap-with-marker is either completed atomically (publishing the new generation) or rolled back cleanly to the previous generation; there is no intermediate state.
4. **Given** an installed satellite whose `.claude/` or `.codex/` root contains an unowned file (a user-authored settings fragment or third-party tool output), **When** an install runs and is interrupted mid-way and later recovered, **Then** that unowned file is present, byte-identical, both before and after recovery — recovery may not touch entries not recorded in the adapter overlay.

---

### User Story 4 — Removing an atom cleans up its files in the same transaction (Priority: P3)

An operator removes an atom entry from `.haex-hive.json` (or the atom's contribution set shrinks between revisions). The next `haex install` computes the delta between the previous `install.lock` output set and the new planned output set, and stages deletions of files owned by removed resources in the same transaction as new writes. A partial rollback of this transaction never leaves files that should have been deleted, nor deletes files that should still be present.

**Why this priority**: Necessary for the system to be usable over time — without it, the tree accumulates orphans and eventually diverges from what `.haex-hive.json` says. Not needed for the very first install (all outputs are new), so it can land after US1/US2/US3.

**Independent Test**: With a satellite installed against two atoms, remove one from `.haex-hive.json` and run `haex install`. Verify the removed atom's contributed files are gone. Now interrupt an install mid-delete, recover, and verify no file that should be deleted remains and no file that should be present is missing.

**Acceptance Scenarios**:

1. **Given** an install that removes an atom compared to the previous `install.lock`, **When** `haex install` runs and completes, **Then** every file owned by the removed atom is gone from every participating output root.
2. **Given** the same delete-orphans install is interrupted mid-way, **When** recovery runs, **Then** the outcome is either fully applied (files gone, `install.lock` and `visibility.json` reflect the new generation) or fully rolled back (files still present, previous generation intact). A partial state — some deletes applied, others not — must not be observable.

---

### Edge Cases

- **Mid-install source mutation**: a supported haex writer attempts to rewrite `.haex-hive.json` while an install is running. Writers of manifest or publisher/atom input state MUST use the same exclusive install lock, so the write is refused or waits until the transaction releases its fence. The transaction MUST still use only its sealed commit snapshot after the final check; an out-of-band rewrite is not read into the current transaction and is detected by the next install. The conformance suite must exercise both the blocked-writer boundary and a changed input before the final check.
- **Fresh install on a clean checkout**: no previous `install.lock`, no journal. Transaction publishes the first-ever generation successfully.
- **Recovering an install that was performed by a different `haex` version**: version-mismatch handling in recovery is spec-worthy but out of scope for this spec's core contract — the transaction MUST at minimum refuse cleanly rather than corrupt state.
- **Mixed-ownership root that lacks an atomic-overlay mechanism on the target OS**: refuse the install rather than publish a torn direct view. Windows without Developer Mode (no symlink), and any exotic filesystem that cannot atomically point-swap, fall here.
- **The lock file is present but its owner is dead** (crashed, host rebooted, VM paused indefinitely): recovery MUST distinguish "genuinely-abandoned lock" from "live-but-slow install" via the fenced-lease contract defined in FR-010. mtime alone is insufficient.
- **Publisher-hook outputs during install**: a publisher-authored hook (Spec 009 territory) produces additional files during the transaction. Those outputs MUST be sealed before `install.lock` is computed, per the source doc's `install.lock` clause. This spec must not preclude Spec 009's hook execution model.

## Requirements *(mandatory)*

The functional requirements below are the direct spec-level statement of the invariants in the source doc. Numbering is spec-local; the source doc's clause names appear in each requirement so they trace back one-to-one.

### Functional Requirements — Transaction contract

- **FR-001** (Repository lock ordering): The install transaction MUST acquire an exclusive advisory lock BEFORE any read of `.haex-hive.json`, any clone, resolution, or plan-build, and hold it through recovery, staging, commit, rollback, and cleanup. Concurrent invocations MUST wait for the lock or exit with a diagnostic naming the owner's PID, hostname, and start time. `haex verify` MUST acquire a shared/read lock; `haex verify --recover` MUST acquire the same exclusive lock as `haex install` and MUST NOT upgrade a shared lock to modify state.

- **FR-002** (Journal + startup recovery): Every filesystem mutation step MUST be recorded in a durable journal BEFORE it is executed. A journal state transition MUST fsync both the journal file and its parent directory before advancing. The publication boundary ends when the marker is published; idempotent post-publication cleanup mutations MUST also have write-ahead journal entries. The next `haex install` (or `haex verify --recover`) MUST replay or roll back any incomplete journal before building a new plan. If the marker was already published and verifies, recovery MUST NOT roll back that generation; it resumes cleanup only.

- **FR-003** (Repository-wide visibility commit): New bytes MUST be staged next to the target (same filesystem), fsynced, and prepared as complete logical output-root views. Publication MUST occur through the mechanism the source doc's "Repository-wide visibility commit" clause specifies for each root class: for haex-owned roots (`.haex-hive/`), each staged file MUST be published with an atomic same-filesystem replacement under the journal; for mixed-ownership roots (`.claude/`, `.codex/`), an adapter-owned overlay under a versioned generation directory with a stable per-adapter current-generation pointer. The overlay MUST change only paths recorded as adapter-owned; it MUST NEVER enumerate, copy, or replace sibling entries in the mixed-ownership root. A platform lacking an atomic pointer or stable overlay mechanism for a required root MUST refuse the install.

- **FR-004** (Marker as sole publication event): The transaction MUST write and fsync `install.lock` after every other staged output has been sealed, compute participating-root digests over those final staged bytes, then write and fsync a staged `.haex-hive/visibility.json` marker containing a unique, time-based generation ID and the digest of every participating output root. Readers MUST NOT treat individual root exchanges or pointer replacements as publication. The final marker replacement MUST be the final *publication* step and is the sole publication event. Journaled, idempotent staging cleanup MAY follow it; cleanup MUST never change the marker or the published generation.

- **FR-005** (Reader visibility invariant): A reader MUST first load `visibility.json` and then verify every participating root's generation and digest. A missing marker or a mixed-generation observation MUST be treated as an unavailable installation, never as a partially-valid one. The `.haex-hive/` digest MUST exclude `install.lock` and `visibility.json`; excluding both removes the lock/marker integrity recursion while still covering every other committed output. The digest for a mixed-ownership root MUST cover only its managed overlay, never its unowned directory contents.

- **FR-006** (Stable staged-input reads through commit): Plan-build MUST capture the exact bytes of `.haex-hive.json`, every publisher manifest, and every atom manifest into a sealed plan snapshot with recorded digests. Still holding the exclusive install lock, the transaction MUST create a fresh commit snapshot immediately before the final preparation phase, re-hash it, and compare every digest with the plan snapshot. Any mismatch — including a source identity/metadata change during capture — MUST abort the install BEFORE the first output-root swap. After the comparison succeeds, the commit snapshot MUST be copied into a transaction-owned, immutable input snapshot; resolution and hydration MUST be performed from those bytes only, and no later step may re-read live inputs. All supported haex input writers MUST honor the same exclusive install lock, which prevents a coordinated mutation between the final check and the first swap. An uncoordinated external mutation cannot change the sealed bytes used by this transaction and is detected on the next install.

- **FR-007** (Every side effect through the transaction): All of the following outputs MUST be produced through the same staging-root + journal transaction: `.haex-hive/constitution.md` (Spec 007 D2), `.haex-hive/config/<atom-id>.json` (Spec 007 D7), every file under `.haex-hive/generated/`, and any device-local agent-facing copy under `.claude/`, `.codex/`, etc. that Spec 010's adapters emit. `install.lock` MUST be written LAST, after every other output in the transaction has been sealed (including any deferred publisher-hook outputs).

- **FR-008** (Delete-orphans in-transaction): The plan MUST compute the delta between the previous install lock's versioned `ownership.paths` set and the current planned ownership set. Each generated path MUST have one persisted ownership record containing its root-relative path, owning resource, current generation and content digest, plus the previous-generation existence and digest information needed to restore it. Files owned by removed resources MUST be staged for deletion through the same transaction as new writes; the plan MUST preserve unowned files in mixed-ownership roots. Both writes and deletes MUST retain their pre-images in journaled rollback records. A partial state — some deletes applied and others not, or new files persisting after rollback — MUST NOT be observable at any time.

- **FR-009** (`install.lock` content and ordering): `install.lock` MUST record `generated_content_integrity` and every `atoms[].content_integrity` computed over the final sealed bytes that were actually swapped into place. Its own fsync MUST precede construction of `visibility.json`. Any output that could still mutate (e.g. deferred native-tool outputs) MUST be sealed BEFORE `install.lock` is computed.

### Functional Requirements — Recovery contract

- **FR-010** (Stale-lease detection): The transaction MUST implement the following fenced-lease contract so a genuinely-abandoned lock can be safely reclaimed and a live-but-slow install is never wrongly recovered:
  1. At acquisition it MUST create an owner token with the exact format `<pid>:<hostname>:<start_ns>:<uuid4_hex>`, where `pid` is decimal, `hostname` matches `[A-Za-z0-9.-]{1,64}`, `start_ns` is the acquisition process's monotonic start timestamp, and `uuid4_hex` is 32 lowercase hexadecimal characters. The full token is at most 128 ASCII bytes.
  2. `install.mutex` MUST contain the token, an immutable UTC `acquired_at`, a UTC `heartbeat_at`, a reboot-safe `heartbeat_at_ns_wallclock = time.time_ns()` value, `heartbeat_interval_ns = 5_000_000_000`, `ttl_ns = 60_000_000_000`, and `safety_margin_ns = 5_000_000_000`. The owner MUST heartbeat every 5 seconds by updating and fsyncing the record in place through the locked file handle; it MUST NOT replace the lock pathname or inode. Monotonic time schedules the owner's heartbeat, while the persisted wall-clock nanoseconds are used for cross-process expiry.
  3. Recovery MUST first attempt the same non-blocking exclusive OS lock. If a live owner still holds it, recovery MUST wait or refuse, regardless of the recorded age. After acquiring it, recovery MUST read the lease, require `time.time_ns() - heartbeat_at_ns_wallclock > ttl_ns + safety_margin_ns`, then re-read the record under the exclusive handle and require the token and wall-clock heartbeat to be unchanged and still expired. Any failed revalidation MUST abort reclamation.
  4. Reclamation MUST rewrite the lease in place through the recovering process's locked file handle before replaying or rolling back. Every owner MUST revalidate its token before each mutation; a resumed process with a fenced token MUST stop without touching transaction state. `mtime` alone MUST NOT be treated as sufficient signal.

- **FR-011** (Recovery outcome discipline): The outcome of any recovery MUST be one of: (a) the interrupted install is completed to its planned new generation with a valid marker; (b) the interrupted install is rolled back and the previous generation's marker is intact. There is no third outcome. Recovery MUST NEVER produce a state where the marker names generation G but a participating root's digest differs.

- **FR-012** (Recovery preserves unowned bytes): Recovery MUST NEVER modify, restore, or delete files that are not recorded in the adapter overlay for a mixed-ownership root, nor files outside the participating output roots. An unowned file in `.claude/` or `.codex/` that survived staging MUST survive recovery byte-identically.

### Functional Requirements — Conformance suite (mandatory scenarios)

- **FR-013**: The Spec 008 conformance suite MUST cover concurrent `haex install` invocations demonstrating that one wins and the other waits or fails with owner detail (PID + hostname + start time).

- **FR-014**: The conformance suite MUST cover crash recovery from every journal state a `haex install` invocation can enter — at minimum, a crash after each of: (a) lock acquisition; (b) each staged-output seal; (c) `install.lock` fsync but before marker; (d) marker publication and before or during each post-publication cleanup step. Cases in (d) MUST prove that recovery keeps the verified new generation and resumes idempotent cleanup rather than rolling it back.

- **FR-015**: The conformance suite MUST cover a mid-install mutation of `.haex-hive.json` and prove that no output is published — a mutation before the final check aborts at the commit-time re-hash step (FR-006). It MUST also attempt a coordinated mutation after the final check and before the first swap, proving that the writer is blocked by the shared exclusive lock and that the install publishes only the immutable commit snapshot.

- **FR-016**: The conformance suite MUST cover rollback of a partially-applied delete-orphans plan (FR-008 endpoint), verifying no orphans persist and no should-persist file is deleted.

- **FR-017**: The conformance suite MUST cover a reinstall against non-empty output roots that contain unowned entries (files not recorded in the adapter overlay), and prove those entries survive unchanged.

### Functional Requirements — Constraints and interfaces

- **FR-018** (Constitution compliance): The install pipeline MUST NOT store or transport any secret material through the transaction — Principle I. Every cross-repo reference the install resolves MUST be an immutable full-SHA per Principle IV. Compiled outputs MUST NOT embed device-local absolute paths per Principle II.

- **FR-019** (Manifest as sole on-disk contract): The transaction MUST consume `.haex-hive.json` and the atom `contributes.*` / publisher `includes[]` fields from Spec 007's schema unchanged. Spec 008 MUST NOT introduce a rival on-disk state file that shadows, mirrors, or supersedes `.haex-hive.json`'s adoption record.

- **FR-020** (Downstream-spec compatibility): The transaction envelope MUST be structured so that Spec 009's `haex hook run` execution surface can plug in as an in-transaction publisher-hook mechanism without requiring changes to FR-001–FR-009. Spec 010's per-adapter output emission (Claude Code `.claude/settings.json`, Codex `.codex/config.toml`, etc.) MUST fit under FR-003's mixed-ownership overlay and FR-007's "every side effect through the transaction" clause without further Spec 008 amendment.

### Functional Requirements — Transaction artefact placement

- **FR-021** (Device-local state root): The transaction MUST place the repository-wide `install.mutex` under `$HAEX_HIVE_STATE/locks/<repo-key>/` and each checkout-scoped `install.journal` under `$HAEX_HIVE_STATE/locks/<repo-key>/checkouts/<checkout-key>/` — the same device-local state root the constitution-assembly path uses for publisher clones, with the XDG data-directory default defined by the CLI. The in-repo `.haex-hive/` directory MUST remain 100% committed content — no gitignored subpath under it, no lock or journal files inside the repo tree. `<repo-key>` MUST be the lowercase hexadecimal SHA-256 of the canonical, device-independent Spec-007 repo identity; `<checkout-key>` MUST be a device-local hash of the resolved checkout path. The full canonical identity MUST be stored separately in a state-root `repo-identity.v1.json` record for diagnostics and collision detection; credentials and path separators MUST never appear in either directory name. Multiple checkouts of the same repo on one satellite therefore share the repository lock but cannot recover one another's journal.

  The path and identity derivation MUST be provided by shared helpers used by `haex install`, `haex constitution assemble`, and `haex constitution show`. Migration from any legacy `.haex-hive/constitution-transaction.lock`/`.json` artefacts on a satellite is out of scope for Spec 008 under the project's pre-user policy: the operator regenerates by removing the legacy files and re-running `haex constitution assemble`. If a future adopter ever requires an in-place migration path, it lands under an explicit `haex migrate` verb per Principle VI v1.3.0, not as an implicit tool-side rewrite.

- **FR-022** (State-root secret discipline): `$HAEX_HIVE_STATE` MUST NOT contain any secret material (credentials, tokens, API keys, session cookies) under any circumstances — Principle I is not weakened by moving state out of the committed tree. Secret material lives exclusively in the OS keychain (macOS Keychain, Windows Credential Manager, Linux libsecret/kwallet or equivalent). `$HAEX_HIVE_STATE` MAY store keychain identity aliases (e.g. `work-github` → the name used to look up the credential in the keychain), never the credential itself.

### Key Entities

- **Install lock (`install.mutex`)** — device-local exclusive advisory lock file that gates the entire install transaction. Contains owner metadata (PID, hostname, start time, owner token) sufficient for stale-lease detection. Never synchronised across satellites.
- **Install journal (`install.journal`)** — device-local durable record of every filesystem mutation the transaction will perform, written and fsynced before each mutation. Consumed on next-invocation recovery to replay or roll back.
- **Plan snapshot** — sealed, digest-recorded copy of `.haex-hive.json`, every publisher manifest, and every atom manifest read at plan-build time. Read-only after seal.
- **Commit snapshot** — a fresh re-read of the same inputs performed immediately before publication, hashed and compared with the plan snapshot to detect mid-install mutation.
- **Staging root** — the same-filesystem directory next to each participating output root where new bytes are written and fsynced before publication.
- **Participating output root** — one of `.haex-hive/`, `.claude/`, `.codex/`, and any other Spec 010 adapter target. Each has a digest recorded in `visibility.json`.
- **Adapter overlay** — for mixed-ownership roots (`.claude/`, `.codex/`, …), a versioned generation directory holding only the adapter-owned files, plus a stable per-adapter current-generation pointer (symlink, junction, or launcher indirection depending on OS) that swaps atomically.
- **Visibility marker (`.haex-hive/visibility.json`)** — the sole publication event. Contains a unique, time-based generation ID and each participating root's digest. Written as the final publication step inside the transaction; journaled idempotent cleanup may follow without changing the marker or generation.
- **Install lockfile (`install.lock`)** — records `generated_content_integrity` and every `atoms[].content_integrity` over final sealed bytes. Written after all other transaction outputs, before `visibility.json`.
- **Ownership set (`install.lock.ownership`)** — a versioned, per-path record of the current generation's owned paths. Each record names the root-relative path and owning resource and carries the current digest plus the prior-generation existence/digest data. Journal pre-image records carry the actual rollback bytes; unowned mixed-root entries are never added to this set.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every crash point defined in FR-014's conformance suite, the recovery outcome is one of {complete-new-generation, rollback-to-previous-generation}. There is no measured case where a mixed or torn state is observable to a concurrent reader. This is verified by the conformance suite executing a scripted-kill matrix.
- **SC-002**: Two `haex install` invocations against the same checkout can never both succeed. One acquires the lock; the other either waits or exits with a diagnostic naming the winner (PID + host + start). Verified with a scripted race-start.
- **SC-003**: On an unchanged `.haex-hive.json` matching the last successful install, `haex install` writes zero bytes, updates no timestamps, and reports "no changes". Verified by comparing `stat` output before and after.
- **SC-004**: A mid-install mutation of `.haex-hive.json` (introduced by a scripted mutator between plan-build and commit-time re-hash) never results in a published new generation. Verified by the FR-015 conformance test.
- **SC-005**: On any platform lacking an atomic pointer or stable overlay mechanism for a required participating root, `haex install` refuses with a clear diagnostic before making any filesystem change. Verified by an isolation test on a filesystem where the primitive is disabled.
- **SC-006**: A satellite whose `.claude/` or `.codex/` contains files not recorded in the adapter overlay retains those files byte-identically through any successful install AND through any recovery from an interruption. Verified by the FR-017 conformance test.
- **SC-007**: `install.lock`'s recorded digests match, byte-for-byte, the sealed content actually swapped into place. Verified by hashing the on-disk outputs after publication and comparing with `install.lock`.

## Assumptions

- **Spec 007 is the on-disk manifest contract**. `.haex-hive.json`, the atom-manifest schema, and the publisher-manifest schema from Spec 007 are consumed unchanged. Any evolution needed at the manifest layer belongs in Spec 007, not here.
- **Spec 009 is downstream**. `haex hook run` (Spec 009) plugs into this transaction as a publisher-hook execution mechanism. Spec 008 does not define what runs inside a hook — only that hook outputs are sealed before `install.lock`.
- **Spec 010 is downstream**. Per-agent adapters (Claude Code `.claude/settings.json`, Codex `.codex/config.toml`, and the ≤24 platforms graphify targets today) emit their outputs under this transaction's staging + overlay contract. Spec 008 does not specify what the adapters emit — only that whatever they emit passes through FR-003 and FR-007.
- **Nix envs (Phase 3), relay (Phase 4), mobile UI (Phase 5) are out of scope**. Nothing in this spec presumes or depends on them.
- **Platform overlay primitives**. The plan phase will select concrete per-OS mechanisms — Linux/macOS same-filesystem `rename(2)` for haex-owned roots, symlink-based overlay for mixed-ownership roots where available, junctions on Windows with Developer Mode, and refusal where none of the above is available. Cross-platform verification of overlay primitives is a plan-phase deliverable, not a spec-phase decision.
- **Windows Developer Mode fallback**. When the underlying platform mechanism for a required overlay is unavailable (Windows without Developer Mode being the concrete case today), the install refuses cleanly per FR-003 and SC-005. Making Windows-without-Developer-Mode installable via a launcher indirection is a future refinement, not this spec's scope.
- **Existing `haex constitution assemble` behaviour**. Constitution assembly (Spec 007 landed) already implements a two-file durable transaction. Spec 008 generalises the same transaction discipline to the full atom-hydration surface; the constitution-assembly path becomes one participant among many rather than a separate mechanism.
