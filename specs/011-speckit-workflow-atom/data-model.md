# Data Model: Speckit workflow molecule (simplified)

**Feature**: Spec 011 (simplified, PR #54 merged)
**Date**: 2026-09-02
**Purpose**: Dataclass-level shapes and relationships for the workflow subpackage. Every persisted format has a matching contract under [contracts/](./contracts/); this file records the in-memory shapes.

---

## Entities

### WorkflowMoleculeManifest

Runtime representation of a workflow molecule's v3 `atoms` map. Specialises `MoleculeManifest` from Spec 007. Constructor validates every source path via `RepoRelativePath.validate` + containment against the molecule root; at publication time the resolver re-validates destinations against the consumer repo root.

| Field | Type | Notes |
|---|---|---|
| `molecule_id` | `str` | Reverse-DNS id per Spec 007. |
| `molecule_revision` | `str` | Full 40-char SHA (Principle IV). |
| `workflow_path` | `str` | The single repo-relative path from `atoms.workflow`; exactly one path is required for a workflow molecule. |
| `constitution_paths` | `tuple[str, ...]` | Optional constitution fragment paths. |
| `extensions_path` | `str \| None` | The optional single repo-relative path from `atoms.extensions`. |
| `hook_paths` | `tuple[str, ...]` | Optional hook file paths. |

**Construction rules**: invalid path fields raise `WorkflowMoleculeManifestPathError` (Principle II diagnostic). `ConsumerManifest.from_json` validates only consumer-owned fields and does not inspect publisher content. After molecule resolution, `WorkflowMoleculeManifest` loading/validation MUST reject a molecule carrying `extensions_path` or `hook_paths` without `workflow_path`, with the same path diagnostic, before fragment loading or staging.

### WorkflowFragment

Parsed representation of the molecule's contributed `extensions.yml`.

| Field | Type | Notes |
|---|---|---|
| `molecule_id` | `str` | Source molecule. |
| `molecule_revision` | `str` | Full 40-char SHA. |
| `required_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `optional_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Keyed by stage; entries retain in-fragment declaration order. |

Duplicate `(id,)` within `required_extensions` or `optional_extensions` raises `WorkflowMoleculeExtensionIdCollisionError`. The same id across the two lists is normalized as one required requirement: the generated output contains one `required_extensions[]` entry, and compatible required/optional declarations both appear in that entry's `sources[]` with their original kinds. An incompatible optional declaration is dropped with a warning while the required declaration remains. Duplicate hook identity within a single stage raises `WorkflowHookMappingInvalidError`.

### ExtensionRequirement

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Extension id. |
| `version_constraint` | `VersionConstraint` | Parsed per Spec 007 grammar. Unparseable raises `InvalidConstraintError`. |
| `homepage` | `str \| None` | Optional URL for diagnostics. |
| `kind` | `Literal["required", "optional"]` | Which list this entry came from. |

### HookEntry

| Field | Type | Notes |
|---|---|---|
| `stage` | `str` | Enum of legal stages (`before_specify` etc.). |
| `extension` | `str \| None` | Extension id that owns the hook; nullable for local-only hooks. |
| `command` | `str` | Dotted command name. |
| `script_path` | `str` | Canonical published repo-relative path. For molecule hooks, the loader converts the fragment's molecule-root-relative `script` to `.specify/extensions/workflow-molecules/<molecule-id>/<script>`; for local hooks, it normalizes the consumer-root-relative path against the local hook base. |
| `origin` | `Literal["molecule", "local"]` | Provenance required for generated hook entries. |
| `enabled` | `bool` | Defaults true. |
| `optional` | `bool` | Defaults true for molecule-contributed hooks. |
| `description` | `str` | Operator-facing description. |
| `prompt` | `str \| None` | Optional confirmation prompt. |

The normalization happens before a `WorkflowFragment` becomes a `HookEntry`.
Local entries are normalized by the same loader boundary. The generated YAML
serializes `script_path` as its `script` value, so fragment/local replacement
and generated output all use the same canonical path. Identity is
`(stage, extension, command, script_path)` after normalization, per R8.

### LocalExtensionsSource

Parsed `.specify/extensions.local.yml`. When the file is absent, an empty instance is returned. NEVER mutated by the runtime.

| Field | Type | Notes |
|---|---|---|
| `installed` | `list[str]` | Locally-installed extension ids (informational). |
| `settings` | `dict[str, Any]` | Local-only settings, passed through to the generated file. |
| `required_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `optional_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Local hook entries. Duplicate identity within one stage refuses at load. |
| `source_bytes` | `bytes \| None` | Exact bytes loaded from `.specify/extensions.local.yml`; `None` when the file is absent. Used only to build and verify one immutable install snapshot. |

### GeneratedExtensionsYml

Merge output written to `.specify/extensions.yml`.

| Field | Type | Notes |
|---|---|---|
| `installed` | `list[str]` | Passed through from local source (unchanged). |
| `settings` | `dict[str, Any]` | Passed through from local source (unchanged). |
| `required_extensions` | `tuple[MergedRequirement, ...]` | Deterministic sort by `(extension_id,)`. |
| `optional_extensions` | `tuple[MergedRequirement, ...]` | Deterministic sort by `(extension_id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Merged per-stage: molecule entries first (in declaration order), local entries after; identity-matching local entries replace molecule entries in their position. Every serialized entry carries `origin`. |

Serialisation: `to_yaml_bytes()` writes YAML with a top-of-file `# generated by haex install: do not edit` comment, sorted keys where deterministic, atom-declared order preserved for hook lists.

### MergedRequirement

Result of molecule-vs-local reduction for a single extension id.

| Field | Type | Notes |
|---|---|---|
| `extension_id` | `str` | The id. |
| `effective_constraint` | `VersionConstraint` | Canonical form after R4 reduction. |
| `is_required` | `bool` | True when either molecule or local marked it required. |
| `sources` | `tuple[ExtensionRequirementSource, ...]` | Molecule source first when present, then local source. |

### ExtensionRequirementSource

| Field | Type | Notes |
|---|---|---|
| `origin` | `Literal["molecule", "local"]` | Which side contributed. |
| `molecule_id` | `str \| None` | Populated when `origin == "molecule"`. |
| `molecule_revision` | `str \| None` | Populated when `origin == "molecule"`. |
| `declared_constraint` | `VersionConstraint` | Verbatim from source. |
| `kind` | `Literal["required", "optional"]` | Which list on that side. |

### InstalledExtensionMetadata

Loaded from `.specify/extensions/<id>/extension.yml`. `version` is authoritative; no `.registry` cross-check.

| Field | Type | Notes |
|---|---|---|
| `extension_id` | `str` | Matches the directory name. |
| `version` | `str` | From `extension.yml`'s `version` field. Parseable as SemVer. |
| `source_path` | `Path` | Absolute path of the loaded `extension.yml`. |

### WorkflowResolution

Return type of `resolve_active_workflow(repo_root)`.

| Field | Type | Notes |
|---|---|---|
| `source` | `Literal["molecule", "bundled"]` | Where the binding workflow comes from. |
| `workflow_path` | `Path` | Absolute path to the binding `workflow.yml`. |
| `molecule_id` | `str \| None` | Populated when `source == "molecule"`. |
| `diagnostics` | `tuple[str, ...]` | Non-fatal messages the caller may log. |

---

## Relationships

- A `WorkflowMoleculeManifest` is one adopted molecule's declaration; per FR-006 at most one such molecule may be adopted per project.
- Every adopted `WorkflowMoleculeManifest` produces zero or more of: (a) directory publication under `.specify/workflows/<molecule-id>/`; (b) directory publication under `.specify/extensions/workflow-molecules/<molecule-id>/`; (c) merged constitution fragment inside `## Workflow-Contributed Rules`; (d) contribution to `.specify/extensions.yml` merged with `LocalExtensionsSource`.
- `LocalExtensionsSource` is the operator-owned input; `GeneratedExtensionsYml` is the deterministic output. The runtime writes only the latter.
- `WorkflowFragment` + `LocalExtensionsSource` -> `merge_extensions` -> `GeneratedExtensionsYml` (with `MergedRequirement` per unique id).
- `resolve_active_workflow` reads `ConsumerManifest` -> returns `WorkflowResolution`.

---

## Cross-root publication and recovery contract

`publish_generation` remains the Spec 008 primitive for one haex-owned root.
Workflow installation uses a repository-wide coordinator around that primitive
because one install changes both `.haex-hive/**` and `.specify/**`. The
coordinator MUST hold the exclusive install lock and follow this protocol:

1. Materialise complete candidate views in same-filesystem siblings
   `.haex-hive.next/` and `.specify.next/`. The `.haex-hive.next/` view contains
   the candidate `install.lock`; the `.specify.next/`
   view contains only the generated and molecule-owned managed paths, plus a
   `.haex-hive-generation.json` record with `{ "generation_id": "...", "root": ".specify/" }`.
   The record's fields are schema-validated, while the effective participating
   roots are derived from the molecule `paths[]` records in `install.lock`. The consumer-owned
   `.specify/extensions.local.yml` is excluded from the staged view and is
   never generated, edited, renamed, or deleted.
2. Validate both views, including schemas, path ownership, generated output,
   and the cross-root generation ID, before either live root is changed. The
   candidate view contains no removed molecule-owned paths; unrelated consumer
   files are outside the managed path set and remain untouched. A generated
   `.specify/extensions.yml` is always rebuilt from the parsed local-source
   snapshot and molecule fragment.
   Immediately before the first swap, re-read the live local-source path and
   compare its presence and bytes with `LocalExtensionsSource.source_bytes`;
   if it differs, refuse or retry without publishing either root.
3. Commit the `.specify/` managed path set first without swapping the root:
   save the previous managed paths in `.specify.prev/`, write the candidate
   `.haex-hive-generation.json` record first, then atomically replace or delete
   managed files in deterministic order, excluding
   `.specify/extensions.local.yml` and all unrelated consumer files. Fsync each
   changed file and the `.specify/` directory. Commit `.haex-hive/` second
   through `publish_generation`, with `install.lock` carrying the candidate
   generation ID and molecule paths under both roots. Publishing that lock as
   part of the rename-swap is the sole repository-wide visibility event; until
   it is published, a candidate root paired with the previous lock is
   unavailable and must not be accepted by readers.
4. Pass the cross-root verification as `publish_generation`'s
   `post_write_verify` callback. The callback runs after the `.haex-hive/`
   swap but before that primitive removes `.haex-hive.prev/`; it verifies both
   live-root generation records and `.haex-hive/install.lock`'s
   `generation_id`. If verification fails, it
   restores all changed `.specify/` managed paths from `.specify.prev/` and
   raises so `publish_generation` restores `.haex-hive/` while its previous root
   is still available. The local source is not part of this rollback because it
   was never changed. On success, `publish_generation` may remove
   `.haex-hive.prev/`, after which the coordinator removes `.specify.prev/`;
   both parent directories are fsynced. Cleanup is not part of the visibility
   event and is retry-safe.

Recovery runs under the same lock before a retry reads inputs. It first reads
and validates each `.next/` sibling and its generation record. Before the live
`install.lock` participates in classification, recovery MUST apply the Spec
008 FR-005 schema/migration gate to it. An unsupported version, retired field,
or required migration makes the lock non-authoritative; recovery MUST refuse
without using its generation for classification or deleting evidence. Only
after that gate passes does recovery classify a sibling against the live
install lock, the matching
`.prev/` record, and the other root's sibling. A sibling is deleted only when
its well-formed generation is attributable as stale (for example, an
unpublished candidate older than the live generation). A missing, malformed, or
unattributable record causes recovery to refuse and preserve that sibling.
After classification, recovery compares the generation records in both live
roots and the install lock. If only the `.specify/` managed paths were changed,
or the lock and roots name different generations, it restores those paths from
`.specify.prev/`. If `.haex-hive/` was also swapped, `publish_generation`
restores it from `.haex-hive.prev/`; recovery fsyncs the parent directories. If
both roots and the lock agree, recovery only removes attributable stale
`.prev/` siblings. A failed
retry keeps the previous complete generation. Downgrade cleanup is therefore
atomic at the repository visibility boundary: removed molecule-owned workflow
directories and generated entries become absent together with the new
`.haex-hive/install.lock`,
while unrelated consumer files and `.specify/extensions.local.yml` survive
verbatim.

Readers enforce the same visibility boundary. A reader MUST acquire the
shared/read lock before loading `.haex-hive/install.lock` and retain it through
validation and consumption. It MUST first apply the Spec 008 FR-005
schema/migration gate. An unsupported version, retired field, or required
migration makes the lock non-authoritative and unavailable. Only after that
gate passes may a reader require its `generation_id` and every path in its
molecules to be present, and require the live
`.specify/.haex-hive-generation.json` record and every active adapter pointer
to name the same generation. The effective participating roots are the root
prefixes of those molecule paths; there is no separate root list to compare.
Any missing record or generation mismatch, including the interval after the
`.specify/` swap and before the `.haex-hive/` lock swap, is unavailable; the
reader rejects the view and retries after the install recovery path has run.

The integration suite MUST inject process termination after staging, after the
first `.specify/` managed-path replacement, after the `.haex-hive/` swap, after
post-write verification, and during stale-sibling cleanup. It MUST also run a
deterministic failure case where `post_write_verify` raises after the managed
path replacement; that case MUST assert restoration of the old generation in
both roots, no mixed managed paths, byte-identical
`.specify/extensions.local.yml`, and safe stale-sibling cleanup. The suite
MUST exercise a reader during the interval between the managed-path
replacements and the lock swap, and mutate `.specify/extensions.local.yml`
between parsing and staging. Each retry MUST converge to either the old
generation or the fully published candidate, never a mixed generation; tests
also assert that removed atom paths are absent, unrelated files are unchanged,
and the local source is byte-identical to the captured snapshot.

---

## State machine of an install with a workflow molecule

```text
START
  │
  ▼
[acquire_lock]                    (Spec 008: ConstitutionWriterLock)
  │
  ▼
[clean_stale_siblings]            (Spec 008: detect+retry cleanup)
  │
  ▼
[load_consumer_manifest]          (ConsumerManifest.from_json)
  │
  ▼
[resolve_molecules]               (workflow molecule -> WorkflowMoleculeManifest)
  │
  ▼
[refuse_multiple_workflow_molecules] (count resolved, validated
                                   atoms.workflow fields;
                                   refuse before fragments or publication)
  │
  ▼
[validate_workflow_paths]         (RepoRelativePath.validate + containment
                                   on every molecule source and destination path)
  │
  ▼
[load_workflow_fragment]          (WorkflowFragment; duplicate id/hook
                                   refusals fire here)
  │
  ▼
[load_local_source]               (LocalExtensionsSource + source_bytes;
                                   empty when absent)
  │
  ▼
[merge_extensions]                (GeneratedExtensionsYml + MergedRequirements
                                   with conflict refusals per FR-005)
  │
  ▼
[validate_required_extensions]    (per-required-id installation + version
                                   check via extension.yml)
  │
  ▼
[compose_constitution_candidate]  (multi-source merge including workflow molecule's
                                   fragment inside ## Workflow-Contributed Rules)
  │
  ▼
[review_gate --llm=file / --accept-merged]   (Principle VI, unchanged)
  │
  ▼
[compose_install_lock + extensions.yml + workflow files]
  │
  ▼
[publish_install_generation]      (repository-wide coordinator: stage both
                                   roots, replace managed `.specify/` paths,
                                   then call the Spec 008 `.haex-hive/`
                                   rename-swap; verify the shared generation
                                   ID from install.lock before cleanup. The consumer-owned
                                   `.specify/extensions.local.yml` remains
                                   outside the transaction.)
  │
  ▼
END
```

**Invariants**:

- No workflow-molecule-derived file is written before `[validate_workflow_paths]`, `[load_workflow_fragment]`, `[merge_extensions]`, and `[validate_required_extensions]` all pass.
- The live `.specify/extensions.local.yml` is NEVER written, renamed, or deleted by the runtime. It is read by `[load_local_source]` and remains outside the staged and published managed path set.
- After a successful install, every resolved adopted workflow molecule results in exactly one directory under `.specify/workflows/`; bundled `.specify/workflows/speckit/` is untouched by molecule adoption.
- A refused install, including invalid paths, broken YAML, missing required extensions, or multiple workflow molecules, creates no new molecule directory and preserves the previous published generation.

---

## Boundaries

- **Spec 007** (molecule-manifest schema, ConsumerManifest, VersionConstraint): reused. `WorkflowMoleculeManifest` specialises the base molecule.
- **Spec 008** (install transaction, rename-swap, multi-source constitution merge): reused. workflow molecule deltas participate in the repository-wide `publish_install_generation` coordinator, which calls the single-root `publish_generation` primitive for `.haex-hive/`.
- **Constitution v1.4.0** (§ Development Workflow -> Declared speckit workflow adherence): `resolve_active_workflow` is what that clause resolves to at read-time.
- **Spec 010** (compiler adapters): out of scope.
- **specifyr extension-install** (external): out of scope. workflow molecules declare which extensions they need; installation is delegated.
