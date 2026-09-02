# Atom Manifest v2 Contract Delta: Speckit Workflow (simplified)

**Spec**: [Spec 011 simplified](../spec.md)
**Base**: [Spec 007 atom-manifest.v2.schema.json](../../007-unified-manifest-v2/contracts/atom-manifest.v2.schema.json)
**Referenced by**: FR-001

This delta document defines the three new optional `contributes.*` fields that Spec 011 adds to atom-manifest v2. It does NOT redefine the base shape; that stays in Spec 007's schema file.

## New fields

### `contributes.speckit_workflow`

- **Type**: string (repo-relative path).
- **Required**: no; presence marks the atom as a `speckit-workflow` kind.
- **Content shape**: YAML file matching the bundled `.specify/workflows/speckit/workflow.yml` reference shape (`schema_version`, `workflow.id/name/version`, `steps[]`).
- **Validation**: path passes `RepoRelativePath.validate`; content parses as YAML; content passes `validate_no_plaintext_secrets` and `validate_no_concealment_instructions`; every `steps[].script` and `hooks[].script` inside the yml passes `RepoRelativePath.validate` + containment against the atom root.

### `contributes.speckit_extensions`

- **Type**: string (repo-relative path).
- **Required**: no; REQUIRES `contributes.speckit_workflow` on the same atom. Presence without `speckit_workflow` refuses at consumer-manifest load time.
- **Content shape**: YAML matching [extensions-fragment.v1.md](./extensions-fragment.v1.md).

### `contributes.speckit_hooks`

- **Type**: string (repo-relative directory path).
- **Required**: no; REQUIRES `contributes.speckit_workflow` on the same atom.
- **Content shape**: a directory whose files are copied into `.specify/extensions/workflow-atoms/<atom-id>/` preserving relative structure. All files below must be regular files reachable without symlink escape.

## Multi-workflow-atom refusal (FR-006)

When two or more atoms in `.haex-hive.json`'s resolved adoption set carry `contributes.speckit_workflow`, `ConsumerManifest.from_json` refuses with `key=multiple-workflow-atoms-refused` (exit `INPUT_REFUSE=2`). Stderr names every offending atom's `id` and `source`. Zero files are written under `.specify/workflows/`, `.specify/extensions/workflow-atoms/`, `.specify/extensions.yml`, or `.haex-hive/`.

## Publication targets

| Contribution | Destination | Semantics |
|---|---|---|
| `speckit_workflow` file | `.specify/workflows/<atom-id>/workflow.yml` | Byte-for-byte copy. |
| `speckit_extensions` file | Merged into `.specify/extensions.yml` per [extensions-fragment.v1.md](./extensions-fragment.v1.md) and [extensions-generated.v1.md](./extensions-generated.v1.md). Never published as a standalone file. |
| `speckit_hooks/*` tree | `.specify/extensions/workflow-atoms/<atom-id>/**` (reserved namespace). Directory-preserving copy. |
| `constitution` file | Merged into `.haex-hive/constitution.md` `## Workflow-Contributed Rules` section under a `### From atom <atom-id> (revision <short-sha>)` byline. |

## Delete-orphans

Removing the atom from `.haex-hive.json` and re-running `haex install` deletes `.specify/workflows/<atom-id>/`, `.specify/extensions/workflow-atoms/<atom-id>/`, the atom's entries from the generated `.specify/extensions.yml`, and the atom's constitution fragment atomically as part of the R1 rename-swap generation. The consumer-owned `.specify/extensions.local.yml` survives verbatim.

## Concrete example

```json
{
  "haex_hive_version": "2",
  "id": "com.example.publisher.strict-tdd-workflow",
  "version": "1.2.0",
  "priority": 5,
  "contributes": {
    "speckit_workflow": "workflow.yml",
    "constitution": "constitution.md",
    "speckit_extensions": "extensions.yml",
    "speckit_hooks": "hooks/"
  }
}
```

For the full directory shape a publisher produces, see [../research.md § R7](../research.md).
