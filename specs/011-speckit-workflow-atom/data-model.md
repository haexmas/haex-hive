# Data Model: Speckit Workflow Atom (simplified)

**Feature**: Spec 011 (simplified, PR #54 merged)
**Date**: 2026-09-02
**Purpose**: Dataclass-level shapes and relationships for the workflow subpackage. Every persisted format has a matching contract under [contracts/](./contracts/); this file records the in-memory shapes.

---

## Entities

### WorkflowAtomManifest

Runtime representation of a `speckit-workflow` atom kind. Specialises `AtomManifest` from Spec 007. Constructor validates every path via `RepoRelativePath.validate` + containment against the atom root; at publication time the resolver re-validates against the consumer repo root.

| Field | Type | Notes |
|---|---|---|
| `atom_id` | `str` | Reverse-DNS id per Spec 007. |
| `atom_revision` | `str` | Full 40-char SHA (Principle IV). |
| `workflow_path` | `str` | Repo-relative path to `workflow.yml` inside the atom directory. Presence marks the atom as workflow-kind. |
| `constitution_path` | `str \| None` | Optional constitution fragment path. |
| `extensions_path` | `str \| None` | Optional extensions.yml fragment path. |
| `hooks_dir` | `str \| None` | Optional hooks directory. |

**Construction rules**: invalid path fields raise `WorkflowAtomManifestPathError` (Principle II diagnostic). An atom carrying `extensions_path` or `hooks_dir` without `workflow_path` refuses at consumer-manifest load time via `ConsumerManifest.from_json`.

### WorkflowFragment

Parsed representation of the atom's contributed `extensions.yml`.

| Field | Type | Notes |
|---|---|---|
| `atom_id` | `str` | Source atom. |
| `atom_revision` | `str` | Full 40-char SHA. |
| `required_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `optional_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Keyed by stage; entries retain in-fragment declaration order. |

Duplicate `(id,)` within `required_extensions` or `optional_extensions` raises `WorkflowAtomExtensionIdCollisionError`. The same id across the two lists is normalized as one required requirement: the generated output contains one `required_extensions[]` entry, and compatible required/optional declarations both appear in that entry's `sources[]` with their original kinds. An incompatible optional declaration is dropped with a warning while the required declaration remains. Duplicate hook identity within a single stage raises `WorkflowHookMappingInvalidError`.

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
| `script_path` | `str` | Repo-relative under `.specify/extensions/workflow-atoms/<atom-id>/` for atom-contributed hooks, or below the consumer-owned local hook base for local hooks. |
| `enabled` | `bool` | Defaults true. |
| `optional` | `bool` | Defaults true for atom-contributed hooks. |
| `description` | `str` | Operator-facing description. |
| `prompt` | `str \| None` | Optional confirmation prompt. |

Identity is `(stage, extension, command, script_path)` per R8.

### LocalExtensionsSource

Parsed `.specify/extensions.local.yml`. When the file is absent, an empty instance is returned. NEVER mutated by the runtime.

| Field | Type | Notes |
|---|---|---|
| `installed` | `list[str]` | Locally-installed extension ids (informational). |
| `settings` | `dict[str, Any]` | Local-only settings, passed through to the generated file. |
| `required_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `optional_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Local hook entries. Duplicate identity within one stage refuses at load. |

### GeneratedExtensionsYml

Merge output written to `.specify/extensions.yml`.

| Field | Type | Notes |
|---|---|---|
| `installed` | `list[str]` | Passed through from local source (unchanged). |
| `settings` | `dict[str, Any]` | Passed through from local source (unchanged). |
| `required_extensions` | `tuple[MergedRequirement, ...]` | Deterministic sort by `(extension_id,)`. |
| `optional_extensions` | `tuple[MergedRequirement, ...]` | Deterministic sort by `(extension_id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Merged per-stage: atom entries first (in declaration order), local entries after; identity-matching local entries replace atom entries in their position. |

Serialisation: `to_yaml_bytes()` writes YAML with a top-of-file `# generated by haex install: do not edit` comment, sorted keys where deterministic, atom-declared order preserved for hook lists.

### MergedRequirement

Result of atom-vs-local reduction for a single extension id.

| Field | Type | Notes |
|---|---|---|
| `extension_id` | `str` | The id. |
| `effective_constraint` | `VersionConstraint` | Canonical form after R4 reduction. |
| `is_required` | `bool` | True when either atom or local marked it required. |
| `sources` | `tuple[ExtensionRequirementSource, ...]` | Atom source first when present, then local source. |

### ExtensionRequirementSource

| Field | Type | Notes |
|---|---|---|
| `origin` | `Literal["atom", "local"]` | Which side contributed. |
| `atom_id` | `str \| None` | Populated when `origin == "atom"`. |
| `atom_revision` | `str \| None` | Populated when `origin == "atom"`. |
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
| `source` | `Literal["atom", "bundled"]` | Where the binding workflow comes from. |
| `workflow_path` | `Path` | Absolute path to the binding `workflow.yml`. |
| `atom_id` | `str \| None` | Populated when `source == "atom"`. |
| `diagnostics` | `tuple[str, ...]` | Non-fatal messages the caller may log. |

---

## Relationships

- A `WorkflowAtomManifest` is one adopted atom's declaration; per FR-006 at most one such atom may be adopted per project.
- Every adopted `WorkflowAtomManifest` produces zero or more of: (a) directory publication under `.specify/workflows/<atom-id>/`; (b) directory publication under `.specify/extensions/workflow-atoms/<atom-id>/`; (c) merged constitution fragment inside `## Workflow-Contributed Rules`; (d) contribution to `.specify/extensions.yml` merged with `LocalExtensionsSource`.
- `LocalExtensionsSource` is the operator-owned input; `GeneratedExtensionsYml` is the deterministic output. The runtime writes only the latter.
- `WorkflowFragment` + `LocalExtensionsSource` -> `merge_extensions` -> `GeneratedExtensionsYml` (with `MergedRequirement` per unique id).
- `resolve_active_workflow` reads `ConsumerManifest` -> returns `WorkflowResolution`.

---

## State machine of an install with a workflow atom

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
[resolve_atoms]                   (workflow atom -> WorkflowAtomManifest)
  │
  ▼
[refuse_multiple_workflow_atoms]  (count resolved, validated
                                   contributes.speckit_workflow fields;
                                   refuse before fragments or publication)
  │
  ▼
[validate_workflow_paths]         (RepoRelativePath.validate + containment
                                   on every contributes.speckit_* path)
  │
  ▼
[load_workflow_fragment]          (WorkflowFragment; duplicate id/hook
                                   refusals fire here)
  │
  ▼
[load_local_source]               (LocalExtensionsSource; empty when absent)
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
[compose_constitution_candidate]  (multi-source merge including workflow atom's
                                   fragment inside ## Workflow-Contributed Rules)
  │
  ▼
[review_gate --llm=file / --accept-merged]   (Principle VI, unchanged)
  │
  ▼
[compose_install_lock + visibility.json + extensions.yml + workflow files]
  │
  ▼
[publish_generation]              (Spec 008 rename-swap for `.haex-hive/`
                                   only. The cross-root publication and
                                   recovery protocol for `.specify/**` is
                                   outside this primitive. The consumer-
                                   owned `.specify/extensions.local.yml` is
                                   NOT part of the publication set.)
  │
  ▼
END
```

**Invariants**:

- No workflow-atom-derived file is written before `[validate_workflow_paths]`, `[load_workflow_fragment]`, `[merge_extensions]`, and `[validate_required_extensions]` all pass.
- `.specify/extensions.local.yml` is NEVER read, written, or deleted outside `[load_local_source]`, which is read-only.
- After a successful install, every resolved adopted `speckit-workflow` atom results in exactly one directory under `.specify/workflows/`; bundled `.specify/workflows/speckit/` is untouched by atom adoption.
- A refused install, including invalid paths, broken YAML, missing required extensions, or multiple workflow atoms, creates no new atom directory and preserves the previous published generation.

---

## Boundaries

- **Spec 007** (atom-manifest schema, ConsumerManifest, VersionConstraint): reused. `WorkflowAtomManifest` specialises the base atom.
- **Spec 008** (install transaction, rename-swap, multi-source constitution merge): reused. Workflow atom deltas participate in the same `publish_generation` call.
- **Constitution v1.4.0** (§ Development Workflow -> Declared speckit workflow adherence): `resolve_active_workflow` is what that clause resolves to at read-time.
- **Spec 010** (compiler adapters): out of scope.
- **specifyr extension-install** (external): out of scope. Workflow atoms declare which extensions they need; installation is delegated.
