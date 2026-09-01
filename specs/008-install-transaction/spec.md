# Feature Specification: Install Transaction Contract for `haex install`

**Feature Branch**: `008-install-transaction`
**Created**: 2026-08-31
**Status**: Draft
**Input**: User description: "Spec 008 delivers `haex install` end-to-end as the single consumer-side entrypoint for turning `.haex-hive.json`'s adopted atoms into their resolved, installed state on a satellite, with correctness under concurrency and interruption guaranteed. Authoritative source of requirements: [docs/plans/2026-08-29-spec-008-install-transaction-requirements.md](../../docs/plans/2026-08-29-spec-008-install-transaction-requirements.md)."

**Authoritative requirements source**: This spec's transaction invariants are extracted from [docs/plans/2026-08-29-spec-008-install-transaction-requirements.md](../../docs/plans/2026-08-29-spec-008-install-transaction-requirements.md). Where the source doc's phrasing carries the load-bearing detail, this spec references it rather than restating it verbatim, so a change to one does not silently diverge from the other. The source doc's phrases (e.g. "repository lock ordering" and "repository-wide visibility commit") are the anchor names used below.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operator installs adopted atoms with byte-perfect, atomic results (Priority: P1) 🎯 MVP

An operator has edited `.haex-hive.json` on a satellite (adding an atom, bumping a pinned revision, or removing an adoption) and runs `haex install` from that satellite's project checkout. On success, `.haex-hive/`, `.claude/`, `.codex/` and any other participating output roots reflect the new atom set exactly — no old files that should be gone, no missing files that should be present, `install.lock` reflects the final sealed bytes, and `.haex-hive/visibility.json` names the newly-published generation.

**Why this priority**: This is the MVP — without a working happy path, none of the other guarantees matter. Every downstream spec (009 hook boundary, 010 compiler, and every atom adoption in the future) requires that `haex install` works correctly on the good-weather case.

**Independent Test**: On a satellite with a valid `.haex-hive.json` naming two atoms from `github.com/haexmas/haex-hive`, run `haex install`. Verify (a) `.haex-hive/constitution.md` is the byte-for-byte assembled output; (b) `.haex-hive/install.lock` records both atoms' `(id, source, revision, contributed_paths)`; (c) `.haex-hive/visibility.json` names a fresh generation ID and lists the participating root names; (d) re-running `haex install` with no changes is a no-op and reports "no changes".

**Acceptance Scenarios**:

1. **Given** a satellite with `.haex-hive.json` adopting two atoms at pinned SHAs, **When** the operator runs `haex install`, **Then** all outputs listed in the source doc's "Every side effect through the transaction" section appear at their canonical paths with correct content, `install.lock` is the last file sealed, and `visibility.json` publishes the new generation with all participating-root names present.
2. **Given** a satellite with an already-installed generation matching the current `.haex-hive.json`, **When** the operator runs `haex install` a second time, **Then** the transaction is a no-op: no file is rewritten, `install.lock` is byte-identical, and the run reports "no changes".
3. **Given** the operator changes one atom's pinned revision in `.haex-hive.json`, **When** `haex install` runs, **Then** the new revision's contributed files replace the old ones and files owned by resources that disappeared are deleted in the same transaction (see US4).

---

### User Story 2 — Concurrent installs are safely serialised (Priority: P2)

A satellite may end up running two `haex install` invocations at once — a git hook fires while the operator manually runs it, or two shell sessions race. The transaction must guarantee that exactly one installs at a time; the other either waits or refuses with a diagnostic naming the current owner (PID, hostname, start time). A concurrent `haex verify` must not observe a torn state: it either sees the pre-install generation or the post-install generation, never a mix.

**Why this priority**: Necessary for correctness on any real satellite (hooks + operator + editor extensions all share the repo). Without it, US1's outputs can be corrupted by races and the system is unusable in practice.

**Independent Test**: Start two `haex install` invocations at the same instant against the same checkout. Verify one succeeds and the other either waits for the lock or exits with a diagnostic naming the winner's PID+hostname+start-time. Verify `haex verify` run concurrently sees a single consistent generation throughout.

**Acceptance Scenarios**:

