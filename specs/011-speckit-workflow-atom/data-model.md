# Data Model: Speckit Workflow Atom

**Feature**: Spec 011: Speckit Workflow Atom
**Date**: 2026-09-02
**Purpose**: Dataclass-level shapes and relationships for the workflow-atom pipeline. Every persisted format has a matching JSON Schema under [contracts/](./contracts/); this file records the in-memory shapes.

---

## Entities

### WorkflowAtomManifest

Runtime representation of a `speckit-workflow` atom kind. Extends the base `AtomManifest` from Spec 007. Constructor validates every path via `RepoRelativePath.validate` plus containment against the atom root; the resolver then re-validates against the consumer repo root before publication.

| Field | Type | Notes |
|---|---|---|
| `atom_id` | `str` | Reverse-DNS id per Spec 007. |
| `version` | `str` | Atom version. |
| `priority` | `int` | Merge priority (Spec 007). |
| `workflow_path` | `str` | Repo-relative path to `workflow.yml` inside the atom directory. Required (presence marks the atom as workflow kind). |
| `constitution_path` | `str \| None` | Repo-relative path to the constitution fragment. When present, participates in the multi-source merge. |
| `extensions_path` | `str \| None` | Repo-relative path to the extensions.yml fragment. |
| `hooks_dir` | `str \| None` | Repo-relative directory of hook scripts. When present, every file below is copied to `.specify/extensions/workflow-atoms/<atom-id>/`. |

**Construction rules**: on `__post_init__` every path field is validated. Invalid paths raise `WorkflowAtomManifestPathError` (subclass of `HaexError`, diagnostic key per §R6 of research.md).

### WorkflowRegistry

Runtime representation of `.specify/workflows/workflow-registry.json`. See [contracts/workflow-registry.v1.schema.json](./contracts/workflow-registry.v1.schema.json).

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `Literal["1.0"]` | Strict; readers refuse other versions. |
| `active_workflow` | `str \| None` | Names an entry in `workflows`, or null/absent to fall back to bundled. |
| `workflows` | `dict[str, WorkflowEntry]` | Keyed by workflow id. |

Serialisation: `to_json_bytes()` sorts keys lexicographically, writes 2-space indent + LF newlines, no trailing whitespace. Deserialisation: `from_json(raw: bytes) -> WorkflowRegistry` validates via `workflow-registry.v1.schema.json`.

### WorkflowEntry

Per-workflow entry inside `WorkflowRegistry.workflows`.

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Human-readable name. |
| `version` | `str` | Semantic version. |
| `source` | `Literal["bundled", "atom"]` | Where the workflow came from. |
| `atom_id` | `str \| None` | Present when `source == "atom"`; matches the map key. |
| `atom_revision` | `str \| None` | Full 40-char SHA per Principle IV, when `source == "atom"`. |
| `installed_at` | `str` | UTC ISO 8601 timestamp of first install. |
| `updated_at` | `str` | UTC ISO 8601 timestamp of last update. |
| `unknown_extras` | `dict[str, Any]` | Reserved for forward-compat with speckit-community metadata. |

### WorkflowFragment

Parsed representation of a workflow atom's contributed `extensions.yml`.

