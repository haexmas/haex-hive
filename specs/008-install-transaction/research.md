# Phase 0 Research: Install Transaction Contract for `haex install`

**Feature**: Spec 008 — Install Transaction Contract
**Date**: 2026-08-31
**Purpose**: Resolve every load-bearing implementation decision the plan reserved as "chosen in research". Each section below records the decision, the rationale, and the alternatives considered. Where a decision has a residual risk, that risk is called out explicitly.

---

## R1. Atomic per-file publication primitive across OSes

**Decision**: Use `os.replace(src, dst)` for every publication step. Sequence per-file replacements via the durable journal (see R7). The visibility marker publication is one final `os.replace()` call and is the sole publication event (FR-004).

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

**Decision**: Stage all pre-publication bytes under a per-generation sibling directory of each participating output root, named `<root>.staging.<gen>/`. Example: `.haex-hive.staging.g_20260831T142011Z_a4c2/`. `<gen>` is the deterministic generation identifier from R8.

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
- **Heartbeat cadence**: 5 seconds. The lock owner runs a background thread that rewrites the `heartbeat_at_ns` field of `install.mutex` every 5 seconds.
- **Lease TTL**: 60 seconds (12× heartbeat). Recovery treats `now_ns - heartbeat_at_ns > TTL` as "abandoned".
- **Revalidation ordering** (recovery): (1) open `install.mutex` for shared read; (2) parse owner token + heartbeat_at_ns; (3) if not stale, wait or exit with owner-detail diagnostic; (4) if stale, re-open for exclusive-write; (5) re-parse owner token — MUST equal what was read in step 2, MUST still be stale; (6) atomically overwrite with the recovering process's own owner token; (7) proceed with recovery.

**Rationale**:
- **UUID4 for uniqueness** — pid+hostname+start_ns can theoretically collide (containers reusing pids, low-resolution clock); UUID4 makes collision astronomically unlikely.
- **5s heartbeat** — short enough that a paused-then-resumed process refreshes before TTL expires under normal circumstances; long enough that the background thread does not measurably contend with the main install work.
- **60s TTL** — twelve heartbeat intervals absorbs common transient stalls (GC pauses, VM freezes under load, IO stalls). Longer TTLs delay recovery from genuinely dead installs; shorter risks false-positive reclaim.
- **Revalidation-before-reclaim** — the "read stale, exclusive-re-read stale-and-unchanged, then reclaim" ordering prevents a race where a paused owner resumes mid-recovery: if it manages to refresh between our reads, step 5 sees a new heartbeat and we back off.
- **`mtime` explicitly rejected** as sole signal — reqs doc says so and it is well-known unsound (a `touch` from an unrelated process can spoof it).

**Alternatives considered**:
- **etcd/consul-style monotonic fencing token issued by a central authority**: not applicable, no central authority.
- **File-lock with `fcntl.flock` alone, no fenced lease**: `flock` releases automatically on process death, but a hung process (SIGSTOP, kernel wait) holds the lock indefinitely; the fenced-lease is what breaks that deadlock.
- **Shorter TTL (e.g. 10s)**: rejected — false-positive reclaim risk on a heavily-loaded satellite is too high for a state-mutating operation.

**Residual risk**: A satellite whose clock jumps backward under NTP adjustment could produce a false-positive stale reading. Mitigation: use `time.monotonic_ns()` for `heartbeat_at_ns` (unaffected by wall-clock jumps); persist and compare monotonic timestamps in-process; recovery from a different process compares wall-clock timestamps and MUST tolerate ±5s skew (add safety margin: effective TTL = 60s + 5s clock-skew allowance).

---

## R5. Per-root Merkle-tree digest scheme

**Decision**:
- **Algorithm**: SHA-256.
- **Per-root normalisation**: enumerate the root's owned paths in POSIX-byte-sorted order (lexicographic on UTF-8-encoded bytes). For each path, compute `content_hash = SHA-256(bytes-of-file)`. Concatenate `<repo-relative-path>:<hex-content-hash>\n` for every path (LF terminator per line). The root's digest is `SHA-256(concatenation)`.
- **Mixed-ownership root**: enumerate ONLY the overlay-owned paths recorded in `install.lock` (never sibling entries).
- **`.haex-hive/` root**: enumerate every file under `.haex-hive/` EXCEPT `visibility.json` (self-reference). `install.lock` IS included in the digest.
- **Emission format**: `sha256-<base64url-nopad(digest)>` — matches Spec 007's SRI-style `content_integrity` representation for consistency.