1. **Given** a `haex install` is running on process A, **When** process B invokes `haex install` on the same checkout, **Then** B either waits for A's exclusive lock or exits with a "lock owned by A (PID X, host Y, started at T)" message, per the source doc's "Repository lock ordering" clause.
2. **Given** a `haex install` is running, **When** a third-party reader loads `.haex-hive/visibility.json` and then reads the participating output roots, **Then** it sees an available generation only when every named root is present and every active overlay pointer names the marker's `generation_id`. A missing marker, incomplete root set, or generation mismatch during root/pointer publication is installation-unavailable; no mixed-generation state may be treated as valid.
3. **Given** a `haex verify --recover` invocation, **When** it runs while any other `haex install` is in flight, **Then** it acquires the same exclusive lock as `haex install` before inspecting the on-disk in-flight state (`<root>/`, `<root>.next/`, `<root>.prev/`) — it never upgrades a shared lock to modify state.

---

### User Story 3 — Crashes and interruptions do not leave partial state (Priority: P2)

Any `haex install` invocation may crash, be killed, or lose power at any point. The next successful `haex install` (or an explicit `haex verify --recover`) must either complete the interrupted install to a valid new generation, or roll it back to the previous marker-consistent generation. At no point may a reader see a partially-applied state.

**Why this priority**: Guarantees the durability half of the transaction contract. Without it, a single power loss or Ctrl-C can turn a satellite's harness state into unrecoverable garbage — the exact failure mode `haex install` exists to prevent.

**Independent Test**: With a running `haex install` on a satellite, kill the process (SIGKILL) at each of these in-flight states for the `.haex-hive/` root: (a) after the exclusive lock is acquired but before any staging (no `.haex-hive.next/` yet); (b) `.haex-hive.next/` fully staged and verified but before rename A; (c) between rename A and rename B (`.haex-hive.next/` present, `.haex-hive.prev/` present, `.haex-hive/` absent); (d) after rename B but before `.haex-hive.prev/` is cleaned. In each case, run `haex install` again and verify recovery either completes the new generation or restores the previous one per the R7 state table. Verify no reader observed a torn state at any point.

**Acceptance Scenarios**:

1. **Given** an interrupted install left a mid-swap in-flight state (`<root>.next/` and/or `<root>.prev/` present), **When** the operator runs `haex install` (or `haex verify --recover`), **Then** the transaction resolves that in-flight state per research §R7 (complete forward, roll back, or refuse) before building any new plan.
2. **Given** an install was interrupted mid-staging, **When** it is recovered, **Then** the previous generation remains intact and available — every participating root and active overlay pointer still names the previous marker's `generation_id`, and no reader observed a mixed state.
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

- **Mid-install source mutation**: a supported haex writer attempts to rewrite `.haex-hive.json` while an install is running. Writers of manifest or publisher/atom input state MUST use the same exclusive install lock, so the write is refused or waits until the transaction releases its fence. The transaction uses the inputs read while holding that lock; an out-of-band rewrite that ignores the lock is outside Spec 008's trusted-writer threat model. The conformance suite exercises the blocked-writer boundary.
- **Fresh install on a clean checkout**: no previous `install.lock`, no `<root>.next/` or `<root>.prev/`. Transaction publishes the first-ever generation successfully.
- **Recovering an install that was performed by a different `haex` version**: version-mismatch handling in recovery is spec-worthy but out of scope for this spec's core contract — the transaction MUST at minimum refuse cleanly rather than corrupt state.
- **Mixed-ownership root that lacks an atomic-overlay mechanism on the target OS**: refuse the install rather than publish a torn direct view. Windows without Developer Mode (no symlink), and any exotic filesystem that cannot atomically point-swap, fall here.
- **The lock file is present but its owner is dead** (crashed, host rebooted, VM paused indefinitely): recovery MUST distinguish "genuinely-abandoned lock" from "live-but-slow install" via the fenced-lease contract defined in FR-010. mtime alone is insufficient.
- **Publisher-hook outputs during install**: a publisher-authored hook (Spec 009 territory) produces additional files during the transaction. Those outputs MUST be sealed before `install.lock` is computed, per the source doc's `install.lock` clause. This spec must not preclude Spec 009's hook execution model.

## Requirements *(mandatory)*

