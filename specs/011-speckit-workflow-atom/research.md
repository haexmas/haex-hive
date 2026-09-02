# Phase 0 Research: Speckit Workflow Atom

**Feature**: Spec 011: Speckit Workflow Atom
**Date**: 2026-09-02
**Purpose**: Resolve every load-bearing implementation decision the plan reserved as "chosen in research". Each section records the decision, rationale, and alternatives considered.

---

## R1. Workflow-registry schema shape

**Decision**: `.specify/workflows/workflow-registry.json` is a strictly-versioned JSON document validated against `workflow-registry.v1.schema.json`. Top-level unknown fields are refused (`additionalProperties: false`); per-workflow entries under `workflows.<id>` accept unknown fields for forward-compat with speckit-community additions.

**Concrete shape**:

```json
{
  "schema_version": "1.0",
  "active_workflow": "com.example.publisher.strict-tdd-workflow",
  "workflows": {
    "speckit": {
      "name": "Full SDD Cycle",
      "version": "1.0.0",
      "source": "bundled",
      "installed_at": "2026-08-26T19:16:48.810653+00:00",
      "updated_at": "2026-08-26T19:16:48.810661+00:00"
    },
    "com.example.publisher.strict-tdd-workflow": {
      "name": "Strict TDD Cycle",
      "version": "1.2.0",
      "source": "atom",
      "atom_id": "com.example.publisher.strict-tdd-workflow",
      "atom_revision": "aabbccdd...",
      "installed_at": "2026-09-02T14:30:00Z",
      "updated_at": "2026-09-02T14:30:00Z"
    }
  }
}
```

**Rationale**: strict top-level catches operator typos on `active_workflow`, `schema_version`, `workflows` before they turn into silent fallbacks. Per-workflow openness lets community extensions add fields (extra metadata, capability declarations) without a Spec 011 revision.

Schema validation is followed by a semantic identity check: for every atom entry, `workflows[<key>].atom_id` MUST equal `<key>`. JSON Schema cannot compare an object property name with a nested value, so a mismatch is rejected by the registry parser before resolution or publication. Unknown per-entry fields are captured in `WorkflowEntry.unknown_extras` and round-tripped unchanged by `to_json_bytes()`.

