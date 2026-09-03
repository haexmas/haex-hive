# Data Model: Install Transaction Contract

**Feature**: Spec 008 — Install Transaction Contract
**Date**: 2026-08-31 (amended 2026-09-02)
**Purpose**: dataclass-level shapes and relationships for the install pipeline. Every persisted format has a matching JSON Schema under [contracts/](./contracts/); this file records the in-memory shapes and the state transitions of a running install.

---

## Entities

### ~~PlanSnapshot / CommitSnapshot / PlanStep~~ (retired)

**Retired by the trust-git amendment (2026-09-01) together with FR-006.** The digest-under-lock re-hash defence-in-depth these entities carried has no concrete threat model under the exclusive install lock + git-content-addressed publisher-clone delivery. The `install()` orchestration under this amendment reads `.haex-hive.json`, resolves the complete output set (including configuration, generated molecule files, adapter files, and `constitution.md`), stages every caller-supplied file before writing `install.lock` last, and hands the staged view to `publish_generation` — no intermediate typed plan snapshot is needed for this publication.

If Spec 009 (hooks), Spec 010 (adapters), or a future requirement introduces a variable-shape multi-step publication, the plan structure is reinstated together with the requirement that motivates it. The dataclass code in `install/plan.py` is deleted by the follow-up code-cleanup PR.

### In-flight recovery state

Superseded 2026-09-02 by the detect+retry amendment (research.md §R7). There
is no durable JSONL journal, no state-table dispatcher, and no per-state
recovery action. The in-flight state of one haex-owned output root is
simply the presence or absence of two same-filesystem siblings beside the
live directory:

| Directory | Meaning |
|---|---|
| `<root>/` | The currently-live generation. Its `install.lock` names the published `generation_id`. |
| `<root>.next/` | Leftover staging directory from a crashed prior install; deleted before the next install builds its candidate. |
| `<root>.prev/` | Previous published generation retained after a mid-swap crash; kept until a replacement is successfully published. |

The recovery primitive is `install.inflight.clean_stale_siblings(live)`. It
removes stale `<root>.next/`, fsyncs the parent, and returns whether the
previous sibling was present (for diagnostics). The subsequent regular install
pipeline runs to completion and produces a valid generation deterministically
from the pinned inputs. If resolution or staging fails, `<root>.prev/` remains
available; after successful publication, stale siblings are removed.

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

### InstallLock

The 2026-09-03 amendment is the authoritative Spec 008 definition of
`.haex-hive/install.lock` and supersedes Spec 007's pre-amendment
`generated_by`/`constitution` shape. See
[contracts/install-lock.v2.schema.json](./contracts/install-lock.v2.schema.json).
The lock records only the published generation and the molecules that wrote
consumer-repository-root-relative paths. A legacy lock is non-authoritative:
the FR-005 schema/migration gate rejects unsupported versions, retired fields,
and required migrations before recovery or a reader uses its generation.

| Field | Type | Notes |
|---|---|---|
| `haex_hive_version` | `Literal["2"]` | Current install-lock schema version. Unsupported values fail the FR-005 schema/migration gate. |
| `generation_id` | `str` | Unique, time-based `g_YYYYMMDDTHHMMSSZ_<4-hex>` generation identifier. |
| `molecules` | `list[MoleculeInstallRecord]` | One record per resolved molecule; sorted by `(id, source, revision, paths)` and free of duplicate records. |

### MoleculeInstallRecord

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Reverse-DNS molecule id. |
| `source` | `str` | Publisher repo URL. |
| `revision` | `str` | Full 40-char SHA. |
| `paths` | `list[str]` | Deterministically ordered, unique POSIX paths relative to the consumer repository root that this molecule wrote. |

The `molecules` array is canonically ordered by the lexicographic tuple
`(id, source, revision, paths)`, with the already-canonical `paths` sequence as
the final tie-breaker. Duplicate tuples are rejected rather than preserved in
input order. The molecule revision is the immutable input-byte anchor under
Principle IV; deterministic generation and canonical serialization provide
byte identity without recording generation-input metadata in the lock.

