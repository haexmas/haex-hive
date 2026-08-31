# Spec 008 — Install Transaction Contract

**Status**: Draft (extracted from [Spec 007 design doc](2026-08-28-spec-007-unified-manifest-design.md) 2026-08-29 to keep the Spec 007 doc focused on the manifest-v2 architecture)
**Author**: haex-hive constitution v1.3.0 process
**Related**: [Spec 007 — Unified Manifest & harness_sources v2 design](2026-08-28-spec-007-unified-manifest-design.md);
[Constitution §Principle IV, VI](../../.specify/memory/constitution.md)

## Purpose

Spec 008 delivers `haex install` end-to-end. The requirements captured here
are load-bearing for correctness under concurrency and interruption and are
non-negotiable for the Spec 008 landing. When Spec 008 is drafted via
`/speckit-specify`, this document is its authoritative source for the
transaction contract; Spec 008's plan/tasks reference this file rather than
restating.

## Install-transaction requirements

The following rules are load-bearing for correctness under concurrency and
interruption and are non-negotiable for the Spec 008 landing:

- **Repository lock ordering**. Acquire an exclusive advisory lock at the
  device-local `$HAEX_HIVE_STATE/locks/<repo-key>/install.mutex` (or per-OS
  equivalent) **before** reading
  `.haex-hive.json`, cloning, resolving, or building the install plan. Hold
  it through recovery, staging, commit, rollback, and cleanup. Concurrent
  invocations wait or fail with the lock owner's PID, hostname, and start
  time. Ordinary `haex verify` acquires a shared/read lock so a concurrent
  install cannot present it a torn view. `haex verify --recover` is a
  modifying operation: it MUST acquire the same exclusive lock as `haex
  install` before reading the journal, and it MUST NOT first take a shared
  lock and upgrade it before replaying or rolling back a journal or changing
  any output root.
- **Journal + startup recovery**. Every filesystem mutation step is recorded
  in the device-local `install.journal` before it is executed, and the next
  `haex install` (or `haex verify --recover`) replays or rolls back an
  incomplete journal before any new plan is built. Journal state
  transitions fsync the journal file and its parent directory before
  advancing. The marker publication is the publication boundary; cleanup
  mutations after it are also journaled and idempotent. If the marker already
  verifies, recovery retains that generation and resumes cleanup only.
- **Repository-wide visibility commit**. All new bytes are written to a
  staging root next to the target (same filesystem), fsynced, and prepared as
  complete logical output-root views for `.haex-hive/`, `.claude/`, and
  `.codex/`. `.haex-hive/` is haex-owned and may use a platform primitive that
  atomically exchanges populated, same-filesystem directories. `.claude/` and
  `.codex/` are mixed-ownership roots and MUST NEVER be exchanged or renamed as
  directories. Their adapter-owned leaves are instead stored under a versioned
  generation directory and published through a stable per-adapter overlay and
  current-generation pointer (for example, a supported symlink/junction or
  adapter-managed launcher). The overlay changes only paths recorded as
  adapter-owned; it never enumerates, copies, or replaces sibling entries in
  the mixed-ownership root. A platform without an atomic pointer or stable
  overlay mechanism MUST refuse the install rather than publish a torn direct
  view. The digest for a mixed-ownership root covers only its managed overlay,
  never its unowned directory contents. After every other staged output is
  sealed, the transaction writes and fsyncs the final staged `install.lock`,
  computes the participating-root digests over those final staged bytes, and
  writes the staged `.haex-hive/visibility.json` marker last. The marker
  contains a deterministic generation ID and the digest of every participating
  output root; the `.haex-hive/` digest includes `install.lock` and excludes
  only the marker itself to avoid self-reference. Readers MUST NOT treat
  individual root exchanges or pointer replacements as publication. The
  `.haex-hive/` exchange or pointer replacement containing that final marker is
  the final publication step and publishes the generation. Journaled cleanup
  may follow but cannot change the marker or generation. Readers first load the
  marker and then verify every root's generation and digest; a missing marker
  or mixed generation is an unavailable installation, never a partially valid
  one. Recovery tests MUST cover a crash after each root publication step and a
  reinstall with non-empty output roots, including an unowned `.claude/` or
  `.codex/` file modified during staging that survives unchanged, proving that
  recovery either restores the previous marker-consistent generation or
  completes the new one before readers resume.