The functional requirements below are the direct spec-level statement of the invariants in the source doc. Numbering is spec-local; the source doc's clause names appear in each requirement so they trace back one-to-one.

### Functional Requirements — Transaction contract

- **FR-001** (Repository lock ordering): The install transaction MUST acquire an exclusive advisory lock BEFORE any read of `.haex-hive.json`, any clone, resolution, or plan-build, and hold it through recovery, staging, commit, rollback, and cleanup. Concurrent invocations MUST wait for the lock or exit with a diagnostic naming the owner's PID, hostname, and start time. `haex verify` MUST acquire a shared/read lock; `haex verify --recover` MUST acquire the same exclusive lock as `haex install` and MUST NOT upgrade a shared lock to modify state.

- **FR-002** (In-flight recovery via directory-name state): The transaction MUST NOT keep a separate durable journal file. For each haex-owned output root, the in-flight state MUST be encoded in the presence or absence of three same-filesystem sibling directory names — `<root>/`, `<root>.next/`, and `<root>.prev/` — as defined by research §R1 and §R7. Mixed-ownership roots use the retained overlay generations and pointer state defined by R3. The transaction MUST fsync the parent directory after every rename that transitions between these names. The next `haex install` (or `haex verify --recover`) MUST inspect these states before building a new plan and complete forward, roll back, or refuse per the applicable recovery contract. If the fresh `<root>/` is present with schema-compatible metadata and all participating roots and active overlay pointers are available for its `generation_id`, recovery MUST NOT roll back that generation; it removes any lingering `<root>.next/`/`<root>.prev/` idempotently and continues.

- **FR-002a** (Mixed-root recovery ordering): Before the new marker is published, the installer MUST stage and validate every adapter generation, atomically exchange each active adapter pointer, and publish the new `.haex-hive/visibility.json` only after every pointer names the candidate generation. Recovery MUST validate the marker/lock cross-reference, all participating-root availability, and every active pointer before cleanup or forward completion. While the prior marker is live, a pointer naming the candidate MUST be restored to the prior generation; a pointer naming neither the prior nor candidate generation, or a missing prior marker needed for classification, MUST be refused without deleting evidence. After marker publication the marker is authoritative; matching candidate pointers are retained and obsolete generations are cleaned only after all pointers match it.

- **FR-003** (Repository-wide visibility commit): New bytes MUST be staged next to the target (same filesystem), fsynced, and prepared as complete logical output-root views. Publication MUST occur through the mechanism the source doc's "Repository-wide visibility commit" clause specifies for each root class: for haex-owned roots (`.haex-hive/`), the transaction MUST publish via the R1 directory rename-swap (verify staged `<root>.next/`, rename `<root>/` → `<root>.prev/`, rename `<root>.next/` → `<root>/`, cleanup `<root>.prev/`); for mixed-ownership roots (`.claude/`, `.codex/`), an adapter-owned overlay under a versioned generation directory with a stable per-adapter current-generation pointer. The overlay MUST change only paths recorded as adapter-owned; it MUST NEVER enumerate, copy, or replace sibling entries in the mixed-ownership root. A platform lacking an atomic pointer or stable overlay mechanism for a required root MUST refuse the install.

- **FR-004** (Marker as sole publication event): The transaction MUST prepare a staged `.haex-hive.next/visibility.json` marker containing a unique, time-based generation ID and the list of participating output-root names. The rename-swap that renames `.haex-hive.next/` → `.haex-hive/` (per FR-003) is the sole publication event. Idempotent cleanup MAY follow it but MUST never change the marker or the published generation. For no-op detection, the installer MUST compare the stable resolved output projection with the live projection while ignoring only transaction metadata (`generation_id` and `written_at`); it MUST allocate neither field or stage anything when that projection is unchanged. Per-root and per-file `content_integrity` digests are retired by the 2026-09-01 trust-git amendment (see research §R5); deterministic generation from pinned inputs provides byte identity for generated payloads.

