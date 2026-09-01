# Phase 0 Research: Install Transaction Contract for `haex install`

**Feature**: Spec 008 — Install Transaction Contract
**Date**: 2026-08-31
**Purpose**: Resolve every load-bearing implementation decision the plan reserved as "chosen in research". Each section below records the decision, the rationale, and the alternatives considered. Where a decision has a residual risk, that risk is called out explicitly.

---

## R1. Atomic per-file publication primitive across OSes

**Decision**: Use `os.replace(src, dst)` for every file publication step. Sequence per-file replacements via the durable journal (see R7). The visibility marker publication is one final `os.replace()` call and is the sole publication event (FR-004). No directory-exchange primitive is part of this contract.

**Rationale**:
- Linux/macOS: `os.replace()` calls `rename(2)` — atomic when `src` and `dst` are on the same filesystem, replacing the target if present.
- Windows: `os.replace()` calls `MoveFileExW(..., MOVEFILE_REPLACE_EXISTING)` — atomic for files with an existing target; documented as such in the Win32 API.
- Same-filesystem guarantee is preserved by staging bytes into `<root>.staging.<gen>/` siblings of each participating output root (see R2).
- fsync of parent directory after each replace on POSIX (`os.fsync(os.open(parent, os.O_RDONLY))`); Windows uses `FlushFileBuffers` on the file handle before rename per Spec 007's proven durability contract.

**Alternatives considered**:
- **`renameat2(RENAME_EXCHANGE)`** (Linux ≥ 3.15) / **`renamex_np(RENAME_SWAP)`** (macOS ≥ 10.13) for atomic directory-swap. Rejected: requires filesystem support (not all ext4 configurations, not tmpfs on older kernels; not portable to Windows). The per-file replace + journal approach reaches the same outcome without a filesystem-specific dependency.
- **Copy-and-truncate**: not atomic; a reader can observe a torn file. Rejected — violates FR-005.
- **Write-then-hardlink-swap**: works but adds complexity and doesn't buy anything over `os.replace()` on same filesystem. Rejected.

**Residual risk**: `os.replace()` on Windows for a file being read by another process fails with `ERROR_SHARING_VIOLATION`. If a downstream agent CLI holds an open handle on `.haex-hive/constitution.md`, the swap fails. Mitigation: retry with bounded backoff; if still failing, refuse the install with a diagnostic naming the holding process (via `handle.exe` or `Restart Manager API` in a future revision). MVP: three retries at 100ms, then refuse.

---

## R2. Same-filesystem staging layout

**Decision**: Stage all pre-publication bytes under a per-generation sibling directory of each participating output root, named `<root>.staging.<gen>/`. Example: `.haex-hive.staging.g_20260831T142011Z_a4c2/`. `<gen>` is the time-based, collision-checked generation identifier from R8.

**Rationale**:
- Guarantees `os.replace(staged_file, canonical_file)` stays on the same filesystem — a rename that crosses filesystems degrades to copy+unlink and loses atomicity.
- Sibling-directory naming is clearly not the operator's — the `.staging.<gen>` suffix identifies the transaction's ownership and disambiguates concurrent invocations even if the lock were somehow bypassed.
- Cleanup is trivial: after successful publication, the whole staging directory is `rmtree`d as the transaction's final step.

**Alternatives considered**:
- **Central `$HAEX_HIVE_STATE/staging/<repo-identity>/<gen>/`**: could cross filesystems (state root often on a different volume than the project checkout). Rejected — same-filesystem invariant broken.
- **`<root>/.staging/`**: an inside-the-root staging subdirectory. Rejected for mixed-ownership roots (`.claude/`, `.codex/`) — the transaction is not allowed to enumerate or write siblings inside those roots, and a `.staging` subdirectory would violate that.

**Residual risk**: interrupted install leaves `<root>.staging.<gen>/` behind. Recovery discovers and either finalises it (if journal indicates progress) or `rmtree`s it (if journal indicates abort). A stale staging directory from an abandoned pre-lock crash is cleaned on next successful acquisition of the exclusive lock.