---

## State machine of a running install

```text
START
  │
  ▼
[acquire_lock]  ──── on stale lease → [reclaim_lease] ──┐
  │                                                     │
  ▼                                                     ▼
[clean_stale_siblings]  ◄──── remove <root>.next/; retain <root>.prev/
  ▼
[resolve_and_hydrate]
  │
  ▼
[validate_install_lock_projection]  (validate the current schema and canonical molecule records)
  │
  ▼
[materialise_haex_root_next]  (write haex-owned files into <root>.next/, fsync)
  │
  ▼
[materialise_overlay_generations]  (write only adapter-owned paths for mixed roots)
  │
  ▼
[invoke_hooks]  (Spec 009 extension point; MAY be no-op in Spec 008)
  │
  ▼
[seal_install_lock_inside_next]  (write .haex-hive.next/install.lock)
  │
  ▼
[validate_staged_generation]  (schema-valid install.lock and available recorded paths)
  │
  ▼
[publish_overlay_pointers]  (swap mixed-root pointers; preserve unowned siblings)
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
[crash] → next `haex install`
  │
  ▼
[clean_stale_siblings]  → remove <root>.next/, retain <root>.prev/
  │
  ▼
[resolve_and_hydrate]  → on failure, refuse and preserve <root>.prev/
  │
  ▼
[stage_and_validate]  → on failure, refuse and preserve <root>.prev/
  │
  ▼
[rename_A] / [rename_B] / [cleanup_prev]  → publish and then remove stale siblings
```

**Invariants at every transition**:
- The exclusive lock is held from `[acquire_lock]` through `[cleanup_prev]`.
- Every rename that transitions between the three directory names is followed by a parent-directory fsync before the next state is entered.
- `[validate_install_lock_projection]` validates the current install-lock schema and canonical molecule ordering before the lock is sealed; retired fields and required migrations refuse publication.
- The `[rename_B]` step (`os.rename(<root>.next, <root>)`) is the sole publication event; `[cleanup_prev]` follows but cannot change the published generation and is idempotent under retry.

---

## Relationships between entities

- One install ⇌ one `install.mutex` file ⇌ one live `OwnerToken`.
- One in-flight install ⇌ at most one `<root>.next/` and one `<root>.prev/` beside each haex-owned root; mixed-ownership roots use the retained overlay generations and pointers defined by R3 (see §In-flight recovery state).
- One successful install ⇌ one `InstallLock` whose `generation_id` is the publication boundary.
- One `InstallLock` ⇌ many `MoleculeInstallRecord`s.
- ~~`PlanSnapshot` / `CommitSnapshot` / `PlanStep` / `OwnershipSet` / `PathOwnershipRecord`~~ — retired by the 2026-09-01 trust-git amendment.

---

## Boundaries and non-goals

- **Publisher-hook payloads** (Spec 009 territory): hook execution happens while `<root>.next/` is being materialised — whatever the hook produces lands in `.next/` and is committed atomically by the rename-swap. Spec 009 defines the hook-invocation surface; Spec 008 does not need a typed plan step to reserve it.
- **Adapter output payloads** (Spec 010 territory): adapter-emitted files land in `.next/` alongside constitution.md; the rename-swap commits them atomically. Any per-adapter ownership or overlay-pointer bookkeeping is Spec 010's design decision.
- **Cross-version migration** of `install.lock` and transaction state: **out of scope for Spec 008 under the project's pre-user policy.** A Spec 007-vintage `install.lock` fails the FR-005 schema/migration gate because it uses retired fields instead of the amended molecule shape, and the transaction refuses with `InstallLockSchemaInvalidError`. If a future adopter requires an in-place migration path, it lands under an explicit `haex migrate` verb per Principle VI v1.3.0, not as an implicit tool-side rewrite.
