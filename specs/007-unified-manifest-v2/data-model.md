# Data Model: Unified Manifest v2 + Migration + Constitution Assemble

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-08-29

Every entity here corresponds to a concrete Python `dataclass` in `src/haex_hive/model/` and drives the JSON Schema in [contracts/](./contracts/). Field-level validation rules are stated once here and referenced from the schemas. Cross-references to design-doc decisions use the form "(D3)" and to spec FRs the form "(FR-002)".

## Entities

### ConsumerManifest

Represents the parsed content of `.haex-hive.json` v2. Root of the consumer-facing manifest world.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `haex_hive_version` | `Literal["2"]` | required | Must be the exact string `"2"` (FR-001). Any other value routes through `haex migrate` or refusal per FR-034. |
| `haex_hive_min_version` | `VersionConstraint` | optional | Grammar defined by `VersionConstraint` (see below); either `X.Y.Z` exact or `>=X.Y.Z` (FR-006). |
| `identity` | `AtomId`-shaped reverse-DNS string | required | Matches D3 reverse-DNS grammar; validated by `AtomId.parse_identity()`. |
| `atoms` | `list[AtomEntry]` | required | Zero or more entries. Empty is allowed (V.: opt-in-per-project); grants no external inheritance. |
| `groups` | `list[str]` | optional | Carried forward from v1 (Spec 004/005). Not consumed by any Spec-007 command. |
| `active_feature` | `str \| None` | optional | Carried forward from v1. Not consumed by any Spec-007 command. |
| `identity_note` | `str` | optional | Carried forward from v1 free-text field for operator notes. |

**Validation rules**:

- `ConsumerManifest` and its nested consumer-owned objects MUST set `additionalProperties: false` in their JSON Schema counterparts (FR-004). `InstallLock` deliberately permits unknown root fields so Spec 008 can extend it (FR-030).
- `identity` string MUST canonicalize to itself (idempotent under `AtomId.canonicalize()`); typographical variants like uppercase letters are refused with a diagnostic naming the acceptable form.

### AtomEntry

One row of `ConsumerManifest.atoms[]`. Represents a consumer's selection of one-or-more atoms from a single publisher-repo pinned at one revision.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `source` | `CanonicalSourceUrl` | required | Passes through `source_url.canonicalize()` (D3); canonical output accepts only lowercase `https` or `ssh`, and rejects userinfo or every other scheme. |
| `revision` | `str` (40-char lowercase hex) | required | Full commit SHA. 7-39-char short SHAs are refused by Spec 007's read path (only `haex migrate` expands them, at migration time). |
| `track` | `str \| None` | optional | Non-authoritative branch annotation. Never overrides `revision`. |
| `includes` | `list[AtomId]` | required, non-empty | Reverse-DNS atom-IDs. Length ≥ 1 (D12). |
| `config` | `dict[AtomId, ConfigEntry]` | optional, default `{}` | Keys MUST be atom-IDs that appear in this entry's `includes` OR are transitively resolved from a profile atom in `includes` (validated at resolve-time, not schema-time). |

**Validation rules**:

- `source` is stored in its canonicalized form; the JSON Schema uses a pattern that admits only the canonical shape (post-canonicalization).
- `revision` MUST match `^[0-9a-f]{40}$`.
- `includes` MUST contain no duplicate atom-IDs after normalization.

### ConfigEntry

Per-atom-ID entry inside `AtomEntry.config`. Split between two orthogonal surfaces: consumer-owned `priority` (D5 override) and publisher-schema-validated `values`.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `priority` | `int` | optional | Integer per D5; overrides the publisher's manifest default. Consumer schema-owned, NEVER validated by publisher `config_schema`. |
| `values` | `dict[str, Any]` | optional, default `{}` | Deep-merged onto publisher `defaults` per D7; validated against publisher's `config_schema` after merge. |

**Validation rules**:

- Only the two keys `priority` and `values` are permitted at this level (FR-005). Any other key is refused with `additionalProperties: false`.
- Publisher's `config_schema` MUST NOT declare a top-level `priority` property (D5). Enforced by an atom-manifest sanity check at read time, not by JSON Schema alone.

