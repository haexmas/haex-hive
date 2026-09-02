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
      script: hooks/pre-implement.sh
      description: "Enforce TDD prerequisites before specification"
      enabled: true
      optional: true
      prompt: "Verify TDD prerequisites?"

  after_tasks:
    - command: speckit.strict-tdd.post-tasks
      script: hooks/post-tasks.sh
      description: "Verify task decomposition follows TDD phasing"
      enabled: true
      optional: true
```

### Field rules

- `required_extensions[]`: list of `ExtensionRequirement`. `id` matches `^[A-Za-z0-9][A-Za-z0-9._-]*$`. `version_constraint` parses per `haex_hive.model.version_constraint.VersionConstraint` grammar. `homepage` optional.
- `optional_extensions[]`: same shape; missing extensions surface as warnings (`key=optional-workflow-extension-conflict` on conflict), not refusals.
- `hooks.<stage>[]`: at most one entry per `(stage, command)` pair inside a single fragment. `stage` is one of the enumerated stage names from `.specify/extensions.yml`'s existing shape. `script` MUST resolve to a file under the atom's `speckit_hooks` directory (validated when the fragment is loaded).

## Constraint-merge algorithm (canonical form)

When two or more adopted workflow atoms declare the same `extension_id`, the resolver reduces to a single canonical `VersionConstraint`:

1. Parse every declared `version_constraint` per atom.
2. Group by kind: **exact** (`X.Y.Z`), **lower** (`>=X.Y.Z`), **upper** (`<=X.Y.Z`), **compatible** (`~=X.Y.Z`).
3. Reduce pairwise, order-independent:
   - **Exact vs Exact**: same → keep; different → refuse (`key=conflicting-constraint`).
   - **Exact vs Lower**: exact must satisfy `>= lower`, else refuse.
   - **Exact vs Upper**: exact must satisfy `<= upper`, else refuse.
   - **Exact vs Compatible**: exact must be compatible with the base version, else refuse.
   - **Lower vs Lower**: keep the higher (more restrictive).
   - **Upper vs Upper**: keep the lower (more restrictive).
   - **Lower vs Upper**: if `lower > upper`, refuse (empty range).
   - **Compatible vs Compatible**: keep the higher when compatible; refuse when disjoint.
4. Emit a single canonical `VersionConstraint`.
5. Record every contributing atom in the resulting `ResolvedExtensionRequirement.sources` for diagnostic tracing.

**Order-independence**: the algorithm produces the same output regardless of `.haex-hive.json` `atoms[]` order. Two atoms A + B and B + A yield the same merged constraint.

**Required-vs-optional interaction**: if the same extension id appears as required in one atom's fragment and optional in another's, required wins; the optional entry contributes to the merge only when its constraint is compatible with the required one. When incompatible, the optional entry is dropped and stderr emits `key=optional-workflow-extension-conflict` naming the ignored optional constraint. The install still succeeds.

## Hook-merge algorithm

Hook entries merge into the consumer's `.specify/extensions.yml.hooks.<stage>` lists using the "atom hooks first, local hooks last" precedence (design-doc Q2, spec §Assumptions):

1. For each stage the consumer's `.specify/extensions.yml` defines, atom-contributed entries prepend to the existing list in the order they appear in `.haex-hive.json.atoms[]` `includes` traversal.
2. Duplicate entries (same `(stage, command)`) within a single fragment refuse with `key=workflow-hook-mapping-invalid`.
3. Duplicate `(stage, command)` between an atom and the local extensions.yml: the atom's entry runs first, then the local override. Both retain their `enabled` and `optional` flags.
4. Hook `script` paths validated at merge time: must resolve to a file under `.specify/extensions/workflow-atoms/<atom-id>/` after publication. Any hook whose script would land outside the atom's owned namespace refuses with `key=workflow-hook-mapping-invalid`.

## Non-constraint metadata

`homepage`, `description`, `prompt` fields are string-typed and NOT part of the constraint algebra. When two atoms declare different `homepage` values for the same extension id, refuse with `key=conflicting-extension-metadata`. `description` and `prompt` may differ; the atom-declared string of the first contributing atom wins (deterministic by `(atom_id,)` sort order after adoption resolution).

## Load-time validation errors

| Fault | Diagnostic key | Category |
|---|---|---|
| YAML parse fails | `workflow-fragment-parse-failed` | `INPUT_REFUSE` |
| Unknown stage name | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Duplicate `(stage, command)` within a fragment | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| `version_constraint` unparseable | `invalid-constraint` | `INPUT_REFUSE` |
| Same extension id required twice in one fragment | `workflow-atom-extension-id-collision` | `INPUT_REFUSE` |
| Hook `script` path escapes atom root | Principle II diagnostic | `INPUT_REFUSE` |
| Hook `script` file not present after copy | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
