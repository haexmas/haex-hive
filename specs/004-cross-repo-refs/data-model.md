# Phase 1 Data Model: Cross-Repo References

**Date**: 2026-08-27
**Feature**: 004-cross-repo-refs

Concrete entity shapes, field rules, and lifecycle transitions for
everything Spec 004 introduces or modifies.

## Entity: `.haex-hive.json` (repo-scope config)

### Shape after Spec 004

```json
{
  "haex_hive_version": "1",
  "identity": "local:haex-hive",
  "identity_note": "Placeholder while this repo has no git remote…",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "<40-char SHA>",
      "path": ".specify/memory/constitution.md"
    }
  ],
  "groups": [],
  "active_feature": null
}
```

### Field rules

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `haex_hive_version` | string, exactly `"1"` | Yes | Const value; used to detect format-forward changes. |
| `identity` | string, non-empty | Yes | Unchanged from Spec 003. |
| `identity_note` | string | No | Unchanged from Spec 003. |
| `harness_sources` | array of entries | Yes | Empty array = repo declared but permits nothing (edge case; resolver refuses everything including its own constitution). Absent field = validation error, fail-closed. |
| `groups` | array | No | Unchanged from Spec 003 (empty here). Not touched by Spec 004. |
| `active_feature` | string or null | No | Unchanged from Spec 003. |

### Removed fields (from Spec 003 shape)

| Field | Migration |
|-------|-----------|
| `constitution` (top-level object) | Content moves into `harness_sources[0]` as `role: "constitution"` entry. Field itself is deleted. |
| `external_sources` (top-level object with `.allowed` list) | Renamed to `harness_sources` AND flattened (no more nested `.allowed`). |

## Entity: `harness_sources` entry

Two entry shapes, distinguished by whether `role` is present.

### Shape A — Role-carrying (concrete pointer + self-permission)

```json
{
  "role": "constitution",
  "repository": "<self | https:// | ssh:// | user@host:path>",
  "revision": "<7-40 hex SHA>",
  "path": "<repo-relative path>"
}
```

**Rules**:
- MUST have `role`, `repository`, `revision`, and `path`.
- MUST NOT have `paths` (plural).
- `role` MUST be one of the enum values (Phase 1: `"constitution"` only).
- `revision` MUST match `^[0-9a-f]{7,40}$` — SHA only, no `"self"`.
- `repository` MAY be `"self"` (magic keyword) OR a URL passing
  scheme validation (see below).
- `path` is a single, non-empty string (repo-relative).
- Loaded automatically by the snippet at session start.
- Self-permitting — no separate permission-only entry needed to
  authorize this exact reference.

### Shape B — Permission-only (trust scope)

```json
{
  "repository": "<https:// | ssh:// | user@host:path>",
  "revision": "<optional, 7-40 hex SHA>",
  "paths": ["<optional list>", "<of paths>"]
}
```

**Rules**:
- MUST have `repository`. MAY have `revision`. MAY have `paths` (array).
- MUST NOT have `role` (that flips it to Shape A).
- MUST NOT have `path` (singular). Use `paths` (plural).
- `revision`, if present, MUST match SHA pattern (same as Shape A).
- `paths`, if present, MUST be a non-empty array of strings.
- `repository` here MUST NOT be `"self"` — permission-only entries
  are for external repos. (Rationale: a `"self"` permission-only entry
  would be either redundant with the role entry or contradictory;
  reject at load time.)
- NOT loaded automatically. Only permits external references.

### URL scheme validation (both shapes, when `repository != "self"`)

Accept if:
- Starts with `https://`.
- Starts with `ssh://`.
- Matches SCP-style pattern: exactly one `@` before host, exactly one
  `:` separating host and path, no whitespace, no scheme prefix.

Reject otherwise (including `file://`, `git://`, `http://`, bare paths).

### Entry-shape allOf constraints (JSON Schema)

- If `role` present: `revision` AND `path` MUST be present, `paths`
  MUST be absent, `repository` MAY be `"self"`.
- If `role` absent: `path` MUST be absent, `repository` MUST NOT be
  `"self"`.

## Entity: JSON Schema at `.specify/schemas/haex-hive.schema.json`

Canonical vocabulary source. Same constraints as above but expressed
in JSON Schema Draft-07.

### Location and lifecycle

- Committed at `.specify/schemas/haex-hive.schema.json`.
- Version-controlled with the rest of the repo; no separate versioning.
- Editors map `.haex-hive.json` to this schema via IDE config
  (documented in `docs/spec-resolve.md`).
- Role enum evolution: Phase 1 = `["constitution"]`. Phase 2+ widens
  as PATCH bumps to the constitution.