### PublisherManifest

Represents the parsed content of a publisher-repo's root `manifest.json`. Read from `git show <pinned-sha>:manifest.json` (or the manifest-path recorded elsewhere in future specs).

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `haex_hive_version` | `Literal["2"]` | required | Exact `"2"`. |
| `publisher` | `AtomId`-shaped reverse-DNS string | required | Namespace prefix under which all atoms in this publisher's `atoms` MUST live. |
| `atoms` | `dict[AtomId, PublisherAtomEntry]` | required | Maps every atom-ID this publisher offers to its internal path + version. |

**Validation rules**:

- Every key in `atoms` MUST have the `publisher` field as a proper reverse-DNS prefix (i.e., `atom-id.startswith(publisher + ".")`). Enforced at read time.
- `additionalProperties: false` at every object level.

### PublisherAtomEntry

Value type in `PublisherManifest.atoms`. Points at where the atom's own `manifest.json` lives in the publisher repo.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `path` | `RepoRelativePath` | required | Non-empty POSIX-style relative path; no `.`, `..`, or empty segments (FR-011). Points at the *directory* containing the atom's `manifest.json`, not at the file itself. |
| `version` | `str` (semver: `X.Y.Z`) | required | Atom's semver. |
| `description` | `str` | optional | Human-readable one-liner shown by `haex atoms list` (Spec 010; validated but not consumed here). |

### AtomManifest

Represents the parsed content of an individual atom's `manifest.json`. Read at `git show <sha>:<publisher_atom_path>/manifest.json`.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `haex_hive_version` | `Literal["2"]` | required | Exact `"2"`. |
| `id` | `AtomId` | required | Reverse-DNS. MUST equal the key under which the publisher's root manifest listed this atom (FR-021's consistency rule; enforced by `haex constitution assemble`). |
| `version` | `str` (semver: `X.Y.Z`) | required | Must equal the version the publisher's root manifest declared for this atom-ID. |
| `priority` | `int` | optional, default 100 | Publisher's default priority (D5). Consumer can override via `ConfigEntry.priority`. |
| `contributes` | `ContributesBlock` | required-or-omitted | Present unless this atom is a pure profile. See below. |
| `includes` | `list[AtomId]` | required-or-omitted | Profile composition. See below. |
| `defaults` | `dict[str, Any]` | optional, default `{}` | Publisher's default `values` for the atom's `config_schema`. |
| `config_schema` | `RepoRelativePath` | optional | Path to the JSON Schema Draft 2020-12 file (relative to the atom directory) describing `values`. Absent = no consumer configuration accepted. |

**Type-by-shape rule (D13)**:

- `contributes.constitution` set → constitution atom (participates in `haex constitution assemble`).
- `contributes.spec` set → spec atom (Spec 010 copies).
- `contributes.rules` / `.hooks` / `.skills` set → blueprint atom (Spec 010 hydrates).
- `includes` set → profile atom (transitive resolution).
- At least one of `contributes` or `includes` MUST be present. Both are allowed.

### ContributesBlock

Sub-entity of `AtomManifest.contributes`. Every field is optional; the combination present defines the atom's semantic role.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `constitution` | `RepoRelativePath` | optional | Path to the atom-relative constitution file (typically `constitution.md`). Consumed by Spec 007. |
| `spec` | `RepoRelativePath` | optional | Path to an atom-relative spec file. Consumed by Spec 010. |
| `rules` | `list[str]` (glob patterns) | optional | Consumed by Spec 010. Not touched by Spec 007. |
| `hooks` | `list[str]` (glob patterns) | optional | Consumed by Spec 009 dispatcher. Not touched by Spec 007. |
| `skills` | `list[str]` (glob patterns) | optional | Consumed by Spec 010. Not touched by Spec 007. |

### InstallLock

Represents the parsed content of `.haex-hive/install.lock` in the Spec-007 subset. Spec 008 will extend this with `atoms[]` and `generated_content_integrity`; Spec 007's write MUST preserve unknown top-level fields for forward compatibility (FR-030 forward-compat clause).

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `haex_hive_version` | `Literal["2"]` | required | Exact `"2"`. |
| `generated_by` | `str` | required | Format `"haex <version>"`, e.g. `"haex 2.0.0"` (FR-030). |
| `constitution` | `ConstitutionLockSection` | required-if-constitution-md-exists | Present whenever `.haex-hive/constitution.md` was assembled. Absent otherwise (in the future Spec 008 case where a repo declares no constitution atoms). |

