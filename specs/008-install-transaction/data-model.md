# Data Model: Install Transaction Contract

**Feature**: Spec 008 — Install Transaction Contract
**Date**: 2026-08-31 (amended 2026-09-01)
**Purpose**: dataclass-level shapes and relationships for the install pipeline. Every persisted format has a matching JSON Schema under [contracts/](./contracts/); this file records the in-memory shapes and the state transitions of a running install.

---

## Entities

### ~~PlanSnapshot / CommitSnapshot / PlanStep~~ (retired)

**Retired by the trust-git amendment (2026-09-01) together with FR-006.** The digest-under-lock re-hash defence-in-depth these entities carried has no concrete threat model under the exclusive install lock + git-content-addressed publisher-clone delivery. The `install()` orchestration under this amendment reads `.haex-hive.json`, calls the existing constitution resolver, composes three files (`constitution.md`, `install.lock`, `visibility.json`), and hands them to `publish_generation` — no intermediate typed plan snapshot needed for a fixed-shape three-file publication.

If Spec 009 (hooks), Spec 010 (adapters), or a future requirement introduces a variable-shape multi-step publication, the plan structure is reinstated together with the requirement that motivates it. The dataclass code in `install/plan.py` is deleted by the follow-up code-cleanup PR.

### In-flight recovery state

Replaces the earlier `JournalEntry` + `PlanStep-to-JournalEntry mapping`
sections. There is no durable JSONL journal, no tail-hash chain, and no
sidecar file. The in-flight state of one participating output root is the
combination of three directory names beside that root:

| Directory | Meaning |
|---|---|
| `<root>/` | The currently-live generation. Its `visibility.json` names the published `generation_id`. |
| `<root>.next/` | A staged, fully-written generation with schema-compatible metadata, awaiting rename-in. |
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
| `generation_id` | `str` | Time-based and collision-checked; see R8. |
| `participating_roots` | `list[str]` | One entry per participating output root, e.g. `[".haex-hive/"]`. |
| `written_at` | `str` | UTC ISO 8601 for operator diagnostics; not used in verification. |

Per-root and per-marker content-integrity fields are retired by the 2026-09-01
trust-git amendment. Generated payload bytes come from pinned inputs and
canonical deterministic serialization; `generation_id` and `written_at` are
transaction metadata and may change only for a substantive publication.

### InstallLock

Slimmed shape of `.haex-hive/install.lock`. See [contracts/install-lock.v2.schema.json](./contracts/install-lock.v2.schema.json). Records the resolved atom set — the constitution block from Spec 007 plus `atoms[]`, `participating_roots`, and a `visibility_marker` cross-reference. No `content_integrity` fields per the 2026-09-01 trust-git amendment; deterministic generation from pinned inputs provides byte identity for generated payloads. Under the project's pre-user policy operator recovery from a corrupt/pre-amendment lock is to remove `.haex-hive/install.lock` and re-run `haex install`.

| Field | Type | Notes |
|---|---|---|
| `haex_hive_version` | `Literal["2"]` | Unchanged from Spec 007. |
| `generated_by` | `str` | e.g. `"haex 2.1.0"`. |
| `constitution` | `ConstitutionBlock` | Spec 007 shape without `content_integrity`; the constitution's `sources` + `assembled_by` are recorded, and its committed/pinned candidate is serialized deterministically. |
| `atoms` | `list[AtomInstallRecord]` | Per-atom install detail. |
| `generation_inputs` | `list[GenerationInputIdentity]` | Immutable adapter and tool-configuration identities used for generated payloads, sorted by `(kind, id)` and validated before publication. |
| `participating_roots` | `list[str]` | Output-root names, e.g. `[".haex-hive/"]`. Matches `VisibilityMarker.participating_roots` byte-identically. |
| `visibility_marker` | `VisibilityMarkerRef` | `{ "generation_id": "..." }` — cross-reference by id only. |

### AtomInstallRecord

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Reverse-DNS atom id. |
| `source` | `str` | Publisher repo URL. |
| `revision` | `str` | Full 40-char SHA. |
| `contributed_paths` | `list[str]` | Repo-relative paths this atom contributed under participating roots. |

No `content_integrity` per the trust-git amendment; the `revision` git SHA is
the input-byte anchor, and the adapter/tool configuration plus serialization
must be deterministic.

### GenerationInputIdentity

Every generated payload has a sealed input identity in addition to the atom
records above. This identity is recorded in the generation input envelope
used by `install.lock` whenever adapter output participates in the
publication; it is not an output `content_integrity` field.

| Field | Type | Notes |
|---|---|---|
| `kind` | `Literal["adapter", "tool-config"]` | Which generator input is being pinned. |
| `id` | `str` | Stable reverse-DNS adapter id or canonical tool-config id. |
| `revision` | `str` | Immutable identity: `git:<40 lowercase hex SHA>` for adapter code, or `sha256:<64 lowercase hex>` of canonical tool-config bytes. |
| `serialization` | `SerializationProfile` | Exact deterministic serialization settings used by the generator before its bytes are sealed. |