---

## R3. Mixed-ownership root overlay mechanism

**Decision**: Per-platform overlay primitives selected from a small allowlist:
- **Directory-scoped overlay** (e.g. `.claude/skills/`, `.claude/agents/`): POSIX → `os.symlink()`; Windows → directory junction via `mklink /J` or the `CreateSymbolicLinkW` API with `SYMBOLIC_LINK_FLAG_DIRECTORY`. Junctions work on Windows without Developer Mode.
- **File-scoped overlay** (e.g. `.claude/settings.json`): POSIX → `os.symlink()`; Windows without Developer Mode → **refused per FR-003**, install exits with a diagnostic naming the unsupported path. Launcher-indirection for file-scoped overlays is a future refinement (Spec 010 or later); not in Spec 008 scope.
- Every overlay is recorded in `install.lock`'s per-root `overlay_paths` array; publication touches ONLY the paths in that array; sibling entries in the mixed-ownership root are never enumerated, copied, or replaced (FR-003).

**Rationale**:
- Directory junctions on Windows are OS-native, need no elevation, work identically to symlinks for readers, and cover the common case of adapters that publish a whole directory of skills/agents/rules.
- Per-file symlinks on POSIX are trivially supported.
- File-scoped symlinks on Windows require Developer Mode — treating that as an install-time refusal is consistent with FR-003 ("A platform without an atomic pointer or stable overlay mechanism MUST refuse the install rather than publish a torn direct view").
- The `overlay_paths` allowlist in `install.lock` is the mechanical enforcement of "touch only what we own" — the publication code MUST NOT enumerate the target root; it iterates the allowlist.

**Alternatives considered**:
- **Copy-with-drift-marker** (byte-copy instead of symlink, verify hash on next install): works portably but reintroduces the drift-risk symlinks were chosen to avoid. Rejected for MVP.
- **Adapter-managed launcher** (a small script that redirects to the current generation directory): universal, no elevation, but adds indirection cost per read. Deferred to a future revision.
- **Refuse Windows entirely for mixed-ownership roots**: too broad — directory-scoped overlays via junctions cover the common Spec 010 adapter cases. File-scoped-only refusal is the narrower and more accurate stance.

**Residual risk**: Adapters that publish a mix of directory-scoped and file-scoped overlays force the operator on Windows-non-DevMode to choose between (a) enabling Developer Mode or (b) skipping the file-scoped overlay entry. The plan does not silently drop entries — refusal is loud and names the exact path.

---

## R4. Fenced-lease numeric contract for the install lock

**Decision**:
- **Owner-token format**: `<pid>:<hostname>:<start_ns>:<uuid4-hex>` — exactly four colon-separated fields, all ASCII-safe, total length ≤ 128 bytes. Example: `31245:laptop-hex.local:1727612345678901234:8f3a2d1c9e7b4a5680c2e14f7d6b3a95`.
- **Heartbeat cadence**: 5 seconds. The lock owner runs a background thread that updates `heartbeat_at` and reboot-safe `heartbeat_at_ns_wallclock=time.time_ns()` in place through the already-locked file handle, then fsyncs it every 5 seconds. The pathname and inode remain stable.
- **Lease TTL**: 60 seconds (12× heartbeat), plus a 5-second safety margin. The
  persisted `heartbeat_at_ns_wallclock=time.time_ns()` is compared with the
  recovering process's `time.time_ns()`; recovery requires an age greater than
  65 seconds before reclaiming. Persisted monotonic values are not used across
  reboots.
- **Revalidation ordering** (recovery): (1) acquire the same non-blocking exclusive OS lock; (2) read and parse the lease; (3) if the OS lock is held by another process, wait or exit with owner-detail diagnostic regardless of heartbeat age; (4) require `time.time_ns() - heartbeat_at_ns_wallclock` to exceed TTL plus the safety margin; (5) re-read the lease under the exclusive handle and require the owner token and wall-clock heartbeat to be unchanged and still stale; (6) rewrite the lease in place through the locked handle with the recovering process's own owner token; (7) proceed with recovery. Every owner revalidates its token before each mutation, so a resumed fenced process stops.