| Field | Type | Notes |
|---|---|---|
| `atom_id` | `str` | Source atom. |
| `atom_revision` | `str` | Full 40-char SHA of the atom's pinned revision. |
| `required_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `optional_extensions` | `tuple[ExtensionRequirement, ...]` | Sorted by `(id,)`. |
| `hooks` | `dict[str, tuple[HookEntry, ...]]` | Keyed by stage name (`before_specify`, `after_implement`, etc.); atom-hook entries only, with local hooks merged separately in the transaction path. |

### ExtensionRequirement

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Speckit-community extension id. |
| `version_constraint` | `VersionConstraint` | Parsed per Spec 007's grammar (`X.Y.Z` or `>=X.Y.Z`); unsupported forms refuse with `key=invalid-constraint`. |
| `homepage` | `str \| None` | Optional URL for diagnostics. |

Construction: `version_constraint` parse-error at load time raises `InvalidConstraintError` (`key=invalid-constraint`, exit `INPUT_REFUSE`).

### HookEntry

Represents one hook mapping contributed by a workflow atom.

| Field | Type | Notes |
|---|---|---|
| `stage` | `str` | Enum: `before_constitution`/`after_constitution`/`before_specify`/`after_specify`/`before_plan`/`after_plan`/`before_tasks`/`after_tasks`/`before_implement`/`after_implement`/`before_checklist`/`after_checklist`/`before_analyze`/`after_analyze`/`before_taskstoissues`/`after_taskstoissues` per existing `.specify/extensions.yml` shape. |
| `command` | `str` | Dotted command name (e.g. `speckit.strict-tdd.pre-hook`); the runner maps dot to hyphen. |
| `script_path` | `str` | Repo-relative path under `.specify/extensions/workflow-atoms/<atom-id>/`. Validated before publication against both the atom source root and the staged consumer destination; must resolve to a file copied from the atom's `hooks_dir`. |
| `enabled` | `bool` | Default `true`; an exact local override is authoritative and may disable the atom hook with `false`. |
| `optional` | `bool` | Default `true` for atom-contributed hooks. |
| `description` | `str` | For operator display. |
| `prompt` | `str \| None` | Optional user-facing prompt when the hook is invoked. |

### ResolvedExtensionRequirement

Result of merging every adopted workflow atom's fragments for a single extension id.

| Field | Type | Notes |
|---|---|---|
| `extension_id` | `str` | Speckit-community extension id. |
| `effective_constraint` | `VersionConstraint` | Canonical form after per-R2 merge. |
| `is_required` | `bool` | True when at least one contributing atom marked it required. |
| `sources` | `tuple[ExtensionRequirementSource, ...]` | Every contributing atom, in canonical `(atom_id,)` order. |

### ExtensionRequirementSource

| Field | Type | Notes |
|---|---|---|
| `atom_id` | `str` | Contributing atom. |
| `atom_revision` | `str` | Full 40-char SHA. |
| `declared_constraint` | `VersionConstraint` | Verbatim constraint from the atom's fragment. |
| `kind` | `Literal["required", "optional"]` | Which list this atom put it in. |

### WorkflowResolution

Return type of `resolve_active_workflow(repo_root)`.

| Field | Type | Notes |
|---|---|---|
| `active_id` | `str` | Resolved workflow id. Always non-empty (falls back to `"speckit"` when nothing else applies). |
| `workflow_path` | `Path` | Absolute filesystem path to the resolved `workflow.yml`. |
| `source` | `Literal["bundled", "atom", "fallback"]` | `fallback` when registry file missing / invalid / `active_workflow` unresolvable. |
| `diagnostics` | `tuple[str, ...]` | Non-fatal diagnostic messages for the caller to log. |

---

## Relationships

- A `WorkflowAtomManifest` is one atom's declaration; a project's `.haex-hive.json` may adopt zero or more such atoms.
- Every adopted `WorkflowAtomManifest` produces (a) one directory publication under `.specify/workflows/<atom-id>/`, (b) zero or one directory under `.specify/extensions/workflow-atoms/<atom-id>/`, (c) zero or one merged constitution fragment, (d) zero or one contribution to `.specify/extensions.yml`, (e) one `WorkflowEntry` inside `WorkflowRegistry.workflows` keyed by `atom_id`.
- `WorkflowRegistry.active_workflow` names either `"speckit"` (bundled), any adopted atom id, or `null`. `resolve_active_workflow()` translates to `WorkflowResolution`.
- Every `WorkflowFragment` contributes zero or more `ExtensionRequirement` entries; requirements from multiple fragments merge into `ResolvedExtensionRequirement` per-id via R2's algorithm.
- Every `WorkflowFragment.hooks[stage]` entry contributes one `HookEntry` to the transaction's atom-first merge with locally-declared hooks in `.specify/extensions.yml`.

### Adoption and registry identity

Before workflow resolution, flatten all adopted atom includes and reject a duplicate workflow atom id with Spec 007's existing `AtomIdCollisionError` (`key=atom-id-collision`). This applies even when the duplicate comes from two different source entries; no source or revision silently wins. The synthetic bundled `speckit` entry is not an adopted atom and remains unaffected.

Registry parsing performs the JSON Schema validation first, then a post-schema identity check: every entry under `workflows[<key>]` with `source == "atom"` MUST have `atom_id == <key>`. A mismatch is refused before publication or reader-side path construction. `WorkflowEntry.unknown_extras` contains all unrecognised per-entry fields; `to_json_bytes()` writes those fields back unchanged, merges known fields deterministically, and never lets an extra overwrite a known field.

---

## State machine of an install with workflow atoms

```text
START
  │
  ▼