- **FR-005** (Reader visibility invariant): A reader MUST first load `visibility.json` to determine the currently-published `generation_id`. A missing marker or a marker that names a generation whose participating-root directories are not fully in place MUST be treated as an unavailable installation, never as a partially-valid one. Before accepting the installation, the reader MUST also require every active mixed-root overlay pointer to name exactly the marker's `generation_id`; a missing pointer or a generation mismatch is unavailable. Byte-identity of generated payloads is guaranteed by deterministic generation from pinned inputs; readers that want to detect local tampering with committed content use `git status` / `git diff`. Cross-satellite reproducibility comes from the immutable-SHA revision pins in `.haex-hive.json` (Principle IV), deterministic adapters, and canonical serialization, not from fields recorded in `install.lock` or `visibility.json`.

- **FR-006** (Stable staged-input reads through commit): ~~Retired by the trust-git amendment (2026-09-01).~~ The exclusive install lock (FR-001) already prevents any supported haex writer from mutating `.haex-hive.json` or the publisher clones during an install. Publisher manifests and atom manifests are addressed by full 40-char git SHA (Principle IV) and delivered byte-identically by `git show <sha>`; there is no meaningful re-hash-under-lock check to perform against them. Detection of an uncoordinated external mutation (a rogue writer that ignores the exclusive lock) is out of scope; if a real threat surfaces, this requirement is reinstated together with the `PlanSnapshot` / `CommitSnapshot` machinery that would enforce it.

- **FR-007** (Every side effect through the transaction): All of the following outputs MUST be produced inside the same staged `<root>.next/` (haex-owned root) or the same staged overlay generation (mixed-ownership root), then published through the corresponding R1 (rename-swap) or R3 (symlink-swap) primitive: `.haex-hive/constitution.md` (Spec 007 D2), `.haex-hive/config/<atom-id>.json` (Spec 007 D7), every file under `.haex-hive/generated/`, and any device-local agent-facing copy under `.claude/`, `.codex/`, etc. that Spec 010's adapters emit. `install.lock` MUST be written LAST inside `.haex-hive.next/`, immediately before `visibility.json`, so the rename-swap commits both atomically.

- **FR-008** (Delete-orphans in-transaction): For a haex-owned root, each install MUST materialise the complete staged directory from the current resolved output set. A path contributed by an atom or other resource that is absent from that set is therefore omitted from `<root>.next/` and deleted atomically when the complete staged directory replaces `<root>`. Rollback uses the retained `<root>.prev/` directory as a whole; no per-path ownership record, content-integrity field, or rollback log is defined by Spec 008. Mixed-root ownership tracking and deletion semantics are deferred to Spec 010 until its contract is established; unowned entries in mixed-ownership roots MUST remain outside the adapter overlay and unaffected. A partial state — some deletes applied and others not, or new files persisting after rollback — MUST NOT be observable at any time.

- **FR-009** (`install.lock` content): `install.lock` MUST record the resolved atom set: `haex_hive_version`, `generated_by`, the `constitution` block (sources + assembled_by), the `atoms[]` array (id + source + revision + contributed_paths per atom), and a `visibility_marker.generation_id` cross-reference. Per-file / per-root `content_integrity` fields are retired by the 2026-09-01 trust-git amendment; git provides byte-identity for anything committed under `.haex-hive/`. `install.lock` is one of the files inside `.haex-hive.next/` and is published atomically with the whole generation via the rename-swap — there is no separate ordering constraint between it and `visibility.json` (they land together).

### Functional Requirements — Recovery contract

- **FR-010** (Stale-lease detection): The transaction MUST implement the following fenced-lease contract so a genuinely-abandoned lock can be safely reclaimed and a live-but-slow install is never wrongly recovered:
  1. At acquisition it MUST create an owner token with the exact format `<pid>:<hostname>:<start_ns>:<uuid4_hex>`, where `pid` is decimal, `hostname` matches `[A-Za-z0-9.-]{1,64}`, `start_ns` is the acquisition process's monotonic start timestamp, and `uuid4_hex` is 32 lowercase hexadecimal characters. The full token is at most 128 ASCII bytes.
  2. `install.mutex` MUST contain the token, an immutable UTC `acquired_at`, a UTC `heartbeat_at`, a reboot-safe `heartbeat_at_ns_wallclock = time.time_ns()` value, `heartbeat_interval_ns = 5_000_000_000`, `ttl_ns = 60_000_000_000`, and `safety_margin_ns = 5_000_000_000`. The owner MUST heartbeat every 5 seconds by updating and fsyncing the record in place through the locked file handle; it MUST NOT replace the lock pathname or inode. Monotonic time schedules the owner's heartbeat, while the persisted wall-clock nanoseconds are used for cross-process expiry.
  3. Recovery MUST first attempt the same non-blocking exclusive OS lock. If a live owner still holds it, recovery MUST wait or refuse, regardless of the recorded age. After acquiring it, recovery MUST read the lease, require `time.time_ns() - heartbeat_at_ns_wallclock > ttl_ns + safety_margin_ns`, then re-read the record under the exclusive handle and require the token and wall-clock heartbeat to be unchanged and still expired. Any failed revalidation MUST abort reclamation.
  4. Reclamation MUST rewrite the lease in place through the recovering process's locked file handle before replaying or rolling back. Every owner MUST revalidate its token before each mutation; a resumed process with a fenced token MUST stop without touching transaction state. `mtime` alone MUST NOT be treated as sufficient signal.

