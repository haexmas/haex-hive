# Schema Patch: `haex-hive.schema.json` (adds `external-harness` role)

**Phase**: 1 (planning)
**Spec references**: FR-001 through FR-008, FR-020, FR-033
**Data model**: [data-model.md](../data-model.md) §Layer A
**Research**: [research.md](../research.md) §8

Additive extension to the existing
`.specify/schemas/haex-hive.schema.json`. Preserves all Spec 004 entry
shapes (`role: "constitution"` and permission-only variants), adds the
`role: "external-harness"` variant, and enforces `additionalProperties: false`
per-variant to prevent field bleeds.

## Schema patch (JSON-Schema Draft 2020-12)

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://haex-hive.example.com/schemas/haex-hive.schema.json",
  "title": "haex-hive project config",
  "type": "object",
  "additionalProperties": false,
  "required": ["haex_hive_version", "identity", "harness_sources"],
  "properties": {
    "haex_hive_version": { "const": "1" },
    "identity":          { "type": "string", "minLength": 1 },
    "harness_sources":   {
      "type": "array",
      "items": { "$ref": "#/$defs/HarnessSourceEntry" }
    },
    "groups":            { "type": "array" },
    "active_feature":    { "type": ["string", "null"] }
  },
  "$defs": {
    "HarnessSourceEntry": {
      "oneOf": [
        { "$ref": "#/$defs/ConstitutionEntry" },
        { "$ref": "#/$defs/PermissionOnlyEntry" },
        { "$ref": "#/$defs/ExternalHarnessEntry" }
      ]
    },

    "ConstitutionEntry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["role", "repository", "revision", "path"],
      "properties": {
        "role":       { "const": "constitution" },
        "repository": { "type": "string", "minLength": 1 },
        "revision":   { "$ref": "#/$defs/Sha40" },
        "path":       { "$ref": "#/$defs/RepoRelativePath" }
      }
    },

    "PermissionOnlyEntry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["repository"],
      "not": { "required": ["role"] },
      "properties": {
        "repository": {
          "type": "string",
          "minLength": 1,
          "not": { "const": "self" }
        },
        "revision":   { "$ref": "#/$defs/Sha40" },
        "paths": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/RepoRelativePath" }
        }
      }
    },

    "ExternalHarnessEntry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["role", "repository", "revision"],
      "properties": {
        "role":       { "const": "external-harness" },
        "repository": {
          "type": "string",
          "minLength": 1,
          "not": { "const": "self" }
        },
        "revision":   { "$ref": "#/$defs/Sha40" },
        "name":       { "$ref": "#/$defs/StorageName" },
        "auto_include": { "enum": ["speckit-defaults"] },
        "additional_include": {
          "type": "array",
          "items": { "$ref": "#/$defs/RepoRelativePath" }
        },
        "items": {
          "type": "array",
          "items": { "$ref": "#/$defs/ItemDeclaration" }
        }
      },
      "anyOf": [
        { "required": ["auto_include"] },
        {
          "properties": {
            "additional_include": { "minItems": 1 }
          },
          "required": ["additional_include"]
        },
        {
          "properties": {
            "items": { "minItems": 1 }
          },
          "required": ["items"]
        }
      ]
    },

    "ItemDeclaration": {
      "type": "object",
      "additionalProperties": false,
      "required": ["role", "path", "as"],
      "properties": {
        "role": {
          "type": "string",
          "minLength": 1,
          "description": "Recognised values: constitution, workflow, template, skill, doc, spec, other. Unknown values pass schema (extensibility) and are treated as 'other' at runtime."
        },
        "path": { "$ref": "#/$defs/RepoRelativePath" },
        "as":   { "$ref": "#/$defs/AliasSlug" }
      }
    },

    "Sha40": {
      "type": "string",
      "pattern": "^[0-9a-f]{40}$"
    },
    "RepoRelativePath": {
      "type": "string",
      "minLength": 1,
      "not": { "pattern": "^/" },
      "description": "POSIX path relative to producer repo root. No leading /, no .. traversal (enforced by CLI validator, not by JSON Schema regex; JSON Schema catches leading slash only)."
    },
    "StorageName": {
      "type": "string",
      "pattern": "^[A-Za-z0-9._-]+$",
      "description": "Single platform-safe path component. Additional CLI-side filters reject reserved Windows device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9, case-insensitive) and dot / dot-dot special names."
    },
    "AliasSlug": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*$",
      "description": "Kebab-case ASCII slug per FR-006. Cannot start with a hyphen. No path:, no :, no /, no whitespace, no Unicode."
    }
  }
}
```

## CLI-side additional validation (beyond JSON Schema)

JSON Schema catches the syntactic layer. The `haex-init` CLI enforces
these additional constraints:

- **`repository` HTTPS-userinfo rejection** (FR-007): parse the URL
  via `urllib.parse.urlparse`; if `parsed.scheme` starts with
  `http` and `parsed.username` or `parsed.password` is present →
  refuse.
- **`StorageName` reserved-word filter** (FR-008): after regex
  match, refuse `.`, `..`, and any name whose upper-case form
  matches one of `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`,
  `LPT1`–`LPT9`.
- **`RepoRelativePath` traversal ban**: refuse any path containing
  `..` as a component.
- **`AliasSlug` reserved-prefix check** (FR-006): the regex already
  excludes `:` — so `path:` cannot form. Encoded for documentation
  clarity, no additional code.
- **Global collision checks** (FR-020):
  - Two `external-harness` entries with same `name` but different
    `repository` → refuse
  - Two `external-harness` entries producing the same resolved key
    → refuse
  - An alias inside an entry that would collide with an
    include-expansion path key (`<name>:path:...`) at the same
    source file → alias wins per data-model §Layer B; if aliases
    themselves collide across entries → refuse

## Migration for existing configs

None required (SC-008). Existing consumers with `harness_sources`
containing only Spec 004 shapes validate as-is under the new schema.

Test fixture: `tests/multi-spec-external-ref/fixtures/legacy-config-only/`
holds a `.haex-hive.json` copied from a Spec 004 config; the
compatibility test (`test-legacy-cache-compatibility.sh`) validates
this fixture against the new schema and asserts pass.