### ConstitutionLockSection

Sub-entity of `InstallLock.constitution`. Records provenance for `.haex-hive/constitution.md`.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `sources` | `list[ConstitutionSource]` | required, non-empty | One row per contributing atom, unique and sorted by `ConstitutionSource.id` in bytewise UTF-8 order (FR-030). Length ≥ 1. |
| `assembled_by` | `AssembledBy` | required | Tool identity and semver for the assembly invocation (FR-029). |
| `content_integrity` | `str` (format: `sha256-<base64>`) | required | SHA-256 of D15's `haex-hive-tree-v1` one-file tree with regular-file mode `100644`, path `constitution.md`, and the produced raw bytes (R11). |

### ConstitutionSource

Sub-entity of `ConstitutionLockSection.sources[]`. One row per contributing atom.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `id` | `AtomId` | required | Reverse-DNS atom-ID whose manifest declared `contributes.constitution`. |
| `revision` | `str` (40-char lowercase hex) | required | Full commit SHA at which the constitution content was read. |
| `source` | `CanonicalSourceUrl` | required | Canonical form (D3) of the publisher repo URL. |

### ResolvedConstitutionContribution

In-memory-only assembly input. This entity is not serialized to `install.lock`; its `source` metadata is serialized there as a `ConstitutionSource` after successful publication.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `source` | `ConstitutionSource` | required | Provenance for this exact contribution. |
| `body` | `bytes` | required | Exact raw bytes read from the contribution file at `source.revision`. The single-source path copies these bytes unchanged after the FR-038 safety gate; multi-source adapters receive every body with its associated metadata. |

### MergeResult

In-memory-only return value from `MergeLLM.merge`. It prevents orchestration from treating an unreviewed adapter response as publishable content.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `candidate` | `bytes` | required | The full merged candidate body. It passes FR-038 and Principle-VIII validation before staging. |
| `confirmed` | `bool` | required | `true` only after the `stdio` adapter has displayed the final candidate and received an explicit affirmative operator confirmation. `false` causes `merge-not-confirmed` with no output write. |

### AssembledBy

Sub-entity of `ConstitutionLockSection`. Records the tool that produced the
constitution without placing metadata in the constitution body.

| Field | Type | Optional | Constraint / Source |
|---|---|---|---|
| `tool` | `Literal["haex"]` | required | Fixed assembler identity for Spec 007. |
| `version` | `str` (semver: `X.Y.Z`) | required | Installed `haex` version that assembled the output. |

### MigrationSidecar

Represents a v2-shaped proposal written to `.haex-hive.json.migrated`. Its content is a `ConsumerManifest`; no additional envelope. This "entity" is included here to give the Phase 2 tasks a stable term.

**Lifecycle** (FR-014–FR-018):

1. Write-mode `haex migrate` starts. If a prior `.haex-hive.json.migrated` exists, it is deleted before proceeding. `--dry-run` and `--check` preserve it.
2. The v2 proposal is built in memory as a `ConsumerManifest`.
3. The proposal is validated against `haex-hive.v2.schema.json`.
4. The proposal is serialized via `json_deterministic.dumps()`.
5. The serialized bytes are written to a `.haex-hive.json.migrated.<random>.tmp` file in the same directory.
6. `os.replace()` atomically moves the tmp into place as `.haex-hive.json.migrated`.
7. The unified diff between the original `.haex-hive.json` and the new sidecar is printed to stdout.
8. On any failure between (2) and (7), any tmp file is deleted and no `.haex-hive.json.migrated` is left in place.

### CanonicalSourceUrl

Value object, not a distinct entity. String-typed at the schema level; validated via `source_url.canonicalize(s) == s`.

Grammar (D3, R9):