[acquire_lock]  (Spec 008: ConstitutionWriterLock)
  │
  ▼
[clean_stale_siblings]  (Spec 008: detect+retry cleanup)
  │
  ▼
[load_consumer_manifest]  → ConsumerManifest.from_json
  │
  ▼
[resolve_atoms]  → resolves every atom; workflow atoms produce WorkflowAtomManifest
  │
  ▼
[validate_workflow_paths]  → RepoRelativePath.validate + containment on every workflow atom's contributes.*
  │
  ▼
[parse_workflow_fragments]  → ExtensionRequirement + HookEntry for every adopted workflow atom
  │
  ▼
[merge_extension_requirements]  → ResolvedExtensionRequirement per unique id, per R2 algorithm
  │
  ▼
[validate_required_extensions]  → refuses on missing/incompatible/conflicting metadata
  │
  ▼
[compose_constitution_candidate]  → multi-source merge including workflow-atom constitution fragments in `## Workflow-Contributed Rules` section
  │
  ▼
[review_gate --llm=file / --accept-merged]  (Principle VI: unchanged)
  │
  ▼
[compose_install_lock + visibility.json + workflow-registry.json]
  │
  ▼
[publish_generation]  (Spec 008: atomic rename-swap for each live root and only the files passed to that call; no cross-tree atomicity guarantee)
  │
  ▼
END
```

**Invariants**:

- No workflow-atom-derived file (workflow.yml, hooks, fragments) is written before `[validate_workflow_paths]` and `[validate_required_extensions]` pass.
- The `workflow-registry.json`'s `active_workflow` field is preserved across install runs unless (a) an operator edits it manually, or (b) the atom it names is removed (auto-reset to `null` with `key=workflow-atom-reset-to-default` diagnostic).
- Every atom that appears in `.haex-hive.json`'s `atoms[]` and is a workflow atom appears exactly once in `WorkflowRegistry.workflows` after duplicate-id validation. The bundled `speckit` entry is unaffected by atom adoption.

---

## Boundaries

- **Spec 007** (atom-manifest schema, `ConsumerManifest`, `VersionConstraint`): reused with the schema, model, and parser extended for `contributes.speckit_workflow`, `contributes.speckit_extensions`, and `contributes.speckit_hooks`. Parser coverage MUST verify these fields while preserving existing constitution, spec, rules, hooks, and skills handling. `WorkflowAtomManifest` is a specialisation of the base atom.
- **Spec 008** (install transaction, rename-swap, multi-source constitution merge): reused for each participating live root. `publish_generation` is atomic only for the live directory and staged files passed to that call; a cross-tree commit protocol is out of scope. Retry-after-interruption convergence remains required.
- **Constitution v1.4.0** (§Development Workflow → Declared speckit workflow adherence): the `resolve_active_workflow` helper is what that clause resolves to at read-time.
- **Spec 010** (compiler adapters): out of scope. When Spec 010 lands, its adapter atoms may co-exist with workflow atoms under `.specify/workflows/` and `.specify/extensions/workflow-atoms/`.
- **specifyr extension-install** (external): out of scope. Workflow atoms declare which extensions they need; installation is delegated.
