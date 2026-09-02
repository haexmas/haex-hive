# Extensions Fragment Contract v1 (atom-contributed)

**Spec**: [Spec 011 simplified](../spec.md)
**Referenced by**: FR-005, [atom-manifest.v2.speckit-workflow.md](./atom-manifest.v2.speckit-workflow.md)

The YAML shape a workflow atom's `contributes.speckit_extensions` file MUST conform to. The fragment is one input to the extension-merge pipeline; the other input is the consumer-owned [extensions-local.v1.md](./extensions-local.v1.md) file.

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
    - extension: strict-tdd
      command: speckit.strict-tdd.pre-spec
      script: hooks/pre-implement.sh
      description: "Enforce TDD prerequisites before specification"
      enabled: true
      optional: true
      prompt: "Verify TDD prerequisites?"

  after_tasks:
    - extension: strict-tdd
      command: speckit.strict-tdd.post-tasks
      script: hooks/post-tasks.sh
      description: "Verify task decomposition follows TDD phasing"
      enabled: true
      optional: true
```

## Field rules

- `required_extensions[]` and `optional_extensions[]`: list of extension declarations. `id` matches `^[A-Za-z0-9][A-Za-z0-9._-]*$`. `version_constraint` parses per Spec 007's `VersionConstraint` grammar. `homepage` optional.
- `hooks.<stage>[]`: at most one entry per `(stage, extension, command, script)` identity within a single fragment (duplicate refuses with `key=workflow-hook-mapping-invalid`). `stage` is one of the enumerated stage names. `script` MUST resolve to a file under the atom's `speckit_hooks` directory.
- Same `id` declared twice within `required_extensions[]` or twice within `optional_extensions[]` refuses with `key=workflow-atom-extension-id-collision`.
- Unparseable `version_constraint` in any declaration (required or optional) refuses with `key=invalid-constraint`.
- Conflicting non-constraint metadata (e.g. different `homepage` for the same id across required vs optional lists within the fragment) refuses with `key=conflicting-extension-metadata`.

## Interaction with `extensions.local.yml`

Under one-active-per-repo, the fragment is merged with the consumer-owned [extensions-local.v1.md](./extensions-local.v1.md) to produce [extensions-generated.v1.md](./extensions-generated.v1.md). Merge rules:

- **Requirements per id**: canonical constraint reduction (research.md § R4). Compatible atom-vs-local pair -> merged effective constraint. Incompatible required -> refuse (`key=conflicting-constraint`). Incompatible optional -> drop with warning (`key=optional-workflow-extension-conflict`). Required wins over optional for effective kind.
- **Hooks per stage**: atom entries first (in declaration order), local entries after. Identity match `(stage, extension, command, script)` triggers local-replace-per-position semantics per research.md § R8.

## Load-time refusal errors

| Fault | Diagnostic key | Category |
|---|---|---|
| YAML parse fails | `workflow-fragment-parse-failed` | `INPUT_REFUSE` |
| Unknown stage name | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Duplicate `(stage, extension, command, script)` in fragment | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
| Unparseable `version_constraint` | `invalid-constraint` | `INPUT_REFUSE` |
| Same id declared twice in one list | `workflow-atom-extension-id-collision` | `INPUT_REFUSE` |
| Hook `script` path escapes atom root | Principle II | `INPUT_REFUSE` |
| Hook `script` file not present after publish-time copy | `workflow-hook-mapping-invalid` | `INPUT_REFUSE` |
