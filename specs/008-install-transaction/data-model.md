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

One participant in the transaction. The plan is a linear list of steps; each
filesystem mutation corresponds to exactly one mutation journal entry during
execution. A `hook_invoke` step has one lifecycle pair around its work, and
each filesystem output it produces is represented by its own `stage_file`
mutation entry.

| Field | Type | Notes |
|---|---|---|
| `step_id` | `int` | Monotonically increasing within one plan (0, 1, 2 …). |
| `step_type` | `Literal[...]` | `"stage_file"`, `"delete_orphan"`, `"overlay_pointer"`, `"hook_invoke"` (Spec 009 extension), `"seal_install_lock"`, `"publish_marker"`. |
| `participating_root` | `str` | Repo-relative path of the root this step touches (e.g. `.haex-hive/`, `.claude/`). |
| `payload` | `dict` | Step-type-specific payload; see JSON schema for exact shapes per type. |

### JournalEntry

One line of `install.journal`. See [contracts/install-journal.v1.schema.json](./contracts/install-journal.v1.schema.json).

| Field | Type | Notes |
|---|---|---|
| `entry_id` | `int` | Monotonically increasing from 0. |
| `wrote_at_ns` | `int` | Monotonic nanoseconds at write. |
| `step_id` | `int \| null` | Corresponding `PlanStep.step_id`; null for lifecycle entries (start, commit, rollback). |
| `entry_type` | `Literal[...]` | The journal entry mapped from the corresponding `PlanStep.step_type`; lifecycle entries are explicitly separate. |
| `payload` | `dict` | Type-specific. |
| `tail_hash` | `str` | `sha256-<b64u>` of canonical entry JSON without `tail_hash`, encoded as UTF-8, followed by LF and the previous tail hash as ASCII. |

**Validation**:
- `entry_id` MUST equal the number of preceding entries (0-indexed).
- The first entry's `<prev-tail-hash>` component is the empty string. Canonical
  entry JSON uses deterministic lexicographic key ordering, no insignificant
  whitespace, and UTF-8 encoding; the JSONL record has a separate trailing LF.
  The hash preimage is exactly
  `canonical_json(entry_without_tail_hash).encode("utf-8") + b"\\n" + prev_tail_hash.encode("ascii")`.
- A journal whose `tail_hash` chain is broken MUST fail recovery with a diagnostic — no partial replay.

### PlanStep-to-JournalEntry mapping

The following mapping is normative. Every filesystem mutation has exactly one
corresponding mutation entry written before it is executed. Lifecycle entries
(`plan_snapshot_sealed`, `commit_snapshot_verified`, `cleanup_started`,
`cleanup_completed`, and `install_aborted`) do not represent a `PlanStep`.

| `PlanStep.step_type` | Mutation journal entry | Requirement |
|---|---|---|
| `stage_file` | `stage_file` | One entry per staged replacement. |
| `delete_orphan` | `delete_orphan` | One entry per orphan deletion, including its pre-image. |
| `overlay_pointer` | `overlay_pointer_swapped` | One entry per pointer replacement. |
| `hook_invoke` | `hook_step_started` + `hook_step_ended` | One lifecycle pair brackets the hook; each hook-produced filesystem output also has its own `stage_file` entry with a rollback pre-image. |
| `seal_install_lock` | `install_lock_sealed` | One entry for sealing the lock. |
| `publish_marker` | `commit_marker_published` | One entry for publishing the marker. |

Recovery dispatches only on these canonical journal names; aliases such as
`overlay_pointer_replaced`, `install_lock_sealed` variants, or
`commit_marker_published` variants are not accepted.

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
| `previous` | `PreviousPathState \| null` | Prior generation, existence, and digest; actual rollback bytes are retained by the journal pre-image record. |

The plan computes orphan deletion from the previous lock's `ownership.paths`
set. A delete step carries the removed record and its pre-image in the journal;
an unowned path is never inferred by enumerating a mixed-ownership root.

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
[verify_or_recover_journal]  ◄────────── incomplete journal from prior run
  │
  ▼
[build_plan_snapshot]
  │
  ▼
[commit_snapshot_verify]  ──── mismatch → [abort + rollback]
  │
  ▼
[seal_commit_inputs]
  │
  ▼
[resolve_and_hydrate_from_commit_snapshot]
  │
  ▼
[stage_all_outputs]  (per-step journal entry BEFORE each replace)
  │
  ▼
[invoke_hooks]  (Spec 009 extension point; MAY be no-op in Spec 008)
  │
  ▼
[seal_install_lock]
  │
  ▼
[publish_visibility_marker]  ◄── the SOLE publication event
  │
  ▼
[cleanup_staging]
  │
  ▼
END (success)


At any state above ↓
[crash] → next `haex install` or `haex verify --recover`
  │
  ▼
[replay_journal]  → determine last consistent state
  │
  ├── after publish_visibility_marker + marker present → retain generation, cleanup only
  ├── after seal_install_lock but no marker → publish marker (idempotent)
  └── earlier → roll back per-file replaces, restore prior gen, cleanup
```

**Invariants at every transition**:
- The exclusive lock is held from `[acquire_lock]` through `[cleanup_staging]`.
- Every filesystem mutation is preceded by its journal entry, fsynced.
- The visibility marker is the last publication step and the only publication event; journaled cleanup may follow but cannot change the published generation.

---

## Relationships between entities

- One `PlanSnapshot` ⇌ many `PlanStep`s (composition).
- One `PlanSnapshot` ⇌ one `CommitSnapshot` (compared for equality on published-digest fields).
- One install ⇌ one `install.mutex` file ⇌ one live `OwnerToken`.
- Many `JournalEntry`s ⇌ zero-or-one `PlanStep` (lifecycle entries carry no step reference).
- One successful install ⇌ one `VisibilityMarker` ⇌ one `InstallLock` (their digests cross-reference).
- One `InstallLock` ⇌ many `AtomInstallRecord`s ⇌ many `RootRecord`s.
- One `InstallLock` ⇌ one `OwnershipSet` ⇌ many `PathOwnershipRecord`s.

---

## Boundaries and non-goals

- **Publisher-hook payloads** (Spec 009 territory): `PlanStep.step_type = "hook_invoke"` reserves the slot; the payload shape is Spec 009's design decision. Spec 008 records the step type so recovery can identify hook-boundary journal entries but does not itself execute hooks.
- **Adapter output payloads** (Spec 010 territory): the plan step's `payload` for adapter-emitted files is opaque to Spec 008; the pipeline stages, digests, and publishes them per the transaction contract without introspecting content.
- **Cross-version migration** of `install.lock` and transaction state: **out of scope for Spec 008 under the project's pre-user policy.** A Spec 007-vintage `install.lock` fails Spec 008 schema validation (padded base64 digests, missing atoms shape) and the transaction refuses with `InstallLockSchemaInvalidError`. Legacy `.haex-hive/constitution-transaction.lock`/`.json` artefacts on a satellite are not recovered by `haex install`; operator recovery is to remove the stale files and re-run `haex constitution assemble`. If a future adopter requires an in-place migration path, it lands under an explicit `haex migrate` verb per Principle VI v1.3.0, not as an implicit tool-side rewrite.
