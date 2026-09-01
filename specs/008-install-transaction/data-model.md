# Data Model: Install Transaction Contract

**Feature**: Spec 008 — Install Transaction Contract
**Date**: 2026-08-31
**Purpose**: dataclass-level shapes and relationships for the install pipeline. Every persisted format has a matching JSON Schema under [contracts/](./contracts/); this file records the in-memory shapes and the state transitions of a running install.

---

## Entities

### PlanSnapshot

Sealed capture of every input the transaction depends on. Immutable after seal.

| Field | Type | Notes |
|---|---|---|
| `sealed_at_ns` | `int` | Monotonic nanoseconds at seal time (informational). |
| `haex_hive_json_digest` | `str` | `sha256-<b64u>` of the exact bytes of `.haex-hive.json` at seal. |
| `publisher_manifest_digests` | `dict[str, str]` | Keyed by publisher `source + revision`; value is `sha256-<b64u>` of the publisher `manifest.json` bytes. |
| `atom_manifest_digests` | `dict[str, str]` | Keyed by atom-id; value is `sha256-<b64u>` of the atom `manifest.json` bytes. |
| `plan_snapshot_digest` | `str` | `sha256-<b64u>` over the deterministic serialisation of the complete plan, including ordered steps and mutation-relevant payloads, excluding only informational `sealed_at_ns`. |
| `steps` | `list[PlanStep]` | Ordered list of transaction steps derived from the resolved atom set. |

**Validation**:
- `sealed_at_ns` MUST be non-negative and derived from `time.monotonic_ns()`.
- Every digest MUST be in `sha256-<b64u>` SRI-style format.
- `steps` MUST be non-empty; a zero-step plan is a bug in plan-build.
- `plan_snapshot_digest` MUST hash canonical UTF-8 JSON of all plan fields that
  can affect mutation or recovery, including the ordered `steps` and every
  step payload, with lexicographically sorted keys and no insignificant
  whitespace. Only the informational `sealed_at_ns` field is excluded.

### CommitSnapshot

Fresh re-read of the same inputs while the exclusive install lock is held. It is
compared with `PlanSnapshot` before the final preparation phase to detect
mid-install source mutation (FR-006). After a successful comparison, the exact
bytes are copied into a transaction-owned, read-only input snapshot. Resolution
and hydration consume that snapshot only; live inputs are never re-read before
the first root swap. Supported haex writers use the same exclusive lock, so the
snapshot remains fenced through publication.

Same shape as `PlanSnapshot` fields `haex_hive_json_digest`,
`publisher_manifest_digests`, `atom_manifest_digests`, plus the captured bytes
for each keyed input. Recorded verbatim; on any mismatch, install aborts.

### PlanStep

One participant in the transaction. The plan is a linear list of steps that
determines what gets written into `<root>.next/`. The list is consumed by
plan-build and does not require a durable journal entry per step — the
rename-swap contract (R1) commits the entire step list atomically when
`<root>.next/` becomes `<root>/`.

| Field | Type | Notes |
|---|---|---|
| `step_id` | `int` | Monotonically increasing within one plan (0, 1, 2 …). |
| `step_type` | `Literal[...]` | `"stage_file"`, `"overlay_pointer"`, `"hook_invoke"` (Spec 009 extension), `"seal_install_lock"`, `"publish_marker"`. |
| `participating_root` | `str` | Repo-relative path of the root this step touches (e.g. `.haex-hive/`, `.claude/`). |
| `payload` | `dict` | Step-type-specific payload; opaque here. |

The old `delete_orphan` step type no longer exists as a first-class step:
under R1 the fresh `<root>.next/` is materialised from scratch, so removed
resources' files simply do not appear in the new generation. Orphan tracking
still lives in `install.lock`'s `ownership.paths` set for downstream tooling
that needs to reason about what was removed, but the filesystem-level delete
is a byproduct of the rename-swap, not a discrete step.

### In-flight recovery state