The `generation_inputs` record is sorted by `(kind, id)` and validated before
generation. The adapter revision, tool-config revision, atom revisions, and
their canonical serialization settings used for a candidate MUST equal the
identities recorded in the envelope; a mismatch refuses generation. The
envelope, including these settings, MUST be constructed before
`seal_install_lock_inside_next` and the exact validated envelope MUST be passed
to T029; the seal step MUST NOT infer or rewrite it.
No wall-clock value, random value, environment value, or filesystem ordering
may be used to derive these identities.

### SerializationProfile

The canonical profile is explicit rather than an implicit tool default:

| Field | Type | Notes |
|---|---|---|
| `format` | `Literal["json", "text", "toml"]` | Payload serialization format. |
| `encoding` | `Literal["UTF-8"]` | No platform-default encoding. |
| `newline` | `Literal["LF"]` | Line endings are normalized before bytes are sealed. |
| `key_order` | `Literal["lexicographic-utf8", "not-applicable"]` | JSON/TOML keys use bytewise UTF-8 order; text has no keys. |
| `indent` | `int \| None` | JSON/TOML indentation width, or `null` for compact/text output. |
| `ensure_ascii` | `bool` | Explicit Unicode escaping policy. |

For the shared JSON serializer used by `install.lock` and `visibility.json`,
the profile is `{format: "json", encoding: "UTF-8", newline: "LF",
key_order: "lexicographic-utf8", indent: 2, ensure_ascii: false}`. Any
different profile is a different generation input and must be rejected unless
the resulting profile is explicitly pinned in the envelope.

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
[resolve_and_hydrate]
  │
  ▼
[validate_generation_inputs]  (construct and validate the complete envelope, including serialization profiles)
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
[write_visibility_marker_inside_next]  (write .haex-hive.next/visibility.json)
  │
  ▼
[validate_staged_generation]  (schema-compatible marker/lock and available roots)
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
[crash] → next `haex install` or `haex verify --recover`
  │
  ▼
[resolve_in_flight_state]  → read <root>{,.next,.prev} presence
  │
  ├── row 3 of §R7 (mid-swap, <root>/ absent) → validate availability and complete forward, or refuse
  ├── row 4 of §R7 (post-swap, <root>.prev/ still present) → cleanup, or restore an available previous generation
  ├── row 2 of §R7 (staged but pre-swap) → restore mixed-root pointers, delete <root>.next/, plan afresh
  ├── row 5 of §R7 (both live and staged absent) → restore an available previous generation
  ├── row 7 of §R7 (first install, <root>/ and <root>.prev/ absent) → validate availability and complete forward, or refuse
  └── other rows → per §R7 state table
```

**Invariants at every transition**:
- The exclusive lock is held from `[acquire_lock]` through `[cleanup_prev]`.
- Every rename that transitions between the three directory names is followed by a parent-directory fsync before the next state is entered.
- `[validate_generation_inputs]` constructs the complete envelope before any lock seal and rejects any adapter revision, tool-configuration revision, atom revision, or canonical serialization profile that differs from it; T029 serializes the exact validated envelope.
- The `[rename_B]` step (`os.rename(<root>.next, <root>)`) is the sole publication event; `[cleanup_prev]` follows but cannot change the published generation and is idempotent under recovery.

---

## Relationships between entities

- One install ⇌ one `install.mutex` file ⇌ one live `OwnerToken`.
- One in-flight install ⇌ at most one `<root>.next/` and one `<root>.prev/` beside each haex-owned root; mixed-ownership roots use the retained overlay generations and pointers defined by R3 (see §In-flight recovery state).
- One successful install ⇌ one `VisibilityMarker` ⇌ one `InstallLock` (cross-referenced by `generation_id`).
- One `InstallLock` ⇌ many `AtomInstallRecord`s.
- ~~`PlanSnapshot` / `CommitSnapshot` / `PlanStep` / `OwnershipSet` / `PathOwnershipRecord`~~ — retired by the 2026-09-01 trust-git amendment.

---

## Boundaries and non-goals

- **Publisher-hook payloads** (Spec 009 territory): hook execution happens while `<root>.next/` is being materialised — whatever the hook produces lands in `.next/` and is committed atomically by the rename-swap. Spec 009 defines the hook-invocation surface; Spec 008 does not need a typed plan step to reserve it.
- **Adapter output payloads** (Spec 010 territory): adapter-emitted files land in `.next/` alongside constitution.md; the rename-swap commits them atomically. Any per-adapter ownership or overlay-pointer bookkeeping is Spec 010's design decision.
- **Cross-version migration** of `install.lock` and transaction state: **out of scope for Spec 008 under the project's pre-user policy.** A Spec 007-vintage `install.lock` fails Spec 008 schema validation (missing the amended atom/root shape) and the transaction refuses with `InstallLockSchemaInvalidError`. If a future adopter requires an in-place migration path, it lands under an explicit `haex migrate` verb per Principle VI v1.3.0, not as an implicit tool-side rewrite.