- **FR-011** (Recovery outcome discipline): For a state whose candidate generation has schema-compatible metadata and whose participating roots and active overlay pointers are available for the same `generation_id`, recovery MUST either (a) complete the interrupted install to that generation with a valid marker or (b) roll back so the previous generation's marker remains intact. Before marker publication, recovery MUST restore every candidate pointer to the prior marker generation; after marker publication, recovery MUST retain every pointer matching the authoritative marker. For an unavailable, schema-invalid, or unclassifiable state, recovery MUST refuse with a diagnostic, preserve the evidence, and MUST NOT publish or claim an available generation. Recovery MUST NEVER produce a state where the marker names generation G while a participating root is missing or an active overlay pointer names another generation.

- **FR-012** (Recovery preserves unowned bytes): Recovery MUST NEVER modify, restore, or delete files that are not recorded in the adapter overlay for a mixed-ownership root, nor files outside the participating output roots. An unowned file in `.claude/` or `.codex/` that survived staging MUST survive recovery byte-identically.

### Functional Requirements — Conformance suite (mandatory scenarios)

- **FR-013**: The Spec 008 conformance suite MUST cover concurrent `haex install` invocations demonstrating that one wins and the other waits or fails with owner detail (PID + hostname + start time).

- **FR-014**: The conformance suite MUST cover crash recovery from every legal in-flight state a `haex install` invocation can produce for one participating root — at minimum, a crash after each of: (a) lock acquisition (nothing staged); (b) `<root>.next/` fully staged and metadata-validated but before rename A; (c) between rename A and rename B (`<root>.next/` present, `<root>.prev/` present, `<root>/` absent); (d) after rename B but before `<root>.prev/` cleanup. Case (c) MUST prove that recovery completes forward per §R7 and the resulting `<root>/` has a schema-compatible marker with available, generation-compatible participating roots; case (d) MUST prove that recovery removes `<root>.prev/` without touching the new `<root>/`.

- **FR-015**: The conformance suite MUST cover a coordinated mutation attempt of `.haex-hive.json` while install holds the exclusive lock and prove that the writer waits or is refused. The install MUST publish only the inputs it read while holding that lock. Out-of-band mutation that ignores the lock is outside Spec 008's trusted-writer threat model.

- **FR-016**: The conformance suite MUST cover rollback of a partially-applied delete-orphans plan (FR-008 endpoint), verifying no orphans persist and no should-persist file is deleted.

- **FR-017**: The conformance suite MUST cover a reinstall against non-empty output roots that contain unowned entries (files not recorded in the adapter overlay), and prove those entries survive unchanged.

### Functional Requirements — Constraints and interfaces

- **FR-018** (Constitution compliance): The install pipeline MUST NOT store or transport any secret material through the transaction — Principle I. Every cross-repo reference the install resolves MUST be an immutable full-SHA per Principle IV. Compiled outputs MUST NOT embed device-local absolute paths per Principle II.

- **FR-019** (Manifest as sole on-disk contract): The transaction MUST consume `.haex-hive.json` and the atom `contributes.*` / publisher `includes[]` fields from Spec 007's schema unchanged. Spec 008 MUST NOT introduce a rival on-disk state file that shadows, mirrors, or supersedes `.haex-hive.json`'s adoption record.