Replaces the earlier `JournalEntry` + `PlanStep-to-JournalEntry mapping`
sections. There is no durable JSONL journal, no tail-hash chain, and no
sidecar file. The in-flight state of one participating output root is the
combination of three directory names beside that root:

| Directory | Meaning |
|---|---|
| `<root>/` | The currently-live generation. Its `visibility.json` names the published `generation_id`. |
| `<root>.next/` | A staged, fully-written, digest-verified fresh generation awaiting rename-in. |
| `<root>.prev/` | The previous generation, retained during the swap so it can be restored on a mid-swap crash. |

Every legal combination of presence/absence and its recovery action is
enumerated in research §R7's state table. Recovery reads
`os.listdir(parent_of_root)`, filters for the three names, and dispatches on
the combination. No other durable state is consulted or required.

The rename-swap performs at most two atomic transitions per root:

1. `os.rename(<root>, <root>.prev)` (skipped when `<root>/` does not exist).
2. `os.rename(<root>.next, <root>)`.

Both are single `rename(2)` (POSIX) or `MoveFileExW` (Windows) syscalls;
neither leaves a partially-updated intermediate visible to readers. The
parent directory is fsynced after each rename.

### OwnerToken

Runtime representation of the fenced-lease owner token (see R4).

| Field | Type | Notes |
|---|---|---|
| `pid` | `int` | Process id at acquisition. |
| `hostname` | `str` | `socket.gethostname()` at acquisition. |
| `start_ns` | `int` | `time.monotonic_ns()` at acquisition. |
| `uuid4_hex` | `str` | 32 hex chars, from `uuid.uuid4().hex`. |

**Serialisation**: `<pid>:<hostname>:<start_ns>:<uuid4_hex>`. Total length ≤ 128 bytes; hostname is validated against `[A-Za-z0-9.-]{1,64}$` at acquisition to keep the format ASCII-safe.

### InstallMutexFile

Layout of `install.mutex` (device-local, under `$HAEX_HIVE_STATE/locks/<repo-key>/`).

```json
{
  "owner_token": "<pid>:<hostname>:<start_ns>:<uuid4_hex>",
  "acquired_at": "2026-08-31T14:20:11.000000Z",
  "heartbeat_at": "2026-08-31T14:20:16.000000Z",
  "heartbeat_at_ns_wallclock": 1788186016000000000,
  "heartbeat_interval_ns": 5000000000,
  "ttl_ns": 60000000000,
  "safety_margin_ns": 5000000000
}
```

The owner updates the record in place through the already-locked file handle and
fsyncs it every 5 seconds; it MUST NOT replace the pathname or inode while the
advisory lock is held. `heartbeat_at_ns_wallclock` is `time.time_ns()` and is the
reboot-safe expiry value. The formatted UTC timestamps are diagnostic mirrors;
monotonic time is used only to schedule the heartbeat and to form the
diagnostic `start_ns` token field.

Recovery first obtains the same non-blocking exclusive OS lock. It then requires
the lease to be older than `ttl_ns + safety_margin_ns`, re-reads the record
under that lock, and requires the token and heartbeat to be unchanged and still
expired before rewriting the record in place with a new owner token. A resumed
process whose token was fenced MUST stop before its next mutation.

### VisibilityMarker

Sole publication event's on-disk representation: `.haex-hive/visibility.json`. See [contracts/visibility-marker.v1.schema.json](./contracts/visibility-marker.v1.schema.json).

| Field | Type | Notes |
|---|---|---|
| `haex_hive_version` | `Literal["2"]` | Matches Spec 007. |
| `generation_id` | `str` | Time-based and collision-checked; the hash suffix identifies the sealed plan; see R8. |
| `install_lock_content_integrity` | `str` | `sha256-<b64u>` of `install.lock` bytes. |
| `participating_roots` | `list[RootDigest]` | One entry per participating output root. |
| `written_at` | `str` | UTC ISO 8601 for operator diagnostics; not used in verification. |

### RootDigest

