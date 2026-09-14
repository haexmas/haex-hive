# Contract: Molecule Spec Kit Declaration v1

**Owner**: Spec 024
**Input**: `.spaex` publisher molecule `manifest.json`
**Purpose**: Declare official Spec Kit integrations without shipping Spec Kit skill files.

## Shape

```json
{
  "spaex_version": "4",
  "id": "com.example.speckit",
  "version": "1.0.0",
  "priority": 50,
  "atoms": {
    "constitution": ["constitution.md"]
  },
  "speckit": {
    "version_constraint": "0.12.11",
    "integrations": {
      "claude": {
        "integration_options": ""
      },
      "codex": {
        "integration_options": "--skills"
      }
    }
  }
}
```

## Validation

- `speckit` is optional.
- When present, `version_constraint` MUST match spaex's exact/lower-bound
  version grammar.
- `integrations` MUST be a non-empty object.
- Integration keys MUST be non-empty lower-case identifiers containing only
  letters, digits, and hyphens.
- Each integration value MUST be an object with at most the
  `integration_options` string property.
- `integration_options` MUST NOT contain `--global`, `--project`, shell
  operators, NUL bytes, or newline characters. spaex passes it as one argument
  value and never invokes a shell.
- A molecule MUST NOT declare a `speckit` object and a Spec Kit `install_hook`
  action for the same integration behavior.
- The declaration MUST NOT contain a skill path, absolute path, mutable source
  reference, secret, or executable script path.

## Runtime semantics

- The declaration is resolved from the already pinned molecule revision.
- The effective `specify` CLI version MUST satisfy `version_constraint` before
  any integration install is attempted.
- The supported integration set is read from `specify integration list`; a
  selected key that is not supported is refused before any install operation.
- The official install operation is invoked as:

  ```text
  specify integration install <key>
  ```

  When non-empty, the declaration's option string is passed as one
  `--integration-options=<value>` argument. `cwd` is the consumer repository
  root. The shell is never used.
- Global installation is not supported by this contract.
- The official CLI's stdout/stderr remain visible to the operator. spaex adds a
  machine-readable per-integration outcome after the operation.