- **Stable staged-input reads through commit**. Plan-build captures the exact
  bytes of `.haex-hive.json`, every publisher manifest, and every atom manifest
  into a sealed plan snapshot and records their digests. Immediately before
  publishing any output, still under the install lock, the transaction reads
  the live inputs into a fresh commit snapshot, hashes those snapshot bytes,
  and compares every digest with the plan snapshot. A source identity/metadata
  change during capture is also a failure. On any mismatch the install aborts
  before the first output-root swap. Only the fresh, digest-matching commit
  snapshot is then copied into a transaction-owned immutable input snapshot and
  used for resolution and hydration; no later step re-reads live inputs. All
  supported haex input writers MUST use the same exclusive install lock, which
  prevents a coordinated mutation between the final check and the first swap.
  The conformance suite MUST cover both a changed input before the final check
  (abort) and a coordinated mutation after the final check (blocked writer).
- **Every side effect through the transaction**. The following outputs
  MUST be produced through the same staging-root+journal transaction:
  `.haex-hive/constitution.md` (Spec 007 D2), `.haex-hive/config/<atom-id>.json`
  (Spec 007 D7), every file under `.haex-hive/generated/`, and any device-local
  agent-facing copy under `.claude/`, `.codex/`, etc. that Spec 010's
  adapters emit. `install.lock` is written last, after every other output
  in the transaction has been sealed (including any deferred publisher-hook
  outputs — see Spec 007's Non-Goals "Publisher install-time outputs" clause).
- **Delete-orphans in-transaction**. The plan computes the delta between
  the previous `install.lock` `ownership.paths` set and the current planned
  ownership set. Each generated path has a versioned record containing its
  root-relative path, owning resource, current generation and digest, and
  previous-generation existence/digest data. Files owned by removed resources
  are staged for deletion through the same transaction as new outputs; a
  partial state where deleted files reappear after rollback (or new files
  persist after rollback) is not allowed. Journal pre-image records retain the
  bytes needed to restore writes and deletes, while unowned mixed-root entries
  are preserved.
- **`install.lock` computed last**. The lockfile records
  `generated_content_integrity`, every `atoms[].content_integrity`, and the
  versioned per-path `ownership.paths` set
  over the final sealed bytes actually swapped into place. Its own fsync
  precedes construction of `visibility.json`; the staged `.haex-hive/` view
  swap containing both files is the final publication step; journaled cleanup
  may follow without changing the marker or generation. Any output that could
  still mutate (native-tool outputs when they return — see Spec 007's Non-Goals
  clarifier) is sealed before `install.lock` is computed.

## Conformance suite

Spec 008's conformance suite MUST cover:

- Concurrent `haex install` invocations (one wins, the other waits or fails
  with owner detail)
- Crash recovery from every journal state
- Mid-install `.haex-hive.json` mutation (aborted at commit-time re-hash) and
  a coordinated mutation attempted after the final check (blocked by the lock)
- Rollback of a partially-applied delete-orphans plan

## `install.mutex` / `install.journal` placement

The resolved placement is the device-local state root:
`$HAEX_HIVE_STATE/locks/<repo-key>/`, alongside the content store, keeping
`.haex-hive/` fully committed content. `<repo-key>` is the lowercase
hexadecimal SHA-256 of the canonical Spec-007 repo identity. The full identity
is stored separately in `repo-identity.v1.json` for diagnostics and collision
detection; it is never used verbatim as a path segment.

The fenced-lease contract is fixed: owner token
`<pid>:<hostname>:<start_ns>:<uuid4_hex>`, 5-second heartbeat, 60-second TTL,
5-second safety margin, UTC expiry values, the same non-blocking exclusive OS
lock for recovery, unchanged-token revalidation, and atomic fencing before
replay. Existing `.haex-hive/constitution-transaction.lock` and
`.haex-hive/constitution-transaction.json` files are legacy inputs only; the
first new shared-lock operation recovers a valid legacy journal and creates no
new legacy artifact.