| Field | Type | Notes |
|---|---|---|
| `root` | `str` | Repo-relative directory (e.g. `.haex-hive/`). |
| `content_integrity` | `str` | Per-root digest per R5. For `.haex-hive/`, the digest excludes both `install.lock` and `visibility.json` so lock and marker references remain computable. |
| `overlay_paths` | `list[str] \| null` | For mixed-ownership roots, the exhaustive owned-path allowlist. `null` (or field absent) for haex-owned roots (whole tree owned). |

### InstallLock

Extended shape of `.haex-hive/install.lock`. See [contracts/install-lock.v2.schema.json](./contracts/install-lock.v2.schema.json). Adds `atoms`, `participating_roots`, `visibility_marker`, and `ownership` on top of Spec 007's constitution block. Not backward compatible with Spec 007-vintage `install.lock` bytes: SRI digests are base64url no-pad (Spec 007 used padded standard base64), and any Spec 007-vintage record fails schema validation. Under the project's pre-user policy this is the accepted cut; operator recovery is to remove `.haex-hive/install.lock` and re-run `haex constitution assemble`.

| Field | Type | Notes |
|---|---|---|
| `haex_hive_version` | `Literal["2"]` | Unchanged from Spec 007. |
| `generated_by` | `str` | e.g. `"haex 2.1.0"`. |
| `constitution` | `ConstitutionBlock` | Existing Spec 007 shape; unchanged. |
| `atoms` | `list[AtomInstallRecord]` | New in Spec 008; per-atom install detail. |
| `participating_roots` | `list[RootRecord]` | New in Spec 008; matches `VisibilityMarker.participating_roots` byte-identically at seal time. |
| `visibility_marker` | `VisibilityMarkerRef` | New; `{ "generation_id": "...", "content_integrity": "sha256-..." }`. The integrity is over the marker's canonical identity projection with `install_lock_content_integrity` and `written_at` excluded; it is therefore a one-way reference and not recursive. |
| `ownership` | `OwnershipSet` | New; versioned per-path ownership records used for orphan planning and rollback. |

### OwnershipSet

The authoritative set of generated paths for one installed generation. The set
contains only paths the transaction owns; in particular, it never contains
unowned siblings in a mixed-ownership root.

| Field | Type | Notes |
|---|---|---|
| `version` | `Literal[1]` | Version of the per-path record format. |
| `paths` | `list[PathOwnershipRecord]` | Unique root-relative POSIX paths, sorted bytewise. |

### PathOwnershipRecord

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | Root-relative POSIX path, including the participating root. |
| `owner` | `OwnerResource` | Atom, adapter, or hook that owns the path. |
| `generation_id` | `str` | Generation that sealed the current bytes. |
| `content_integrity` | `str` | Digest of the current sealed bytes. |
| `previous` | `PreviousPathState \| null` | Prior generation, existence, and digest; actual rollback bytes live inside the retained `<root>.prev/` directory during the swap. |

The plan computes orphan deletion from the previous lock's `ownership.paths`
set, but under R1's rename-swap the actual removal is a byproduct of
materialising `<root>.next/` from scratch: removed paths simply do not appear
in the new generation. `ownership.paths` still records the delta for
downstream tooling; unowned paths are never inferred by enumerating a
mixed-ownership root.

### AtomInstallRecord

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Reverse-DNS atom id. |
| `source` | `str` | Publisher repo URL. |
| `revision` | `str` | Full 40-char SHA. |
| `content_integrity` | `str` | Digest of the atom's sealed contribution. |
| `contributed_paths` | `list[str]` | Repo-relative paths this atom contributed under participating roots. |

### RootRecord

Same shape as `RootDigest`; `install.lock` records the authoritative content, `visibility.json` cross-references it via digest.

---

## State machine of a running install