**Rationale**:
- **SHA-256** is Spec 007's existing choice; introducing a different algorithm would fragment the codebase's integrity vocabulary.
- **Byte-sorted paths + LF-terminated lines** — deterministic; independent of iteration order returned by the OS's directory listing; independent of locale.
- **Excluding `visibility.json` from `.haex-hive/`'s digest** — needed because `visibility.json` records that digest; including it would be self-referential.
- **Including `install.lock` in the digest** — reqs doc requires this: "The `.haex-hive/` digest includes `install.lock` and excludes only the marker itself to avoid self-reference."
- **base64url-nopad** — URL-safe, no padding characters, compact — matches SRI convention.

**Alternatives considered**:
- **Blake3** for speed: rejected for consistency (Spec 007 uses SHA-256 everywhere).
- **Merkle-tree with tree-shaped hashing** (each directory a hash of its subtree, root a hash of top-level): more complex, no measurable benefit for the small file counts Spec 008 targets (typically ≤50 files). Rejected as premature complexity.
- **Include `visibility.json` via placeholder-hash**: adds fragility with no benefit. Rejected.

**Residual risk**: A path containing an LF byte would break the concatenation format. Mitigation: refuse at input validation. POSIX allows LF in paths but the atom-manifest schema (Spec 007) forbids control characters in `repoRelativePath` — that rule extends here.

---

## R6. Lock primitive selection

**Decision**: POSIX exclusive advisory lock via `fcntl.flock(fd, LOCK_EX | LOCK_NB)`. Windows exclusive advisory lock via `msvcrt.locking(fd, LK_NBLCK, 1)` on the first byte of the mutex file. Both are non-blocking; a conflict returns `EWOULDBLOCK` / `EAGAIN` (POSIX) or `Permission denied` (Windows), at which point the install reads the owner-token payload from the mutex file for the diagnostic.

