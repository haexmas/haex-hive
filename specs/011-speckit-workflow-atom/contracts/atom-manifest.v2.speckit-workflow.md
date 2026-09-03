# Molecule Manifest v3 Contract: Speckit Workflow

**Spec**: [Spec 011 simplified](../spec.md)
**Base**: [Spec 007 molecule-manifest.v3 contract](../../007-unified-manifest-v2/spec.md)
**Referenced by**: FR-001

This contract defines the workflow-specific categories in the Spec 007 v3 molecule manifest. It replaces the retired v2 `contributes.*` shape; workflow identity is derived from a non-empty `atoms.workflow` list.

## New fields

### `atoms.workflow`

- **Type**: array of strings (repo-relative paths).
- **Required**: no; a non-empty list marks the molecule as a workflow molecule.
- **Content shape**: YAML file matching the bundled `.specify/workflows/speckit/workflow.yml` reference shape (`schema_version`, `workflow.id/name/version`, `steps[]`).
- **Validation**: every path passes `RepoRelativePath.validate`; content parses as YAML; content passes `validate_no_plaintext_secrets` and `validate_no_concealment_instructions`. The workflow file is source-relative to the molecule and its `steps[].script`/`hooks[].script` values are destination-relative to the published molecule-owned hooks directory; each is validated against the corresponding root. A workflow that declares script paths without `atoms.hooks` refuses before publication.

### `atoms.extensions`

- **Type**: array of strings (repo-relative paths).
- **Required**: no; REQUIRES a non-empty `atoms.workflow` list on the same molecule. Presence without `atoms.workflow` refuses at consumer-manifest load time.
- **Content shape**: YAML matching [extensions-fragment.v1.md](./extensions-fragment.v1.md).

### `atoms.hooks`

- **Type**: array of strings (repo-relative paths).
- **Required**: no; REQUIRES a non-empty `atoms.workflow` list on the same molecule.
- **Content shape**: a directory whose files are copied into `.specify/extensions/workflow-molecules/<molecule-id>/` preserving relative structure. All files below must be regular files reachable without symlink escape.

## Multi-workflow-molecule refusal (FR-006)

When two or more resolved publisher molecule manifests carry a non-empty `atoms.workflow` list, the workflow pipeline refuses with `key=multiple-workflow-molecules-refused` (exit `INPUT_REFUSE=2`) after those manifests have been loaded and validated, but before fragments or publication are processed. Stderr names every offending molecule's `id` and `source`. Zero files are written under `.specify/workflows/`, `.specify/extensions/workflow-molecules/`, `.specify/extensions.yml`, or `.haex-hive/`.

## Publication targets

| Contribution | Destination | Semantics |
|---|---|---|
| `atoms.workflow[]` files | `.specify/workflows/<molecule-id>/workflow.yml` | The workflow entry is copied byte-for-byte. |
| `atoms.extensions[]` files | `.specify/extensions.yml` | Merged per [extensions-fragment.v1.md](./extensions-fragment.v1.md) and [extensions-generated.v1.md](./extensions-generated.v1.md); never published as a standalone file. |
| `atoms.hooks[]` files | `.specify/extensions/workflow-molecules/<molecule-id>/**` (reserved namespace) | Directory-preserving copy for the molecule's hook files. |
| `atoms.constitution[]` files | `.haex-hive/constitution.md`, in `## Workflow-Contributed Rules` | Merged under a `### From molecule <molecule-id> (revision <short-sha>)` byline. |

## Delete-orphans

Removing the molecule from `.haex-hive.json` and re-running `haex install` deletes `.specify/workflows/<molecule-id>/`, `.specify/extensions/workflow-molecules/<molecule-id>/`, the molecule's entries from the generated `.specify/extensions.yml`, and the molecule's constitution fragment atomically as part of the R1 rename-swap generation. The consumer-owned `.specify/extensions.local.yml` survives verbatim.

## Concrete example

```json
{
  "haex_hive_version": "3",
  "id": "com.example.publisher.strict-tdd-workflow",
  "version": "1.2.0",
  "priority": 5,
  "atoms": {
    "workflow": ["workflow.yml"],
    "constitution": ["constitution.md"],
    "extensions": ["extensions.yml"],
    "hooks": ["hooks/pre-implement.sh", "hooks/post-tasks.sh"]
  }
}
```

For the full directory shape a publisher produces, see [../research.md § R7](../research.md).
