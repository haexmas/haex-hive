# Data Model: Multi-Spec External-Ref

**Phase**: 1 (planning)
**Spec**: [spec.md](spec.md)
**Research**: [research.md](research.md)

Every entity and relationship materialised by Spec 006, with the
validation rules the CLI enforces at read/write. Groups the model
into three layers: config (versioned), state (device-local), and
runtime (in-memory).

## Layer A — Versioned config

### Entity: `HaexHiveConfig`

The consumer-owned `.haex-hive.json` file. Extended by Spec 006 to
allow a new entry role but backwards-compatible with Spec 004 shape
(FR-033).

**Location**: consumer repo root, committed.

**Fields**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `haex_hive_version` | string | Yes | `"1"` in Spec 006; reserved for future schema evolution. |
| `identity` | string | Yes | Consumer's own git identity (repository URL or `.harness-id` opaque token). Unchanged from Spec 004. |
| `harness_sources` | array of `HarnessSourceEntry` | Yes | May be empty. Empty means "opted in, no permissions granted" (Spec 004 wording). |
| `groups` | array | Yes | Reserved; empty in Spec 006. |
| `active_feature` | string \| null | Yes | Reserved (per haex-hive session-instructions convention). |

**Validation**:

- Root object schema-validated against `haex-hive.schema.json` (see
  [contracts/haex-hive.schema.json.patch.md](contracts/haex-hive.schema.json.patch.md))
- Unknown top-level keys rejected (`additionalProperties: false`)
- Discriminated union for `harness_sources[]` (see next entity)

**State transitions**:

- Written by `haex-init` (Spec 005) on initial project bootstrap
- Mutated by `haex-init add-source` (Spec 006, FR-028–FR-032)
- Mutated by `haex-init --pin-constitution` (Spec 005) — unaffected
  by Spec 006
- Read by `haex-init sync` (Spec 006), `spec-resolve resolve`
  (Spec 004 + extensions), `spec-resolve prefetch` (Spec 004 +
  extensions), `spec-resolve status`

---

### Entity: `HarnessSourceEntry` (discriminated union)

One element of `HaexHiveConfig.harness_sources[]`. Three variants,
distinguished by `role`:

#### Variant A — Legacy Constitution entry (`role: "constitution"`)

Spec 004 shape, retained unchanged (FR-033).

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | const `"constitution"` | Yes | |
| `repository` | string | Yes | `"self"` for self-ref, or git URL. |
| `revision` | string | Yes | Full 40-hex-char SHA (Principle IV). |
| `path` | string | Yes | Repo-relative POSIX path to the constitution file. |

**Validation**: same as Spec 004. Rejects `external-harness`-only
fields (`name`, `auto_include`, `additional_include`, `items`).

#### Variant B — Legacy permission-only entry (no `role`)

Spec 004 shape, retained unchanged (FR-033).

| Field | Type | Required | Notes |
|---|---|---|---|
| `repository` | string | Yes | Git URL. `"self"` NOT permitted here (Spec 004 rule). |
| `revision` | string | Optional | Full 40-hex-char SHA if present. |
| `paths` | array of string | Optional | Non-empty when present. Repo-relative POSIX paths. |

**Validation**: rejects `external-harness`-only fields.

#### Variant C — New External-Harness entry (`role: "external-harness"`)

Spec 006's new variant.

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | const `"external-harness"` | Yes | Discriminator. |
| `repository` | string | Yes | Git URL. SSH or credential-free HTTPS. HTTPS URLs with embedded userinfo rejected before write (FR-007, Research §10). `"self"` NOT permitted. |
| `revision` | string | Yes | Full 40-hex-char SHA (Principle IV, FR-002). |
| `name` | string | No (defaulted) | Single platform-safe path component. Defaults to repository URL basename with `.git` suffix stripped. Validated per FR-008. |
| `auto_include` | string \| null | No | One of the documented presets. Currently only `"speckit-defaults"` (FR-004). Null / omitted = no auto-include. |
| `additional_include` | array of string | No | Repo-relative POSIX paths or globs (FR-005, Research §6). Defaults to `[]`. |
| `items` | array of `ItemDeclaration` | No | Explicit item entries. Defaults to `[]`. |

