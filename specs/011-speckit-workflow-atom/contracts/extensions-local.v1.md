# Local Extensions Source Contract v1 (consumer-owned)

**Spec**: [Spec 011 simplified](../spec.md)
**Referenced by**: FR-005 (reviewer-hardened in PR #54)

Consumer-owned local extensions declarations file. Authored by the operator, edited by the operator, committed by the operator. NEVER generated, deleted, or modified by `haex install`.

## File location

`.specify/extensions.local.yml` (repository root, alongside `.specify/` sibling directories).

## Ownership boundary

- **Consumer-owned**: the operator is the sole authority. Their edits survive every install cycle byte-for-byte.
- **Read-only for the runtime**: `haex install` loads the file (or treats an absent file as empty declarations) but never writes to it.
- **Not published**: the file itself is not the install output; the generated `.specify/extensions.yml` is.

## Shape

```yaml
installed:
  - v-model-extension-pack
  - speckit-companion

settings:
  llm_endpoint: "http://localhost:8080"
  retry_count: 3

required_extensions:
  - id: acme-internal-linter
    version_constraint: ">=2.0.0"
    homepage: https://acme.corp/tooling/speckit-linter

optional_extensions:
  - id: speckit-companion
    version_constraint: ">=0.21.0"

hooks:
  before_specify:
    - extension: acme-internal
      command: acme.internal.spec-guard
      script: hooks/local/spec-guard.sh
      description: "ACME internal spec-guard check"
      enabled: true
      optional: false
```

## Field rules

Same as [extensions-fragment.v1.md](./extensions-fragment.v1.md) with two additions:

- `installed[]`: list of extension ids the operator declares as installed locally. Informational; the runtime does not verify. Passed through to `.specify/extensions.yml` unchanged.
- `settings`: free-form key/value bag. Passed through to `.specify/extensions.yml` unchanged.

All refusal rules from the fragment contract also apply to the local source: duplicate hook identity within one stage refuses, unparseable constraints refuse, duplicate id within `required_extensions[]` or `optional_extensions[]` refuses.

## Missing file semantics

An absent `.specify/extensions.local.yml` denotes empty local declarations:
- `installed: []`
- `settings: {}`
- `required_extensions: []`
- `optional_extensions: []`
- `hooks: {}`

The install proceeds normally; the generated `.specify/extensions.yml` is built from the atom fragment alone.

## Migration from `.specify/extensions.yml` (pre-Spec-011)

Projects that previously edited `.specify/extensions.yml` directly (before Spec 011 introduced the ownership split) must move their local declarations into `.specify/extensions.local.yml`. Recommended procedure:

1. Copy `.specify/extensions.yml` -> `.specify/extensions.local.yml`.
2. Adopt the workflow atom (or leave `.haex-hive.json` unchanged if no workflow atom is adopted).
3. Run `haex install`.
4. The regenerated `.specify/extensions.yml` will contain the operator's declarations merged with the workflow atom's fragment (if any).

No automatic migration is performed by the runtime; the operator drives the move.