**Rationale**:
- **UUID4 for uniqueness** — pid+hostname+start_ns can theoretically collide (containers reusing pids, low-resolution clock); UUID4 makes collision astronomically unlikely.
- **5s heartbeat** — short enough that a paused-then-resumed process refreshes before TTL expires under normal circumstances; long enough that the background thread does not measurably contend with the main install work.
- **60s TTL** — twelve heartbeat intervals absorbs common transient stalls (GC pauses, VM freezes under load, IO stalls). Longer TTLs delay recovery from genuinely dead installs; shorter risks false-positive reclaim.
- **OS lock plus revalidation-before-reclaim** — a paused owner still holds the OS lock and therefore cannot be reclaimed. If the owner died and released it, the "read stale, exclusive-re-read stale-and-unchanged, then reclaim" ordering prevents a replacement race; if a heartbeat changes between reads, step 5 backs off.
- **`mtime` explicitly rejected** as sole signal — reqs doc says so and it is well-known unsound (a `touch` from an unrelated process can spoof it).

**Alternatives considered**:
- **etcd/consul-style monotonic fencing token issued by a central authority**: not applicable, no central authority.
- **File-lock with `fcntl.flock` alone, no fenced lease**: `flock` releases automatically on process death, but it provides no owner metadata or recovery fencing. The lease record supplies diagnostics and prevents a replacement process from acting on a stale read.
- **Shorter TTL (e.g. 10s)**: rejected — false-positive reclaim risk on a heavily-loaded satellite is too high for a state-mutating operation.

**Residual risk**: A satellite whose wall clock jumps backward delays reclamation, which is safe; a forward jump is bounded by requiring the OS lock to be available and revalidating the unchanged lease. Monotonic time schedules heartbeats and supplies the diagnostic `start_ns`; UTC timestamps are persisted for cross-process expiry with a 5-second safety margin.

---

## R5. Per-root Merkle-tree digest scheme

**Decision**:
- **Algorithm**: SHA-256.
- **Per-root normalisation**: enumerate the root's owned paths in POSIX-byte-sorted order (lexicographic on UTF-8-encoded bytes). For each path, compute `content_hash = SHA-256(bytes-of-file)`. Concatenate `<repo-relative-path>:<hex-content-hash>\n` for every path (LF terminator per line). The root's digest is `SHA-256(concatenation)`.
- **Mixed-ownership root**: enumerate ONLY the overlay-owned paths recorded in `install.lock` (never sibling entries).
- **`.haex-hive/` root**: enumerate every file under `.haex-hive/` EXCEPT `visibility.json` and `install.lock`; excluding both avoids recursive lock/marker integrity references. The lock's marker reference uses a canonical marker projection without `install_lock_content_integrity` and `written_at`, so it remains computable.
- **Emission format**: `sha256-<base64url-nopad(digest)>` — matches Spec 007's SRI-style `content_integrity` representation for consistency.

**Rationale**:
- **SHA-256** is Spec 007's existing choice; introducing a different algorithm would fragment the codebase's integrity vocabulary.
- **Byte-sorted paths + LF-terminated lines** — deterministic; independent of iteration order returned by the OS's directory listing; independent of locale.
- **Excluding `visibility.json` from `.haex-hive/`'s digest** — needed because `visibility.json` records that digest; including it would be self-referential.
- **Excluding `install.lock` from the digest** — the lock contains the participating-root digest and the marker contains the lock digest. Excluding the lock and marker breaks that cycle without weakening the digest of any other committed output.
- **base64url-nopad** — URL-safe, no padding characters, compact — matches SRI convention.