**Alternatives considered**:
- **Fully strict schema everywhere**: rejected, blocks community extensions from carrying metadata Spec 011 does not yet know about.
- **Fully loose top level**: rejected, defeats the "catch typos on `active_workflow`" objective.
- **Move the registry into `.haex-hive/install.lock`**: rejected. install.lock is the atom-record contract; the registry is workflow-state that survives install.lock rewrites (an install regenerates install.lock every time, but the registry's `active_workflow` field is operator state).

**Residual risk**: two atoms adopting different `schema_version`s of the workflow-registry contract could conflict. Mitigation: `schema_version` is a top-level field, not per-workflow; the reader picks one version to accept and refuses others. Follow-up: if a v2 lands, add a migration adapter in `workflow/registry.py`.

## R2. Constraint-merge algorithm

**Decision**: Version constraints on the same extension id merge into a canonical form independent of atom declaration order. Spec 007 supports only exact and lower-bound constraints; unsupported upper, compatible, wildcard, comma, and caret syntax is rejected rather than represented lossy. The algorithm:

1. Parse every atom-declared constraint into a `VersionConstraint` (Spec 007 grammar; supports `X.Y.Z` exact and `>=X.Y.Z` lower-bound only).
2. Group by kind: exact constraints and lower-bound constraints.
3. Reduce:
   - **Exact vs Exact**: identical → keep. Different → refuse with `key=conflicting-constraint`.
   - **Exact vs Lower-bound (`>=X`)**: exact must be `>= X`, else refuse.
   - **Multiple lower-bounds**: keep the highest.
4. Emit a single canonical `VersionConstraint` for the id.
5. Record every contributing atom in `ResolvedExtensionRequirement.sources` for diagnostic tracing.

**Rationale**: order-independence is critical because atom-adoption order in `.haex-hive.json` should not silently change which constraint wins. Refuse-empty-range prevents the resolver from returning an unsatisfiable constraint and then the install refusing at a later stage with a less-clear diagnostic.

**Alternatives considered**:
- **First-declared wins**: rejected, order-dependent.
- **Merge everything into a set of constraints without reducing**: rejected, forces the extension-validator to interpret multiple constraints per id, doubling its complexity.
- **Reject every exact/lower intersection (e.g. exact `1.2.3` + `>=1.0.0`)**: rejected, because the canonical exact result preserves the full intersection without adding syntax beyond Spec 007.

**Residual risk**: richer range syntax may be needed in a future Spec 007 revision. Until that revision defines a lossless composite representation, rejecting unsupported forms with `key=invalid-constraint` prevents a resolver from claiming a constraint that accepts versions outside the declared intersection.

## R3. Extension-directory naming discipline

**Decision**: atom-contributed hook scripts publish under `.specify/extensions/workflow-atoms/<atom-id>/` (reserved sub-namespace), NOT under `.specify/extensions/<atom-id>/` (flat with speckit-community extensions). Ratified by the merged spec's US1 acceptance scenario 1.

**Rationale**: prevents an atom from shadowing a legitimately-installed speckit-community extension by claiming its id. The reserved `workflow-atoms/` prefix is off-limits to community-extension installers (specifyr / `speckit extensions install`); collisions on that path are workflow-atom-vs-workflow-atom only, and those are already diagnosed by `key=atom-id-collision` (Spec 007's existing check).

**Alternatives considered**:
- **Flat namespace with a collision-refuse rule**: rejected, adds a new refusal path and still leaves the risk of a community extension being installed AFTER a workflow-atom has claimed its id.
- **Publish hooks directly into workflow's own directory (`.specify/workflows/<atom-id>/hooks/`)**: rejected, decouples hook-script residency from the extension-discovery convention that speckit-community readers use. Extensions live under `.specify/extensions/`, period.

## R4. Constitution-fragment merge byline format

**Decision**: workflow-atom-contributed constitution fragments merge into a shared `## Workflow-Contributed Rules` section in `.haex-hive/constitution.md`. Each fragment is prefixed by a subsection heading:

```markdown
## Workflow-Contributed Rules

### From atom `com.example.publisher.strict-tdd-workflow` (revision `aabbccdd`)

<fragment body verbatim>

### From atom `com.example.other-publisher.bugfix-workflow` (revision `eeff0011`)

<fragment body verbatim>
```

Multiple fragments append in bytewise UTF-8 atom-id order, independent of `.haex-hive.json` source/include order. The section header appears exactly once even when only one atom contributes; when no atom contributes, the section is omitted entirely.

**Rationale**: byline attribution makes provenance auditable (Principle V, VIII); the shared `## Workflow-Contributed Rules` header keeps workflow-imposed rules grouped so readers can find them without scanning the whole file. Bytewise atom-id ordering makes output independent of source/include declaration order.

**Alternatives considered**:
- **Append each fragment as its own top-level `## <atom-id>` section**: rejected, floods the constitution's top-level structure with a section per workflow atom.
- **Merge fragments without provenance**: rejected, defeats Principle V's contract discipline.
- **Prepend rather than append**: rejected, changes what readers see first based on adoption order; append matches the operator's mental model (later adoption = later in the file).

## R5. Diagnostic-key exit-code assignment

**Decision**: reuse existing exit-code categories from `haex_hive.util.exit_codes`. Assignment table:

| Diagnostic key | Category | Exit code | Slot type |
|---|---|---|---|
| `required-workflow-extension-missing` | Validation | reuse `VALIDATION_REFUSE` (4) | refusal |
| `required-workflow-extension-incompatible` | Validation | reuse `VALIDATION_REFUSE` (4) | refusal |
| `invalid-constraint` | Input | reuse `INPUT_REFUSE` (2) | refusal |
| `conflicting-constraint` | Validation | reuse `VALIDATION_REFUSE` (4) | refusal |
| `conflicting-extension-metadata` | Validation | reuse `VALIDATION_REFUSE` (4) | refusal |
| `workflow-hook-mapping-invalid` | Input | reuse `INPUT_REFUSE` (2) | refusal |
| `workflow-atom-extension-id-collision` | Input | reuse `INPUT_REFUSE` (2) | refusal |
| `optional-workflow-extension-conflict` | (warning) | 0 | stderr-only |
| `workflow-atom-reset-to-default` | (warning) | 0 | stderr-only |

**Rationale**: haex-hive's exit-code table (see `contracts/haex-install.cli.md`) already provides a small, semantically-clear set. Adding new numeric slots for each diagnostic key doubles the operator's memorisation burden without adding information: the key string does the discrimination, the exit code does the category. Reuse is standard practice already in the existing errors.py (e.g. multiple diagnostic keys map to `INPUT_REFUSE`).

**Alternatives considered**:
- **New numeric slot per key**: rejected, exit-code inflation for no operator benefit.
- **Everything under one generic "workflow-atom-refuse" code**: rejected, loses the input-vs-validation distinction that lets automation route errors.

**Residual risk**: none identified. The `haex install` shell wrapper (if any operators wrap it) can route on exit code first, key second, matching every other refusal path in the tool.

## R6. Workflow.yml payload validation (safety guards)

**Decision**: workflow.yml's own content is validated for:

1. **Path safety on `steps[].script` and `hooks[].script` fields**: every path passes `RepoRelativePath.validate`, resolves below the atom's declared `speckit_hooks` source root, and names a regular non-symlink/reparse file included by the `speckit_hooks/*` publication. At staging time, the corresponding destination is resolved below `.specify/extensions/workflow-atoms/<atom-id>/` under the consumer root. Absolute, traversal, and symlink/reparse-point escapes are refused. Source and destination containment are checked independently; a valid source does not authorise an escaping destination.
2. **No plaintext secrets**: `validate_no_plaintext_secrets` runs over the entire workflow.yml body and the contents of every validated script referenced by `steps[].script` or `hooks[].script`, before any publication.
3. **No concealment instructions**: `validate_no_concealment_instructions` runs over every string field in workflow.yml and every validated referenced script, using the same policy as constitution fragments.
4. **Schema validation**: workflow.yml MUST parse as valid YAML and match the same shape the existing bundled `.specify/workflows/speckit/workflow.yml` conforms to (schema_version, workflow.id/name/version, steps[]).

**Rationale**: Principle I and VIII apply to every payload haex-hive publishes into a committed root. A workflow-atom that contributes a workflow.yml with an absolute path in `steps[].script` would violate Principle II just as clearly as an absolute path in `contributes.speckit_hooks`.

**Alternatives considered**:
- **Only validate contributes.* paths, not workflow.yml internal paths**: rejected, contradicts Principle II's spirit.
- **Introduce a separate workflow.v1.schema.json**: deferred to Spec 011 successor. The bundled workflow.yml shape is de-facto documented by its own presence; formalising the schema is orthogonal to this spec's scope.

## R7. Delete-orphans semantics for workflow atoms

**Decision**: when a workflow atom is removed from `.haex-hive.json`, its `.specify/workflows/<atom-id>/` and `.specify/extensions/workflow-atoms/<atom-id>/` directories are removed by the corresponding per-root R1 rename-swap publications (Spec 008 US4 delete-orphans semantics). `publish_generation` guarantees atomic replacement only for its live directory and the files passed to that call; it does not guarantee a cross-tree commit between `.haex-hive/` and `.specify/`. The constitution fragment ceases to appear in the assembled `.haex-hive/constitution.md` because the atom no longer contributes to the multi-source merge. If `active_workflow` named the removed atom, it resets to `null` during reconciliation and stderr emits `key=workflow-atom-reset-to-default`. A retry after interruption converges the participating roots.

**Rationale**: consistency with Spec 008's rename-swap for each live root. No new per-file delete-logic; each call receives the reduced set of files for its own root. Cross-tree atomicity is not inferred until a commit protocol exists and is tested.

**Alternatives considered**:
- **Retain the directory but mark the atom as "inactive"**: rejected, contradicts Spec 008 US4's whole-generation replacement contract.
- **Require operator to manually `rm -rf` the workflow-atom directories**: rejected, defeats the "adopt/revert cheap" operator ergonomics that motivates workflow atoms in the first place.

## R8. Reader-side resolution algorithm

**Decision**: `resolve_active_workflow(repo_root: Path) -> WorkflowResolution` returns a typed object rather than a bare path. The algorithm:

1. Load `.specify/workflows/workflow-registry.json`. If absent: return `WorkflowResolution(active_id="speckit", workflow_path=<bundled path>, source="fallback", diagnostics=["registry file missing"])`.
2. Parse and schema-validate against `workflow-registry.v1.schema.json`. On failure: return `fallback` with a diagnostic.
3. Read `active_workflow` field. If `None` or absent: return `WorkflowResolution(active_id="speckit", workflow_path=<bundled path>, source="fallback", diagnostics=[])`.
4. Validate `active_workflow` against the path-safe identifier grammar `^[A-Za-z0-9][A-Za-z0-9._-]*$` before using it as a map key or path component. Atom ids MUST additionally satisfy the reverse-DNS `AtomId` grammar; the bundled id is the fixed path-safe literal `speckit`. Invalid or traversal-like ids return `fallback` with the existing reset diagnostic.
5. Look up `workflows[active_id]`. If missing, or if an atom entry's `atom_id` does not exactly equal its map key, return `fallback` with a diagnostic naming the unresolvable identity.
6. Compute the candidate path only after validation: `.specify/workflows/<id>/workflow.yml` when `source == "atom"`, or `.specify/workflows/speckit/workflow.yml` when `source == "bundled"`. Resolve it and require it to remain contained below `repo_root/.specify/workflows`; reject symlink/reparse-point escapes and return `fallback` on failure. Otherwise return `WorkflowResolution(active_id=<id>, workflow_path=<candidate>, source=<entry.source>, diagnostics=[])`.

**Rationale**: downstream skills (`/speckit-implement`, `/speckit-plan`, etc.) that ask "which workflow is binding?" should never see a raw exception on registry-file corruption; they get a typed answer with diagnostics they can log or surface. The `fallback` variant is a first-class outcome, not an error.

**Alternatives considered**:
- **Return `Path` and raise on any error**: rejected, forces every caller to wrap the call in try/except. The bundled fallback is the safe default; making it an implicit no-error outcome removes error-handling ceremony from every reader.
- **Return `Optional[Path]` with `None` on any error**: rejected, loses the diagnostic thread.

**Residual risk**: if the bundled `.specify/workflows/speckit/workflow.yml` is itself missing (unusual but possible on a broken checkout), the fallback path returns a non-existent file. Callers that read the path get a `FileNotFoundError` and can surface it. Adding a `path_exists` check inside the resolver was rejected as over-engineering; the resolver's contract is registry-shape, not filesystem-existence.

---

## Summary of Phase 0 outputs

- Registry schema: strictly-versioned, top-level closed, per-workflow open (R1)
- Constraint merge: order-independent canonical reduction with early-refuse on empty range (R2)
- Extension-directory naming: reserved `.specify/extensions/workflow-atoms/<atom-id>/` prefix (R3)
- Constitution byline: shared `## Workflow-Contributed Rules` with per-atom subsection heading (R4)
- Diagnostic exit codes: reuse existing categories (R5)
- Workflow.yml safety guards: path containment, no-secrets, no-concealment (R6)
- Delete-orphans: whole-generation rename-swap; `active_workflow` auto-reset (R7)
- Reader resolution: typed `WorkflowResolution` with `fallback` as first-class outcome (R8)

Phase 1 (data-model + contracts + quickstart) consumes these decisions.