**Rationale**:
- `fcntl.flock` — POSIX-standard, released automatically on process death (belt-and-braces alongside fenced lease).
- `msvcrt.locking` — Windows equivalent; also released on process death.
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
- **Format**: one JSON object per line (JSONL), UTF-8, LF-terminated. Each entry has: `entry_id` (monotonically increasing integer), `step_type` (enum), `payload` (step-specific object), `tail_hash` (SHA-256 of `<line-content>\n<prev-tail-hash>`).
- **Write discipline**: append the line, `fsync(fd)`, `fsync(parent_dir_fd)`, then execute the corresponding filesystem mutation. Each state transition writes its own journal entry BEFORE the mutation. This is the "write-ahead" invariant of FR-002.
- **Replay on recovery**:
  1. Open the journal; verify `tail_hash` chain from the first entry; abort recovery on a broken chain (integrity violation).
  2. Walk entries in order; determine the last consistent state.
  3. If the last entry is `commit_marker_published` and the marker file on disk matches, the install completed — proceed with cleanup (rmtree staging directories).
  4. If the last entry is `commit_marker_published` but the marker file on disk is absent or mismatched, roll back to the previous generation's marker.
  5. If the last entry is `install_lock_sealed` but not `commit_marker_published`, complete the marker publication (idempotent — it's a single-file replace).
  6. If any earlier state, roll back: undo any per-file replaces recorded in the journal, restore prior-generation content from `<root>.rollback.<prev-gen>/` if present, `rmtree` staging.
- **Step types**: `plan_snapshot_sealed`, `commit_snapshot_verified`, `stage_file`, `hook_step_started`, `hook_step_ended` (for Spec 009 extensibility), `overlay_pointer_swapped`, `install_lock_sealed`, `commit_marker_published`, `cleanup_started`, `cleanup_completed`, `install_aborted`.

**Rationale**:
- **JSONL** — line-append is atomic below PIPE_BUF (4096 bytes on Linux, 512 on some POSIX); journal entries are ≤512 bytes and thus atomic on append.
- **Tail-hash chain** — detects torn writes and adversarial modification. Not a security boundary (attacker with write access can forge entries), but a robustness check.
- **Write-ahead** — the essential FR-002 property. Without it, a crash between mutation and journal-write leaves an unrecorded state that recovery cannot handle.
- **Explicit step types** — enumerating them makes recovery a state machine, easier to reason about and test.

**Alternatives considered**:
- **SQLite journal**: overkill for tens of entries per install; adds a runtime dependency.
- **Binary format**: more compact but less debuggable. Human-inspectable JSONL wins for a tool operators will occasionally inspect.
- **Redo/undo log with separate files**: more complex, no benefit at this scale.

**Residual risk**: journal grows unbounded if never cleaned. Mitigation: `cleanup_completed` truncates the journal to zero bytes at the end of every successful install. Recovery from a corrupt or truncated journal falls back to `install.lock` reconciliation (see R10 in future revision — not in Spec 008 scope).

---

## R8. Deterministic generation ID

**Decision**: `g_<UTC-ISO8601-basic-format>_<content-hash-prefix>` — e.g. `g_20260831T142011Z_a4c2` — where `<content-hash-prefix>` is the first 4 hex chars of `SHA-256(plan-snapshot-digest)`. Wall-clock is included for operator diagnostics; the content-hash prefix ensures two concurrent-but-different plans on the same second get different IDs.

**Rationale**:
- **Deterministic** — same plan-snapshot ⇒ same content-hash-prefix. Recovery can compute the expected generation ID from the journal's plan-snapshot entry and verify against the marker.
- **Human-inspectable** — the timestamp lets the operator eyeball the install order in `.haex-hive/visibility.json.previous/` (if we ever add generation history — future revision).
- **UTC ISO 8601 basic** — no locale-specific format issues, sortable as ASCII.

**Alternatives considered**:
- **UUID4**: not deterministic; recovery cannot verify.
- **Sequential integer**: needs a persisted counter, adds state.
- **Full content-hash**: opaque to operators; the 4-char prefix + timestamp balance readability with disambiguation.

**Residual risk**: 4-char prefix has 65,536 buckets — two different plans producing the same 4-char prefix at the same second is possible but requires simultaneous concurrent installs of different plans, which the lock already forbids. Acceptable.

---

## R9. Constitution assemble integration

**Decision**: The existing `haex constitution assemble` transaction (Spec 007) becomes a single-participant special case of `haex install`'s transaction. Concretely:
- `haex install` runs constitution assembly as one plan step among many when the plan's atoms include `contributes.constitution`.
- The existing `.haex-hive/install.lock` schema is EXTENDED (backward-compatible; see contracts) with `overlay_paths` per participating root, a `visibility_marker` block, and a `participating_roots` list. Existing single-source records stay valid.
- `haex constitution assemble` (invoked directly) still works — it becomes a shortcut that runs the install transaction with a plan filtered to constitution-only steps. This preserves the current UX.
- Multi-source LLM-merge (Spec 007's `--llm=file` two-phase flow) is preserved unchanged.

**Rationale**:
- Duplicating the transaction machinery for install would be a source of drift. The extract-shared-implementation approach keeps one transaction, many participants.
- The existing schema extension is backward-compatible if new fields default to sensible values (e.g. `overlay_paths: []`, `participating_roots: [".haex-hive/"]`, `visibility_marker: null` for pre-Spec-008 records).

**Alternatives considered**:
- **Keep the two paths separate, migrate later**: rejected — drift risk in a load-bearing invariant is unacceptable.
- **Deprecate `haex constitution assemble` in favour of `haex install --scope=constitution`**: too disruptive for an existing landed CLI. The UX shortcut stays.

**Residual risk**: schema extension must be validated on every existing `install.lock` produced by Spec 007 in the wild. Mitigation: schema tests use the actual Spec 007 fixtures as the backward-compat baseline.

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

## R11. Windows compatibility gotchas

Recorded for the plan phase; each has a mitigation baked into R1–R6.

- **`os.replace()` on Windows with a held reader handle** — see R1 residual risk (retry-backoff-then-refuse).
- **Windows directory-junction creation** — requires no elevation, but the parent directory MUST NOT already contain a matching entry (the junction API refuses to overwrite). Mitigation: publication removes any prior overlay at the same path before creating the junction, recorded in the journal as `overlay_pointer_replaced`.
- **Windows without Developer Mode + file-scoped symlink** — refuse per R3.
- **`fcntl.flock` unavailable on Windows** — use `msvcrt.locking` (R6).
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