**Alternatives considered**:
- **Blake3** for speed: rejected for consistency (Spec 007 uses SHA-256 everywhere).
- **Merkle-tree with tree-shaped hashing** (each directory a hash of its subtree, root a hash of top-level): more complex, no measurable benefit for the small file counts Spec 008 targets (typically ≤50 files). Rejected as premature complexity.
- **Include `visibility.json` via placeholder-hash**: adds fragility with no benefit. Rejected.

**Residual risk**: A path containing an LF byte would break the concatenation format. Mitigation: refuse at input validation. POSIX allows LF in paths but the atom-manifest schema (Spec 007) forbids control characters in `repoRelativePath` — that rule extends here.

---

## R6. Lock primitive selection

**Decision**: POSIX advisory locks use `fcntl.flock(fd, LOCK_EX | LOCK_NB)` for writers and `LOCK_SH | LOCK_NB` for readers. Windows uses the native `LockFileEx` API through `ctypes`: writers pass `LOCKFILE_EXCLUSIVE_LOCK`, while readers omit that flag and therefore acquire a shared lock. Both are non-blocking; a conflict returns `EWOULDBLOCK` / `EAGAIN` (POSIX) or a sharing-violation error (Windows), at which point the install reads the owner-token payload from the mutex file for the diagnostic.

**Rationale**:
- `fcntl.flock` — POSIX-standard, released automatically on process death (belt-and-braces alongside fenced lease).
- `LockFileEx` — the Windows primitive supports both shared readers and exclusive writers, and is released on process death.
- **Advisory, not mandatory** — cooperating processes respect it; unrelated processes ignore it. Matches the "cooperating haex tooling only" trust model. The fenced-lease (R4) covers the case where a cooperating process is alive-but-hung.
- **Non-blocking** — the install fails fast with owner detail rather than silently waiting; the operator can decide whether to wait or investigate.

**Alternatives considered**:
- **`fcntl.lockf`** (POSIX record locks): released when ANY fd in the process closes, which is fragile. Rejected.
- **filelock** third-party package: adds dependency for a stdlib-solvable problem. Rejected.
- **Blocking `flock` with timeout**: obscures who owns the lock during the wait; failing fast with owner detail is more useful.

**Residual risk**: NFS mounts have historically had unreliable `flock`. Mitigation: refuse `haex install` if the project checkout is on a filesystem type known to have unsound `flock` semantics (checked via `statfs` / `GetVolumeInformationW` on init). Not blocking for the MVP — Linux/macOS local filesystems and Windows NTFS all support this correctly.

---

## R7. Durable journal format and replay semantics

