# New Schema: `haex-hive-local.schema.json`

**Phase**: 1 (planning)
**Spec references**: FR-017, FR-018, FR-020
**Data model**: [data-model.md](../data-model.md) §Layer B

Schema for the device-local `.haex-hive.local.json` file. New in
Spec 006. Written to
`.specify/schemas/haex-hive-local.schema.json`.

## Purpose

`haex-init sync` validates the LocalStateTable it constructs
in-memory against this schema **before** the atomic write, so no
malformed local-state file ever hits disk. Reader tools (session-start
snippet, agent-side integrations) validate against this schema
before use — a mismatched or corrupted file triggers a clear error
instead of an obscure attribute lookup failure.

## Schema (JSON-Schema Draft 2020-12)

```jsonc
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://haex-hive.example.com/schemas/haex-hive-local.schema.json",
  "title": "haex-hive device-local state table",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "haex_hive_local_version",
    "generated_from_config",
    "generated_at",
    "device",
    "state_area",
    "constitutions",
    "resolved"
  ],
  "properties": {
    "haex_hive_local_version": { "const": "1" },
    "generated_from_config": {
      "type": "string",
      "pattern": "^sha256:[0-9a-f]{64}$"
    },
    "generated_at": {
      "type": "string",
      "format": "date-time"
    },
    "device": {
      "type": "string",
      "minLength": 1,
      "description": "Hostname or persistent device id. Informational."
    },
    "state_area": {
      "type": "string",
      "minLength": 1,
      "description": "Absolute path to $HAEX_HIVE_STATE at generation time. Enables tools to detect state-area migration or divergence."
    },
    "constitutions": {
      "type": "array",
      "items": { "$ref": "#/$defs/ConstitutionSource" }
    },
    "resolved": {
      "type": "object",
      "additionalProperties": {
        "type": "string",
        "minLength": 1
      },
      "propertyNames": { "$ref": "#/$defs/ResolvedKey" }
    }
  },
  "$defs": {
    "ConstitutionSource": {
      "type": "object",
      "additionalProperties": false,
      "required": ["source", "label"],
      "properties": {
        "source": { "enum": ["role", "resolved"] },
        "role":   { "const": "constitution" },
        "key":    { "$ref": "#/$defs/ResolvedKey" },
        "label":  { "type": "string", "minLength": 1 }
      },
      "oneOf": [
        {
          "properties": { "source": { "const": "role" } },
          "required": ["role"],
          "not": { "required": ["key"] }
        },
        {
          "properties": { "source": { "const": "resolved" } },
          "required": ["key"],
          "not": { "required": ["role"] }
        }
      ]
    },
    "ResolvedKey": {
      "type": "string",
      "pattern": "^[A-Za-z0-9._-]+:(path:.+|[a-z0-9][a-z0-9-]*)$",
      "description": "Either <name>:<alias> (alias per FR-006 grammar) or <name>:path:<repo-relative-path>. Storage name accepts the wider StorageName grammar."
    }
  }
}
```

## Read semantics

- **Reader tools** MUST schema-validate before consuming. Corruption
  or version-mismatch → refuse with a clear error, do NOT partially
  interpret.
- **`generated_from_config`** enables freshness check: reader hashes
  the current `.haex-hive.json`, compares with the stored hash; if
  they differ, the table is stale and the reader can prompt the
  operator to re-run `haex-init sync` (or silently trigger it, if
  the reader is that kind of tool — Spec 006 does neither, but the
  hook is here).
- **`state_area`** enables reader tools to sanity-check the paths
  in `resolved` against the current device's state-area. If
  `state_area` no longer matches (e.g., operator moved from one
  device to another), reader should refuse and prompt for a
  re-`sync`.

## Regeneration

`haex-init sync` regenerates the file end-to-end on every
invocation. There is no partial update — the file is either the
full current state or absent.

## Filesystem posture

- **Path**: `<consumer-repo>/.haex-hive.local.json`
- **Gitignored**: FR-018 (managed marker block in `.gitignore`)
- **Permissions** on Unix-like: `0600` after write (FR-038)
- **Atomicity**: `os.replace` from same-directory temp file
  (FR-024, Research §3)