- Canonical scheme is lowercase `https` or `ssh`; `git://` and every other scheme are refused.
- Host lowercase.
- Path has no trailing `/`.
- Path has no terminal `.git`.
- No userinfo component. During migration only, credential-free SCP remotes (`git@host:path`) and the SSH transport user (`ssh://git@host/path`) normalize to userinfo-free `ssh://host/path`; all other userinfo is refused.

### AtomId

Value object. String-typed at the schema level; validated via `AtomId.parse(s)`.

Grammar (D3, R8): `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$`, length ≤ 253, per-segment length ≤ 63, and every segment ends alphanumeric.

### VersionConstraint

Value object. String-typed at the schema level; validated via `VersionConstraint.parse(s)`.

Grammar (FR-006, R10): `^(?:>=)?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`. Two forms only: exact `X.Y.Z` and lower-bound `>=X.Y.Z`.

### RepoRelativePath

Value object. String-typed at the schema level; validated with a POSIX-only pattern plus a segment-walk rejection for `.`, `..`, empty segments, absolute paths, backslashes, drive-qualified paths, and control characters.

## Relationships

```text
ConsumerManifest 1 ─── * AtomEntry
                       │
                       │ .config (map keyed by AtomId)
                       │
                       * ── 1 ConfigEntry

ConsumerManifest 1 ─── 1 (references, does not embed) InstallLock

InstallLock      1 ─── 0..1 ConstitutionLockSection
ConstitutionLockSection 1 ─── * ConstitutionSource

PublisherManifest 1 ─── * PublisherAtomEntry (keyed by AtomId)
AtomManifest      1 ─── 0..1 ContributesBlock
AtomManifest      1 ─── * (transitively) AtomManifest via includes[]
```

Cross-manifest constraints (validated at read/resolve time, not by JSON Schema alone):

- `PublisherManifest.atoms[<atom-id>].version == AtomManifest.version` for the same atom-id.
- `PublisherManifest.atoms.<atom-id>` MUST have `<atom-id>` starting with `<publisher-manifest>.publisher + "."`.
- `AtomManifest.id == PublisherManifest`-key that referenced it.
- Every `AtomId` in `ConsumerManifest.atoms[i].includes[]` MUST resolve at `atoms[i].source@atoms[i].revision` via `PublisherManifest → PublisherAtomEntry → AtomManifest`.
- Every `AtomId` key in `ConsumerManifest.atoms[i].config[]` MUST resolve (directly or transitively via profile expansion) from `atoms[i].includes[]`.
- `InstallLock.constitution` exists only when an assembled `constitution.md` exists. A lock with no constitution sources may omit the section entirely.
- `ConstitutionLockSection.sources[]` is validated semantically after JSON Schema validation: IDs are unique and entries are bytewise UTF-8 sorted by ID.

## State transitions

Spec 007's entities are read-mostly. The two state-changing operations:

**haex migrate**: input state = v1 `.haex-hive.json` on disk. Output state = v2 `.haex-hive.json.migrated` sidecar on disk. Original file unchanged. Committed transition is a manual `mv` by the operator.

**haex constitution assemble**: input state = v2 `.haex-hive.json` + (via git) publisher manifests + atom manifests + constitution contribution files at pinned SHAs. Output state = updated `.haex-hive/constitution.md` + updated `.haex-hive/install.lock`. Both outputs land atomically via the pattern in R6.

**haex constitution show**: read-only. No state transition.

## Persistence

Every persistent entity lives in the consumer repo as a file, committed to git:

| Entity | On-disk location | Committed |
|---|---|---|
| ConsumerManifest | `.haex-hive.json` | yes |
| MigrationSidecar | `.haex-hive.json.migrated` | no (temporary review artifact; operator commits its content by `mv`ing over `.haex-hive.json`) |
| InstallLock | `.haex-hive/install.lock` | yes |
| Assembled constitution | `.haex-hive/constitution.md` | yes |
| PublisherManifest | (external repo) `manifest.json` at repo root | (external) |
| AtomManifest | (external repo) `<publisher_atom_path>/manifest.json` | (external) |

Non-persistent (in-memory only): every value object (`AtomId`, `CanonicalSourceUrl`, `VersionConstraint`, `RepoRelativePath`).