```text
START
  │
  ▼
[acquire_lock]  ──── on stale lease → [reclaim_lease] ──┐
  │                                                     │
  ▼                                                     ▼
[resolve_in_flight_state]  ◄──── inspect <root>/, <root>.next/, <root>.prev/
  │                                per §R7 state table (complete forward,
  │                                roll back, or refuse)
  ▼
[build_plan_snapshot]
  │
  ▼
[commit_snapshot_verify]  ──── mismatch → [abort + delete <root>.next/]
  │
  ▼
[seal_commit_inputs]
  │
  ▼
[resolve_and_hydrate_from_commit_snapshot]
  │
  ▼
[materialise_root_next]  (write every file into <root>.next/, fsync)
  │
  ▼
[invoke_hooks]  (Spec 009 extension point; MAY be no-op in Spec 008)
  │
  ▼
[seal_install_lock_inside_next]  (write .haex-hive.next/install.lock)
  │
  ▼
[write_visibility_marker_inside_next]  (write .haex-hive.next/visibility.json)
  │
  ▼
[verify_next_digests]  (recompute per-root digest vs staged visibility.json)
  │
  ▼
[rename_A]  os.rename(<root>, <root>.prev)  ◄── first atomic commit boundary
  │
  ▼
[rename_B]  os.rename(<root>.next, <root>)  ◄── SOLE publication event
  │
  ▼
[cleanup_prev]  rmtree(<root>.prev/), fsync parent
  │
  ▼
END (success)


At any state above ↓
[crash] → next `haex install` or `haex verify --recover`
  │
  ▼
[resolve_in_flight_state]  → read <root>{,.next,.prev} presence
  │
  ├── row 3 of §R7 (mid-swap, <root>/ absent) → complete forward
  ├── row 4 of §R7 (post-swap, <root>.prev/ still present) → cleanup only
  ├── row 2 of §R7 (staged but pre-swap) → delete <root>.next/, plan afresh
  └── other rows → per §R7 state table
```

**Invariants at every transition**:
- The exclusive lock is held from `[acquire_lock]` through `[cleanup_prev]`.
- Every rename that transitions between the three directory names is followed by a parent-directory fsync before the next state is entered.
- The `[rename_B]` step (`os.rename(<root>.next, <root>)`) is the sole publication event; `[cleanup_prev]` follows but cannot change the published generation and is idempotent under recovery.

---

## Relationships between entities

- One `PlanSnapshot` ⇌ many `PlanStep`s (composition).
- One `PlanSnapshot` ⇌ one `CommitSnapshot` (compared for equality on published-digest fields).
- One install ⇌ one `install.mutex` file ⇌ one live `OwnerToken`.
- One in-flight install ⇌ at most one `<root>.next/` and one `<root>.prev/` beside each participating root (see §In-flight recovery state).
- One successful install ⇌ one `VisibilityMarker` ⇌ one `InstallLock` (their digests cross-reference).
- One `InstallLock` ⇌ many `AtomInstallRecord`s ⇌ many `RootRecord`s.
- One `InstallLock` ⇌ one `OwnershipSet` ⇌ many `PathOwnershipRecord`s.

---

## Boundaries and non-goals

- **Publisher-hook payloads** (Spec 009 territory): `PlanStep.step_type = "hook_invoke"` reserves the slot; the payload shape is Spec 009's design decision. Spec 008 records the step type so Spec 009 can hang hook execution off it, but hook execution happens while `<root>.next/` is being materialised — the rename-swap contract covers whatever the hooks produced.
- **Adapter output payloads** (Spec 010 territory): the plan step's `payload` for adapter-emitted files is opaque to Spec 008; the pipeline stages, digests, and publishes them per the transaction contract without introspecting content.
- **Cross-version migration** of `install.lock` and transaction state: **out of scope for Spec 008 under the project's pre-user policy.** A Spec 007-vintage `install.lock` fails Spec 008 schema validation (padded base64 digests, missing atoms shape) and the transaction refuses with `InstallLockSchemaInvalidError`. If a future adopter requires an in-place migration path, it lands under an explicit `haex migrate` verb per Principle VI v1.3.0, not as an implicit tool-side rewrite.
