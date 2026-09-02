# Extensions Fragment Contract v1

**Spec**: [Spec 011: Speckit Workflow Atom](../spec.md)
**Referenced by**: FR-005, [atom-manifest.v2.speckit-workflow.md](./atom-manifest.v2.speckit-workflow.md)

The content shape a workflow atom's `contributes.speckit_extensions` YAML fragment MUST conform to, plus the deterministic merge algorithm that combines fragments from multiple adopted atoms with the consumer's local `.specify/extensions.yml`.

## Fragment shape

```yaml
required_extensions:
  - id: v-model-extension-pack
    version_constraint: ">=0.7.2"
    homepage: https://speckit-community.github.io/extensions/v-model-extension-pack

optional_extensions:
  - id: speckit-companion
    version_constraint: ">=0.21.0"

hooks:
  before_specify:
    - command: speckit.strict-tdd.pre-spec
      extension: strict-tdd
      script: hooks/pre-implement.sh
      description: "Enforce TDD prerequisites before specification"
      enabled: true
      optional: true
      prompt: "Verify TDD prerequisites?"

  after_tasks:
    - command: speckit.strict-tdd.post-tasks
      extension: strict-tdd
      script: hooks/post-tasks.sh
      description: "Verify task decomposition follows TDD phasing"
      enabled: true
      optional: true
```

### Field rules

- `required_extensions[]`: list of `ExtensionRequirement`. `id` matches `^[A-Za-z0-9][A-Za-z0-9._-]*$`. `version_constraint` parses per `haex_hive.model.version_constraint.VersionConstraint` grammar: exact `X.Y.Z` or lower-bound `>=X.Y.Z`; all other forms are refused with `key=invalid-constraint`. `homepage` optional.
- `optional_extensions[]`: same shape; missing extensions surface as warnings (`key=optional-workflow-extension-conflict` on conflict), not refusals.
- `hooks.<stage>[]`: at most one entry per `(stage, extension, command, script)` identity inside a single fragment. `stage` is one of the canonical stage names, whether or not the consumer's local `.specify/extensions.yml` currently defines that stage. `script` MUST resolve to a file under the atom's `speckit_hooks` directory (validated before staging).

## Constraint-merge algorithm (canonical form)

When two or more adopted workflow atoms declare the same `extension_id`, the resolver reduces to a single canonical `VersionConstraint`:

1. Parse every declared `version_constraint` per atom.
2. Group by kind: **exact** (`X.Y.Z`) or **lower** (`>=X.Y.Z`). Other constraint syntax is refused at parse time with `key=invalid-constraint`; no lossy intersection is serialized.
3. Reduce pairwise, order-independent:
   - **Exact vs Exact**: same → keep; different → refuse (`key=conflicting-constraint`).
   - **Exact vs Lower**: exact must satisfy `>= lower`, else refuse.
   - **Lower vs Lower**: keep the higher (more restrictive).
4. Emit a single canonical `VersionConstraint`.
5. Record every contributing atom in the resulting `ResolvedExtensionRequirement.sources` for diagnostic tracing.

**Order-independence**: the algorithm produces the same output regardless of `.haex-hive.json` `atoms[]` order. Two atoms A + B and B + A yield the same merged constraint.

**Required-vs-optional interaction**: if the same extension id appears as required in one atom's fragment and optional in another's, required wins; the optional entry contributes to the merge only when its constraint is compatible with the required one. When incompatible, the optional entry is dropped and stderr emits `key=optional-workflow-extension-conflict` naming the ignored optional constraint. The install still succeeds.

## Hook-merge algorithm

Hook entries merge into the consumer's `.specify/extensions.yml.hooks.<stage>` lists using the "atom hooks first, local hooks last" precedence (design-doc Q2, spec §Assumptions):

1. Process the union of stages present in the consumer file and all atom fragments. Atom entries are sorted by bytewise UTF-8 `(atom_id, extension, command, script)` identity and precede local entries, including for stages that exist only in an atom fragment.
2. Duplicate entries with the same `(stage, extension, command, script)` identity within a single fragment refuse with `key=workflow-hook-mapping-invalid`.
3. After collecting all atom fragments, a duplicate atom identity across fragments also refuses with `key=workflow-hook-mapping-invalid`. Duplicate local identities refuse with the same key, so a local override can target at most one atom entry.
4. A local entry with the same exact identity replaces the atom entry in place. The local `enabled` and `optional` flags are authoritative; therefore a local `enabled: false` disables the atom hook rather than running both records. Local entries without an atom match remain after all atom entries in their canonical local order.
5. Before any publication or rename-swap, validate both sides of every mapping: the source path must resolve below the atom's `speckit_hooks` root to one regular, non-symlink/reparse file, and the planned staged destination `.specify/extensions/workflow-atoms/<atom-id>/<relative-script>` must resolve below that atom-owned namespace. Any escaping, duplicate, missing, or non-regular mapping refuses with `key=workflow-hook-mapping-invalid`; validation MUST NOT depend on a destination that exists only after publication.

## Non-constraint metadata

`homepage`, `description`, `prompt` fields are string-typed and NOT part of the constraint algebra. When two atoms declare different `homepage` values for the same extension id, refuse with `key=conflicting-extension-metadata`. `description` and `prompt` may differ; the atom-declared string of the first contributing atom wins (deterministic by `(atom_id,)` sort order after adoption resolution).

## Load-time validation errors

| Fault | Diagnostic key | Category |
|---|---|---|
| YAML parse fails | `workflow-fragment-parse-failed` | `INPUT_REFUSE` |
| Unknown stage name | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Duplicate `(stage, extension, command, script)` within one atom fragment | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Duplicate `(stage, extension, command, script)` across atom fragments | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Duplicate `(stage, extension, command, script)` among local entries | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| `version_constraint` unparseable | `invalid-constraint` | `INPUT_REFUSE` |
| Same extension id required twice in one fragment | `workflow-atom-extension-id-collision` | `INPUT_REFUSE` |
| Hook `script` source or planned destination escapes its owned root | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Hook `script` file is missing, non-regular, or not present in the staged copy | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