### Structure (skeleton)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://haex-hive.example/.specify/schemas/haex-hive.schema.json",
  "title": "haex-hive project marker",
  "type": "object",
  "required": ["haex_hive_version", "identity", "harness_sources"],
  "additionalProperties": false,
  "properties": {
    "haex_hive_version": { "const": "1" },
    "identity": { "type": "string", "minLength": 1 },
    "identity_note": { "type": "string" },
    "harness_sources": {
      "type": "array",
      "items": { "$ref": "#/definitions/harness_source_entry" }
    },
    "groups": { "type": "array" },
    "active_feature": { "type": ["string", "null"] }
  },
  "definitions": {
    "harness_source_entry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["repository"],
      "properties": {
        "role": { "enum": ["constitution"] },
        "repository": { "$ref": "#/definitions/repository_value" },
        "revision": { "type": "string", "pattern": "^[0-9a-f]{7,40}$" },
        "path": { "type": "string", "minLength": 1 },
        "paths": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 },
          "minItems": 1
        }
      },
      "allOf": [
        { "$ref": "#/definitions/role_shape_constraint" },
        { "$ref": "#/definitions/permission_shape_constraint" }
      ]
    },
    "repository_value": {
      "oneOf": [
        { "const": "self" },
        {
          "type": "string",
          "pattern": "^(https://|ssh://|[^/@:\\s]+@[^/@:\\s]+:).+"
        }
      ]
    },
    "role_shape_constraint": {
      "if": { "required": ["role"] },
      "then": {
        "required": ["revision", "path"],
        "not": { "required": ["paths"] }
      }
    },
    "permission_shape_constraint": {
      "if": { "not": { "required": ["role"] } },
      "then": {
        "not": {
          "anyOf": [
            { "required": ["path"] },
            { "properties": { "repository": { "const": "self" } } }
          ]
        }
      }
    }
  }
}
```

**Note on `additionalProperties: false`**: strict. Any unknown top-level
key or unknown entry key is a validation error. This tightens the
schema now while Phase 2 hasn't yet introduced new fields. When Phase 2
adds fields, the schema is updated (PATCH-level) in the same commit.

## Entity: `spec-resolve` (CLI tool)

### Location

`.specify/scripts/spec-resolve` (executable, `#!/usr/bin/env python3`).

### Runtime state

The tool is state-less between invocations except for the cache
directory:

```text
$XDG_CACHE_HOME/haex-hive/  (or ~/.cache/haex-hive/ if $XDG_CACHE_HOME unset)
└── repos/
    ├── <hash1>/            # bare git dir for repo-URL-1
    │   ├── HEAD
    │   ├── objects/
    │   └── ...
    ├── <hash2>/
    └── ...
```

`<hashN>` = first 16 hex chars of SHA-256(byte-identical repository URL).

### Metadata

The tool writes a small metadata file per cache directory recording
the last-fetch timestamp — used by `spec-resolve status` for the
staleness indicator (Spec 005 will extend it):

```text
~/.cache/haex-hive/repos/<hash>/
├── (bare git dir contents)
└── .haex-hive-cache-meta.json
    {
      "repository": "<original URL, for readability>",
      "first_seen": "<ISO 8601 UTC>",
      "last_fetch": "<ISO 8601 UTC>"
    }
```

## Entity: `spec-ref.json` (documented escape hatch)

Feature-scoped references. Not shipped by Spec 004, but format
committed so future features can use it consistently.

### Location

`specs/<feature>/spec-ref.json`

### Shape

```json
{
  "<name>": {
    "repository": "<URL or 'self'>",
    "revision": "<SHA>",
    "path": "<repo-relative>"
  },
  ...
}
```

- Each key is a name unique within this file (used by the feature's
  authors to identify which ref does what).
- Each value is a role-carrying-style triple (`repository`, `revision`,
  `path`) — but WITHOUT the `role` field, because these refs are
  feature-scoped and don't participate in the repo-wide role slot
  vocabulary.
- Values still go through the same allowlist enforcement — resolving
  a `spec-ref.json` entry requires a matching entry in
  `.haex-hive.json.harness_sources`.

### Validation

Also validated by JSON Schema (a companion schema in the same
`.specify/schemas/` directory would land in Phase 2 when a feature
first uses one). For Spec 004: the format is documented but no schema
file is committed for it yet — YAGNI.

## Lifecycle & state transitions

### Repo lifecycle

1. **Uninitialized**: no `.haex-hive.json`. Snippet detects absence,
   exits early, no harness enforcement.
2. **Opt-in initial**: `.haex-hive.json` committed with a minimal
   `harness_sources` containing at least the `role: "constitution"`
   entry pointing at `self`. This is the shape haex-hive itself uses.
3. **Opt-in with external sources**: additional Shape-B entries added
   to `harness_sources` for external harness repos. Each addition is
   a reviewable commit.
4. **Bump**: an entry's `revision` is updated by hand (Spec 004) or by
   `spec-resolve bump` (Spec 005). Always a reviewable commit; never
   auto-applied.

### Cache lifecycle

1. **Absent**: `~/.cache/haex-hive/` doesn't exist. Any resolve with
   a non-`self` reference triggers population.
2. **Populated**: cache dir exists per referenced repository. Resolve
   from cache without network for known SHAs.
3. **Stale metadata**: `.haex-hive-cache-meta.json.last_fetch` records
   the time; `spec-resolve status` reports elapsed time. Spec 005 uses
   this to trigger the update-check workflow.
4. **Wiped**: operator or OS-level cache cleanup removes the directory;
   next resolve re-populates.