**Validation** (schema + CLI, additive):

- At least one of `auto_include`, non-empty `additional_include`,
  or non-empty `items` MUST hold (Research §8).
- `repository` MUST NOT be `"self"`.
- `revision` regex: `^[0-9a-f]{40}$`.
- `name` regex: `^[A-Za-z0-9._-]+$` PLUS the platform-reserved-name
  filter from FR-008 (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`,
  `LPT1`–`LPT9`, case-insensitive).
- `auto_include` MUST be `"speckit-defaults"` or absent in Spec 006.
- `additional_include` entries validated per FR-005 grammar
  (POSIX path, no absolute, no `..` traversal, glob syntax per
  Research §6).
- `items[]` element validation — see next entity.

---

### Entity: `ItemDeclaration`

One element of `HarnessSourceEntry.items[]` (Variant C only).

| Field | Type | Required | Notes |
|---|---|---|---|
| `role` | string | Yes | Item-level role: `constitution`, `workflow`, `template`, `skill`, `doc`, `spec`, or `other`. Unknown values pass schema (extension-friendly). |
| `path` | string | Yes | Repo-relative POSIX path to the file (or directory) in the producer. |
| `as` | string | Yes | Alias: `^[a-z0-9][a-z0-9-]*$` (FR-006, Clarify Q2). |

**Validation**:

- `path` MUST NOT be absolute or contain `..`.
- `path` MUST resolve to a regular file or directory in the pinned
  tree at `sync` time (FR-026 case b).
- `as` MUST be unique across all `items[]` inside this entry
  (FR-020 collision check).
- The final key `<name>:<as>` MUST be globally unique across every
  entry in the consumer's `.haex-hive.json` (FR-020 global
  collision check).

---

## Layer B — Device-local state

### Entity: `LocalStateTable`

The device-local `.haex-hive.local.json` inside each consumer
project. Gitignored (FR-018). Regenerated atomically by `haex-init
sync` (FR-024).

**Location**: consumer repo root, gitignored.

**Fields**:

| Field | Type | Required | Notes |
|---|---|---|---|
| `haex_hive_local_version` | string | Yes | `"1"` in Spec 006. |
| `generated_from_config` | string | Yes | `sha256:<64-hex-char>` of the consumer's `.haex-hive.json` at generation time. |
| `generated_at` | string | Yes | ISO 8601 timestamp of generation. |
| `device` | string | Yes | Device identifier (hostname, or a persistent device id if configured). Informational only. |
| `state_area` | string | Yes | Absolute path to `$HAEX_HIVE_STATE` at generation time. Enables tools to detect state-area migration. |
| `constitutions` | array of `ConstitutionSource` | Yes | Ordered emission list for session-start (FR-011). May be empty. |
| `resolved` | object | Yes | Map from ref key to absolute path. See below. |

**`resolved` map keys** (deterministic per FR-020):

- Explicit items: `<name>:<as>` — e.g., `secana-specs:constitution`,
  `secana-specs:plan-review-workflow`
- Auto-include and additional-include expansion: `<name>:path:<repo-relative-path>`
  — e.g., `secana-specs:path:.specify/workflows/plan-review.md`,
  `secana-specs:path:tools/harness-evaluator/README.md`
- Tie-break for path key = alias key on same source file: alias
  wins; path key omitted (Research §8, encoded in FR-020's "with a
  documented tie-break")

**`resolved` map values**: absolute filesystem paths inside
`$HAEX_HIVE_STATE/repos/<name>/.extracts/@<sha>/…`. For directory
items, the path is the directory itself (not enumerated); the agent
walks it.

**Validation**:

- Schema-validated against
  [contracts/haex-hive-local.schema.json.md](contracts/haex-hive-local.schema.json.md)
- Every value in `resolved` MUST be an absolute path
- Written atomically per FR-024 (Research §3)
- After write, mode is `0600` on Unix-like (FR-038, Research §4)

---

### Entity: `ConstitutionSource`

One element of `LocalStateTable.constitutions[]`. Two subtypes.

| Field | Type | Required | Notes |
|---|---|---|---|
| `source` | `"role"` \| `"resolved"` | Yes | Discriminator. |
| `role` | `"constitution"` | Required when `source: "role"` | Reference to the top-level `role: "constitution"` entry (there is at most one per consumer). |
| `key` | string | Required when `source: "resolved"` | The resolved key of an `items[]` entry whose item-level `role` is `"constitution"`. |
| `label` | string | Yes | Human/agent-facing label emitted between documents. Format per Research §7. |

**Validation**:

- Order preserved per FR-011: top-level `role: "constitution"`
  entry first (if any), then nested `items[]` entries in
  `harness_sources[]` order and `items[]` order
- `label` values generated from the source's identity (see Research
  §7 for exact format)
- `constitutions` array is deterministic — the same config produces
  the same array

---

### Entity: `ProducerClone`

The device-local full clone at `$HAEX_HIVE_STATE/repos/<name>/`.

**Location**: `$HAEX_HIVE_STATE/repos/<name>/` on each device.
Shared across all consumers on the device that reference the same
producer under the same storage name.

**Structure**:

```
$HAEX_HIVE_STATE/repos/<name>/
├── .git/                                  # full history, no --depth
├── <producer working-tree files>          # at HEAD of default branch, browsable
├── .extracts/@<sha>/                      # per-pinned-SHA extract subtree
│   └── <path-in-producer>                 # extracted regular files
└── .sync.lock                             # advisory OS-lock file (Research §2)
```

**Validation before reuse**:

- Directory exists and is a git working tree (`git -C <path>
  rev-parse --is-inside-work-tree` returns `true`)
- `git -C <path> remote get-url origin` equals the declared
  `repository:` URL of every entry referencing this clone
  (FR-014). On mismatch, `haex-init sync` refuses.

**State transitions**:

- Created on first `haex-init sync` referencing a new
  `repository:` + `name:` pair
- Fetched (`git fetch origin`) on every `haex-init sync` before
  pinned-SHA reachability check
- Working tree kept at default branch tip after fetch (best-effort
  fast-forward; if not fast-forwardable — because operator has
  local commits — `sync` skips checkout and logs a note)
- Never deleted by Spec 006 code paths

---

### Entity: `ExtractSubtree`

Per-pinned-SHA content extraction underneath a `ProducerClone`.

**Location**: `$HAEX_HIVE_STATE/repos/<name>/.extracts/@<sha>/`

**Structure**: mirrors the producer's tree at `<sha>`, but only
containing files that at least one consumer's expansion selected.
Not a full checkout.

**Population**:

- Created lazily on first `haex-init sync` that resolves a ref
  requiring content from `<sha>`
- Files are written via `git cat-file blob <sha>:<path>` piped to a
  temp file, then atomically renamed (Research §3, FR-023)
- Existing extract files at the correct path with byte-length
  matching git-object length are reused without re-extraction
  (idempotency — FR-021)
- Modes: `0700` on directory creation, `0600` on file after rename
  (FR-038, Research §4)

**Cleanup**: not performed by Spec 006 (cache-eviction is NG-5).
Old extract SHAs remain on disk until manually removed.

---

## Layer C — Runtime (in-memory during CLI invocation)

### Entity: `ExpansionPlan`

Constructed by `haex-init sync` after config parsing, before any
mutation. Enumerates every resolved key and its target path.

**Fields**:

- `entries: List[EntryPlan]` — one per `harness_sources[]` element
- `constitution_sources: List[ConstitutionSource]` — the ordered
  emission list

**Validation** (preflight per FR-022):

- Every key in every `EntryPlan.resolved_keys` is unique across
  all entries (FR-020 global collision check)
- Every `EntryPlan.explicit_paths` maps to a regular file / dir in
  the pinned tree (FR-026 case b)
- Every `EntryPlan.include_matches` non-empty per glob (FR-005),
  no symlink/non-regular (FR-026 case d)
- Every `EntryPlan.repository` name-URL mapping is unambiguous
  (FR-026 case e/f)

Constructed and validated **before** any temp file is written or
any `.haex-hive.local.json` is touched. On failure: exit non-zero
with structured diagnostic per FR-027a, no side effects.

### Entity: `EntryPlan`

One per `HarnessSourceEntry` in the consumer's config.

**Fields**:

- `entry_variant: "constitution" | "permission-only" | "external-harness"`
- `repository: str`, `revision: str`, `name: str`
- `clone_path: Path` — resolved absolute path under
  `$HAEX_HIVE_STATE/repos/<name>/`
- `resolved_keys: Dict[str, ResolvedPath]` — for
  `external-harness` variants only
- `constitution_sources: List[ConstitutionSource]` — zero or one
  entries contributed to `ExpansionPlan.constitution_sources`

### Entity: `ResolvedPath`

One entry in the final `LocalStateTable.resolved` map.

**Fields**:

- `key: str` — the resolved key
- `absolute_path: str` — the target extract path
- `source_item_kind: "explicit-item" | "auto-include" | "additional-include"`
- `source_role: str | None` — item-level role for explicit items;
  None for include-expansion matches
- `git_object_sha: str` — the git blob SHA (for extract-reuse
  detection during idempotent re-sync)

---

## Relationships

- **`HaexHiveConfig`** 1─N **`HarnessSourceEntry`** (in
  `harness_sources[]`)
- **`HarnessSourceEntry`** (Variant C) 0─N **`ItemDeclaration`**
  (in `items[]`)
- **`HaexHiveConfig`** 1─1 **`LocalStateTable`** (per device, per
  consumer)
- **`LocalStateTable`** 1─N **`ConstitutionSource`** (in
  `constitutions[]`, ordered)
- **`LocalStateTable.resolved`** N─1 **`ExtractSubtree`** (many
  resolved keys point into one extract subtree per SHA)
- **`HarnessSourceEntry`** N─1 **`ProducerClone`** (many entries
  across many consumers on the device can share one clone,
  discriminated by `name` + verified `origin.url`)
- **`ProducerClone`** 1─N **`ExtractSubtree`** (one per pinned SHA
  in use)

## State-transition summary

| From | To | Trigger |
|---|---|---|
| No `.haex-hive.json` | Bootstrapped (Spec 005 shape) | `haex-init` invocation |
| `.haex-hive.json` with no `external-harness` entries | Same, with new `external-harness` entry | `haex-init add-source` (Spec 006) |
| `.haex-hive.json` with `external-harness` entries, no local state | Same, with `.haex-hive.local.json` + populated `ProducerClone` + `ExtractSubtree` | `haex-init sync` (Spec 006) |
| `.haex-hive.local.json` at SHA A | `.haex-hive.local.json` at SHA B | Operator bumps `revision:` in `.haex-hive.json`, runs `haex-init sync` |
| Any state, mid-`haex-init sync` failure | Prior state (100% intact per SC-003) | Any refusal or preflight failure |

## Terminology (canonical)

- **Producer** — external repository declared in a consumer's
  `external-harness` entry
- **Consumer** — repository that owns a `.haex-hive.json` and
  declares producers
- **State area** — device-local `$HAEX_HIVE_STATE` root
- **Producer clone** — `$HAEX_HIVE_STATE/repos/<name>/` full git
  working tree at producer's default branch tip
- **Extract subtree** — `.extracts/@<sha>/…` under a producer
  clone, per-pinned-SHA content extraction
- **Resolution table** — the device-local `.haex-hive.local.json`
- **Resolved key** — deterministic string identifier of one
  inherited file (or directory)
- **Storage name** — the `name` field of an `external-harness`
  entry; the directory under `state-area/repos/`
- **Item alias** — the `as:` field of an `ItemDeclaration`;
  contributes to a resolved key
- **Auto-include preset** — a documented named set of paths
  (currently only `"speckit-defaults"`)