**Decision**:
- **Format**: one JSON object per line (JSONL), UTF-8, LF-terminated. Each entry has: `entry_id` (monotonically increasing integer), `entry_type` (enum), `payload` (step-specific object), `tail_hash` (SHA-256 over canonical UTF-8 entry JSON without `tail_hash`, one LF, and the previous tail hash as ASCII). The first previous hash is empty and the JSONL record's trailing LF is separate from the hash preimage.
- **PlanStep-to-journal mapping**: `stage_file` → `stage_file`, `delete_orphan` → `delete_orphan`, `overlay_pointer` → `overlay_pointer_swapped`, `hook_invoke` → one lifecycle pair `hook_step_started`/`hook_step_ended` plus one `stage_file` entry for each hook-produced filesystem output, `seal_install_lock` → `install_lock_sealed`, and `publish_marker` → `commit_marker_published`. Every filesystem mutation has exactly one mutation entry written before it; lifecycle entries are not PlanSteps.
- **Write discipline**: append the line, `fsync(fd)`, `fsync(parent_dir_fd)`, then execute the corresponding filesystem mutation. Each state transition writes its own journal entry BEFORE the mutation. This is the "write-ahead" invariant of FR-002.
- **Replay on recovery**:
  1. Open the journal; verify `tail_hash` chain from the first entry; abort recovery on a broken chain (integrity violation).
  2. Walk entries in order; determine the last consistent state.
  3. If the last publication entry is `commit_marker_published` and the marker file on disk matches, the install committed — treat any following `cleanup_started` or `cleanup_completed` entries as cleanup-only state and resume or finish cleanup without rolling back (rmtree staging directories).
  4. If the last publication entry is `commit_marker_published` but the marker file on disk is absent or mismatched, roll back to the previous generation's marker, regardless of any following cleanup entries.
  5. If the last entry is `install_lock_sealed` but not `commit_marker_published`, complete the marker publication (idempotent — it's a single-file replace).
  6. If any earlier state, roll back: undo any per-file replaces recorded in the journal, restore prior-generation content from `<root>.rollback.<prev-gen>/` if present, `rmtree` staging.
- **Entry types**: `plan_snapshot_sealed`, `commit_snapshot_verified`, `stage_file`, `delete_orphan`, `hook_step_started`, `hook_step_ended` (for Spec 009 extensibility), `overlay_pointer_swapped`, `install_lock_sealed`, `commit_marker_published`, `cleanup_started`, `cleanup_completed`, `install_aborted`. Recovery tests cover crashes after both cleanup entries and preserve a valid published marker.

**Rationale**:
- **JSONL** — line-append is atomic below PIPE_BUF (4096 bytes on Linux, 512 on some POSIX); journal entries are ≤512 bytes and thus atomic on append.
- **Tail-hash chain** — detects torn writes and adversarial modification. Not a security boundary (attacker with write access can forge entries), but a robustness check.
- **Write-ahead** — the essential FR-002 property. Without it, a crash between mutation and journal-write leaves an unrecorded state that recovery cannot handle.
- **Explicit step types** — enumerating them makes recovery a state machine, easier to reason about and test.

**Alternatives considered**:
- **SQLite journal**: overkill for tens of entries per install; adds a runtime dependency.
- **Binary format**: more compact but less debuggable. Human-inspectable JSONL wins for a tool operators will occasionally inspect.
- **Redo/undo log with separate files**: more complex, no benefit at this scale.

**Residual risk**: journal grows unbounded if never cleaned. Mitigation: `cleanup_completed` removes the checkout-scoped journal atomically at the end of every successful install. Recovery from a corrupt or truncated journal falls back to `install.lock` reconciliation (see R10 in future revision — not in Spec 008 scope).

---

## R8. Time-based generation ID

**Decision**: `g_<UTC-ISO8601-basic-format>_<content-hash-prefix>` — e.g. `g_20260831T142011Z_a4c2` — where `<content-hash-prefix>` is the first 4 hex chars of `SHA-256(plan-snapshot-digest)`. The timestamp is the UTC allocation time, not a deterministic input. The allocator advances the timestamp if the candidate equals an existing generation ID, making IDs unique and lexicographically time-ordered under the exclusive install lock.

**Rationale**:
- **Stable plan identity** — the hash suffix is derived from the sealed plan snapshot, while the timestamp identifies allocation order. Recovery uses the generation ID recorded in the journal rather than recomputing the full ID from inputs.
- **Human-inspectable** — the timestamp lets the operator eyeball the install order in `.haex-hive/visibility.json.previous/` (if we ever add generation history — future revision).
- **UTC ISO 8601 basic** — no locale-specific format issues, sortable as ASCII.

**Alternatives considered**:
- **UUID4**: not deterministic; recovery cannot verify.
- **Sequential integer**: needs a persisted counter, adds state.
- **Full content-hash**: opaque to operators; the 4-char prefix + timestamp balance readability with disambiguation.

**Residual risk**: 4-char prefix has 65,536 buckets — different plans can share a suffix. The timestamp allocator's collision check prevents duplicate complete IDs; the suffix is an identifier hint, not a uniqueness boundary.

---

## R9. Constitution assemble integration

**Decision**: The existing `haex constitution assemble` transaction (Spec 007) becomes a single-participant special case of `haex install`'s transaction. Concretely:
- `haex install` runs constitution assembly as one plan step among many when the plan's atoms include `contributes.constitution`.
- The existing `.haex-hive/install.lock` schema is EXTENDED with `atoms`, `overlay_paths` per participating root, a `visibility_marker` block, `participating_roots`, and a versioned `ownership` set. Digest fields move to base64url no-pad. **Under the project's pre-user policy** (no external adopters, breaking changes fine — see `haex_hive_pre_user.md` in agent memory), this is a hard cut: a Spec 007-vintage `install.lock` fails Spec 008 schema validation with `InstallLockSchemaInvalidError` and there is no in-tool migration. Operator recovery is to remove the stale file and re-run `haex constitution assemble`.
- `haex constitution assemble` (invoked directly) still works — it becomes a shortcut that runs the install transaction with a plan filtered to constitution-only steps. This preserves the current UX.
- Multi-source LLM-merge (Spec 007's `--llm=file` two-phase flow) is preserved unchanged.
- Shared path helpers derive `$HAEX_HIVE_STATE`, the canonical project identity, its SHA-256 `<repo-key>`, the repository mutex, and a checkout-scoped journal under `checkouts/<checkout-key>/`. Both `constitution assemble` and `constitution show` use these helpers. No in-repository transaction lock or journal is created or inspected.
- The pre-user rollout guarantees that no older haex process is active during installation, so no cross-version writer exclusion is required.

**Rationale**:
- Duplicating the transaction machinery for install would be a source of drift. The extract-shared-implementation approach keeps one transaction, many participants.
- The pre-user cut for the schema is cheaper than carrying a Spec 007-vintage compat shim: no external `install.lock` files exist in the wild, self-adoption regenerates its own lock on the next `haex constitution assemble`. Both PR #29 (SRI compat helper) and PR #30 (forward-compat tests) landed exactly this stance in code.

**Alternatives considered**:
- **Keep the two paths separate, migrate later**: rejected — drift risk in a load-bearing invariant is unacceptable.
- **Deprecate `haex constitution assemble` in favour of `haex install --scope=constitution`**: too disruptive for an existing landed CLI. The UX shortcut stays.
- **Preserve backward compatibility for `install.lock` (`sriDigest` accepts both alphabets; atoms fields optional)**: rejected under pre-user policy — cost of the shim exceeds its value while no external adopters exist. If a first adopter ever appears this decision is revisited via a spec amendment.

**Residual risk**: an operator with an in-flight Spec 007-vintage `install.lock` on their dev machine gets a schema refusal on the next `haex install`. Recovery is one `rm` and `haex constitution assemble`. This is acceptable under the pre-user policy because no external adopters need an in-place state migration.

---

## R10. Adapter overlay path enumeration source

**Decision**: The plan-build step (Spec 008 module `install/plan.py`) collects `overlay_paths` from two sources:
1. **Static-per-atom declarations** — an atom's `manifest.json` may declare which paths its adapter emissions will occupy under a mixed-ownership root (extension to Spec 007's atom-manifest schema, coordinated with Spec 010 during that spec's design).
2. **Adapter runtime declarations** — Spec 010 adapters register their emission paths with the install pipeline before staging; the pipeline records those paths in the plan snapshot.

**Rationale**:
- Static declaration is possible for stable, atom-scoped emissions (a fixed skill file, a fixed rule directory).
- Dynamic registration accommodates adapters that compute their output set from the resolved atom set (e.g. a "one skill per adopted MCP server" adapter).
- Both flow through the same `overlay_paths` allowlist so the "touch only what we own" enforcement is uniform.

**Alternatives considered**:
- **Only static**: too restrictive; blocks legitimate dynamic adapters.
- **Only dynamic**: forfeits pre-plan validation (an adapter can register anything at runtime).
- Both together lets the plan validate the static claims and record the dynamic ones under the same enforcement.

**Residual risk**: An adapter that dynamically registers a path outside a mixed-ownership root (e.g. a path in `.git/hooks/` claimed by graphify-first-authoring) is out of scope for the overlay mechanism — those go through the hook boundary (Spec 009) instead. The install pipeline validates that dynamic registrations are within a declared participating output root; violations refuse.

---

## R10a. Persisted per-path ownership and rollback pre-images

**Decision**: Extend `install.lock` with `ownership: {"version": 1, "paths": [...]}`.
Each `paths[]` record contains the root-relative POSIX path, an owner resource
(`atom`, `adapter`, or `hook`), the current generation ID and file digest, and a
`previous` record containing the prior generation ID, whether the path existed,
and its prior digest (or `null`). The array is unique and bytewise sorted.

The previous and current ownership sets are the only inputs to orphan planning.
For every write or delete, the journal records the pre-image existence, digest,
and a transaction-relative rollback reference before the mutation. The rollback
reference is never an absolute path and is not persisted in the committed lock;
it points to the same-filesystem rollback tree while the journal is live. This
allows rollback to restore deleted bytes while ensuring an unowned sibling in a
mixed-ownership root is never inferred or touched.

**Rationale**: Aggregate root digests prove what a generation contains but cannot
answer who owns a path or whether a deletion is safe. A versioned ownership set
provides that planning boundary while journal pre-images provide the bytes needed
for recovery.

---

## R11. Windows compatibility gotchas

Recorded for the plan phase; each has a mitigation baked into R1–R6.

- **`os.replace()` on Windows with a held reader handle** — see R1 residual risk (retry-backoff-then-refuse).
- **Windows directory-junction creation** — `mklink /J` is a command-line fallback for directory targets; `CreateSymbolicLinkW(..., SYMBOLIC_LINK_FLAG_DIRECTORY)` is the native API path. Both refuse an existing matching entry. Before removal, publication moves the existing overlay to the transaction rollback tree and records the pre-image and pointer path in the journal. It then creates the new junction/symlink; on creation failure or crash before marker publication, recovery restores the saved overlay, and after marker publication cleanup removes the backup only after the new pointer verifies. The rollback path and generation are recorded in journal metadata and the ownership set.
- **Windows without Developer Mode + file-scoped symlink** — refuse per R3.
- **`fcntl.flock` unavailable on Windows** — use `LockFileEx` through `ctypes` (R6); the lock module's Windows tests cover two concurrent readers and a writer excluded until both readers release.
- **Path separators** — every path stored on disk is POSIX-normalised (`/`); Windows-side code converts at the OS boundary only.
- **Case-sensitivity** — NTFS is case-insensitive by default; the digest scheme (R5) uses the path exactly as recorded in `install.lock`, so a `Foo.md` vs `foo.md` mismatch is treated as a validation error at input time, not as two distinct files.

---

## R12. Test infrastructure for the conformance suite

**Decision**:
- **Crash injection**: monkey-patch a controlled subset of `install/` module entrypoints to raise `SystemExit(137)` at chosen states. The pytest fixture parametrises across the journal state matrix.
- **Concurrent invocation**: `multiprocessing.Process` fires the second install; the primary asserts the second's exit code, stderr contains the winner's owner token, and no output file was touched by the second.
- **Mid-install source mutation**: a background thread rewrites `.haex-hive.json` at the moment the plan snapshot completes; the assertion is `haex install` exits with the commit-time-mismatch diagnostic and no output was published.
- **Unowned-file survival**: the fixture pre-populates `.claude/` and `.codex/` with files not in the overlay_paths allowlist; the assertion is those files are byte-identical after install and after recovery.

**Rationale**: keeps the conformance suite in pure Python using `pytest`, `multiprocessing`, and `tempfile.TemporaryDirectory`; no external test-orchestration tool. Runs on all three OSes.

**Alternatives considered**:
- **Docker-in-CI**: overkill for these tests; local filesystem is sufficient.
- **Chaos-engineering framework**: designed for distributed systems; a single-process crash matrix does not need it.

---

## Consolidated outcome

Every "NEEDS CLARIFICATION" from the plan phase is resolved above. The plan proceeds to Phase 1 (data model + contracts + quickstart) with these decisions frozen.
