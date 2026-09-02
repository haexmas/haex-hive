# Atom Manifest v2 Contract Delta: Speckit Workflow

**Spec**: [Spec 011: Speckit Workflow Atom](../spec.md)
**Base**: [Spec 007: atom-manifest.v2.schema.json](../../007-unified-manifest-v2/contracts/atom-manifest.v2.schema.json)
**Referenced by**: FR-001

This delta document defines three new optional `contributes.*` fields that Spec 011 adds to the atom-manifest v2 schema. It does NOT redefine the base shape; that stays in Spec 007's schema file. When Spec 011 lands, `atom-manifest.v2.schema.json` gains these three fields under `properties.contributes.properties`.

## New fields

### `contributes.speckit_workflow`

- **Type**: string (repo-relative path)
- **Required**: no; presence marks the atom as a `speckit-workflow` kind
- **Content shape**: a valid YAML file matching the shape of the bundled `.specify/workflows/speckit/workflow.yml` (schema_version, workflow.id/name/version, steps[])
- **Validation**:
  - Path passes `RepoRelativePath.validate`
  - Path resolves to a regular file below the atom directory
  - Content parses as YAML
  - Content passes `validate_no_plaintext_secrets`
  - Any string field passes `validate_no_concealment_instructions`
  - Any `steps[].script` or `hooks[].script` reference inside the yml body passes `RepoRelativePath.validate` and names a file below the declared `speckit_hooks` source directory; every such file is included in the directory publication below

### `contributes.speckit_extensions`

- **Type**: string (repo-relative path)
- **Required**: no
- **Content shape**: YAML matching [extensions-fragment.v1.md](./extensions-fragment.v1.md)
- **Validation**:
  - Path passes `RepoRelativePath.validate`
  - Path resolves to a regular file below the atom directory
  - Content parses as YAML and matches the fragment contract
  - Every `required_extensions[i].version_constraint` and `optional_extensions[i].version_constraint` parses as a `VersionConstraint`
  - Every `hooks.<stage>[i].script` reference passes `RepoRelativePath.validate` and resolves to a file under the atom's `speckit_hooks` directory

### Cross-field validation

`contributes.speckit_extensions` and `contributes.speckit_hooks` are workflow-specific payloads. If either field is present, `contributes.speckit_workflow` MUST also be present and resolve to a valid workflow file. An atom MUST NOT publish workflow-specific payloads without declaring the workflow they belong to.

The `steps[].script` and `hooks[].script` references in that workflow are source references, not independent publication inputs. They MUST resolve below the declared `speckit_hooks` directory and every referenced regular file MUST be copied by the `speckit_hooks/*` publication row. A reference outside that directory, or a script that is not included by that row, is refused before staging.

### `contributes.speckit_hooks`

- **Type**: string (repo-relative directory path)
- **Required**: no
- **Content shape**: a directory containing hook scripts
- **Validation**:
  - Path passes `RepoRelativePath.validate`
  - Path resolves to a directory below the atom root
  - No file inside is a symlink or reparse point escaping the atom root
  - Every file below is a regular file

## Publication targets

When an atom carries these fields, `haex install` publishes the payloads as follows:

| Contribution | Destination | Semantics |
|---|---|---|
| `speckit_workflow` file | `.specify/workflows/<atom-id>/workflow.yml` | Byte-for-byte copy |
| `speckit_extensions` file | Merged into `.specify/extensions.yml` per [extensions-fragment.v1.md](./extensions-fragment.v1.md) | Not published as a separate file |
| `speckit_hooks/*` (directory tree) | `.specify/extensions/workflow-atoms/<atom-id>/**` | Directory-preserving copy |
| `constitution` file (if present) | Multi-source merged into `.haex-hive/constitution.md` `## Workflow-Contributed Rules` section | Existing multi-source flow with new byline-per-atom convention |

## Delete-orphans behaviour

When an operator removes the atom from `.haex-hive.json` and re-runs `haex install`, the generated live trees delete `.specify/workflows/<atom-id>/` and `.specify/extensions/workflow-atoms/<atom-id>/` through their respective R1 rename-swap publications. Each live-tree replacement is atomic; no cross-tree atomicity is claimed. A retry after interruption converges all trees to the same adopted-atom set. The constitution fragment disappears from the merged output because the atom no longer contributes. If `workflow-registry.json.active_workflow` named the removed atom, it resets to `null` in the same reconciliation with `key=workflow-atom-reset-to-default` on stderr.

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

Given the atom directory:

```text
com.example.publisher.strict-tdd-workflow/
├── manifest.json          (the file shown above)
├── workflow.yml           (speckit workflow declaration)
├── constitution.md        (rules the workflow imposes)
├── extensions.yml         (required extensions + hook wiring)
└── hooks/
    ├── pre-implement.sh
    └── post-tasks.sh
```

`haex install` produces:

```text
.specify/workflows/com.example.publisher.strict-tdd-workflow/
└── workflow.yml           (byte-for-byte from the atom)

.specify/extensions/workflow-atoms/com.example.publisher.strict-tdd-workflow/
├── pre-implement.sh
└── post-tasks.sh

.specify/extensions.yml     (merged; atom-contributed required_extensions +
                             hooks entries appended, atom-first + local-last)

.haex-hive/constitution.md  (merged; atom's constitution.md content lands
                             inside `## Workflow-Contributed Rules` under a
                             `### From atom <id> (revision <sha>)` byline)
```