- **FR-020** (Downstream-spec compatibility): The transaction envelope MUST be structured so that Spec 009's `haex hook run` execution surface can plug in as an in-transaction publisher-hook mechanism without requiring changes to FR-001–FR-009. Spec 010's per-adapter output emission (Claude Code `.claude/settings.json`, Codex `.codex/config.toml`, etc.) MUST fit under FR-003's mixed-ownership overlay and FR-007's "every side effect through the transaction" clause without further Spec 008 amendment.

### Functional Requirements — Transaction artefact placement

- **FR-021** (Device-local state root): The transaction MUST place the repository-wide `install.mutex` under `$HAEX_HIVE_STATE/locks/<repo-key>/` — the same device-local state root the constitution-assembly path uses for publisher clones, with the XDG data-directory default defined by the CLI. The in-repo `.haex-hive/` directory MUST remain 100% committed content — no gitignored subpath under it, no lock file inside the repo tree. No transaction journal file is written under the state root or inside the repo tree; the in-flight recovery state lives entirely in the same-filesystem sibling directories `<root>.next/` and `<root>.prev/` beside each participating output root (see FR-002 and research §R1/§R7). `<repo-key>` MUST be the lowercase hexadecimal SHA-256 of the canonical, device-independent Spec-007 repo identity. The full canonical identity MUST be stored separately in a state-root `repo-identity.v1.json` record for diagnostics and collision detection; credentials and path separators MUST never appear in the directory name. Multiple checkouts of the same repo on one satellite therefore share the repository lock; each checkout's in-flight state lives beside its own participating output roots.

  The path and identity derivation MUST be provided by shared helpers used by `haex install`, `haex constitution assemble`, and `haex constitution show`. Transaction state uses only the device-local paths defined above; schema migration of versioned state remains out of scope for Spec 008 and, if ever needed, lands under an explicit `haex migrate` verb per Principle VI v1.3.0.

- **FR-022** (State-root secret discipline): `$HAEX_HIVE_STATE` MUST NOT contain any secret material (credentials, tokens, API keys, session cookies) under any circumstances — Principle I is not weakened by moving state out of the committed tree. Secret material lives exclusively in the OS keychain (macOS Keychain, Windows Credential Manager, Linux libsecret/kwallet or equivalent). `$HAEX_HIVE_STATE` MAY store keychain identity aliases (e.g. `work-github` → the name used to look up the credential in the keychain), never the credential itself.

### Key Entities

- **Install lock (`install.mutex`)** — device-local exclusive advisory lock file that gates the entire install transaction. Contains owner metadata (PID, hostname, start time, owner token) sufficient for stale-lease detection. Never synchronised across satellites.
- **In-flight recovery state** — for each haex-owned output root, the presence or absence of three same-filesystem sibling directory names: `<root>/` (live), `<root>.next/` (staged, metadata-validated, awaiting swap), `<root>.prev/` (pre-image retained during the swap). Mixed-ownership roots use the retained overlay generations and pointers defined by R3. This state replaces the earlier durable-journal file; recovery inspects the applicable state and dispatches per research §R7/R3.
- ~~**Plan snapshot**~~ / ~~**Commit snapshot**~~ — Retired by the 2026-09-01 trust-git amendment together with FR-006. The exclusive install lock plus git's content-addressed publisher-clone delivery replace the re-hash-under-lock defence-in-depth these entities carried.
- **Staging root** — `.next` beside a haex-owned output root, or a versioned adapter overlay generation for a mixed-ownership root; new bytes are written and fsynced there before publication.
- **Participating output root** — one of `.haex-hive/`, `.claude/`, `.codex/`, and any other Spec 010 adapter target. Each is named in `visibility.json` and must be available for its published `generation_id`.
- **Adapter overlay** — for mixed-ownership roots (`.claude/`, `.codex/`, …), a versioned generation directory holding only the adapter-owned files, plus a stable per-adapter current-generation pointer (symlink, junction, or launcher indirection depending on OS) that swaps atomically.
- **Visibility marker (`.haex-hive/visibility.json`)** — the sole publication event. Contains a unique, time-based generation ID and the list of participating output-root names. No per-root `content_integrity` per the 2026-09-01 trust-git amendment. Made visible by the `.haex-hive` rename-swap after mixed-root pointers (Spec 010) have been exchanged; idempotent cleanup may follow without changing the marker or generation.
- **Install lockfile (`install.lock`)** — records the resolved atom set: `haex_hive_version`, `generated_by`, the constitution block (sources + assembled_by), the `atoms[]` array (id + source + revision + contributed_paths), and a `visibility_marker.generation_id` cross-reference. No `content_integrity` fields per the 2026-09-01 trust-git amendment. Published as one of the files inside `.haex-hive.next/`; the rename-swap that lands `.haex-hive/` commits it atomically with `constitution.md` and `visibility.json`.
- ~~**Ownership set (`install.lock.ownership`)**~~ — Retired by the 2026-09-01 trust-git amendment. Delete-orphan semantics under R1's rename-swap are implicit (removed atom files simply do not appear in `.haex-hive.next/`); explicit per-path ownership records were needed only for the retired mixed-root overlay + digest verification path (Spec 010 will reintroduce whatever ownership tracking mixed roots require).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every crash point defined in FR-014's conformance suite, the recovery outcome is one of {complete-new-generation, rollback-to-previous-generation}. There is no measured case where a mixed or torn state is observable to a concurrent reader. This is verified by the conformance suite executing a scripted-kill matrix.
- **SC-002**: Two `haex install` invocations against the same checkout can never both succeed. One acquires the lock; the other either waits or exits with a diagnostic naming the winner (PID + host + start). Verified with a scripted race-start.
- **SC-003**: On an unchanged `.haex-hive.json` matching the last successful install, `haex install` writes zero bytes, updates no timestamps, and reports "no changes". Verified by comparing `stat` output before and after.
- **SC-004**: A coordinated mutation attempt of `.haex-hive.json` cannot change the inputs of an install holding the exclusive lock. Verified by the FR-015 conformance test.
- **SC-005**: On any platform lacking an atomic pointer or stable overlay mechanism for a required participating root, `haex install` refuses with a clear diagnostic before making any filesystem change. Verified by an isolation test on a filesystem where the primitive is disabled.
- **SC-006**: A satellite whose `.claude/` or `.codex/` contains files not recorded in the adapter overlay retains those files byte-identically through any successful install AND through any recovery from an interruption. Verified by the FR-017 conformance test.
- **SC-007**: ~~Retired by the trust-git amendment (2026-09-01)~~ — `install.lock` no longer records content digests, so there is nothing to verify against.

## Assumptions

- **Spec 007 is the on-disk manifest contract**. `.haex-hive.json`, the atom-manifest schema, and the publisher-manifest schema from Spec 007 are consumed unchanged. Any evolution needed at the manifest layer belongs in Spec 007, not here.
- **Spec 009 is downstream**. `haex hook run` (Spec 009) plugs into this transaction as a publisher-hook execution mechanism. Spec 008 does not define what runs inside a hook — only that hook outputs are sealed before `install.lock`.
- **Spec 010 is downstream**. Per-agent adapters (Claude Code `.claude/settings.json`, Codex `.codex/config.toml`, and the ≤24 platforms graphify targets today) emit their outputs under this transaction's staging + overlay contract. Spec 008 does not specify what the adapters emit — only that whatever they emit passes through FR-003 and FR-007.
- **Nix envs (Phase 3), relay (Phase 4), mobile UI (Phase 5) are out of scope**. Nothing in this spec presumes or depends on them.
- **Platform overlay primitives**. The plan phase will select concrete per-OS mechanisms — Linux/macOS same-filesystem `rename(2)` for haex-owned roots, symlink-based overlay for mixed-ownership roots where available, junctions on Windows with Developer Mode, and refusal where none of the above is available. Cross-platform verification of overlay primitives is a plan-phase deliverable, not a spec-phase decision.
- **Windows Developer Mode fallback**. When the underlying platform mechanism for a required overlay is unavailable (Windows without Developer Mode being the concrete case today), the install refuses cleanly per FR-003 and SC-005. Making Windows-without-Developer-Mode installable via a launcher indirection is a future refinement, not this spec's scope.
- **Existing `haex constitution assemble` behaviour**. Constitution assembly (Spec 007 landed) already implements a two-file durable transaction. Spec 008 generalises the same transaction discipline to the full atom-hydration surface; the constitution-assembly path becomes one participant among many rather than a separate mechanism.
