# Contract: `.haex-hive.json` schema (v1)

**Location**: repo root.
**Purpose**: opt-in marker that declares a repo as haex-hive-governed and
points at the canonical constitution the operator's session must load.

## Required top-level fields

- `haex_hive_version` (string, exact value `"1"` for schema v1). Consumers
  MUST refuse to process files without this field or with an unknown value.
- `identity` (string). Device-independent identity per Principle III.
  Canonical form is the git remote URL of the repo (without protocol
  prefix), e.g. `"github.com/owner/repo"`. During the prototype phase
  before a repo has been pushed, `"local:<slug>"` is permitted with an
  accompanying `identity_note` explaining the placeholder.
- `constitution` (object). Points at the canonical constitution the
  session must load. See "Constitution reference" below.
- `groups` (array of strings, may be empty). Group memberships per the
  haex-hive design's group-referencing mechanism (Phase 1+).
- `external_sources` (object). Per-project allowlist for external
  harnesses per Principle V. See "External sources" below.
- `active_feature` (string or null). Path to the currently active
  spec-kit feature directory, e.g. `"specs/003-config-file-based-delivery"`.
  MUST be `null` when no feature is active, and MUST refer to a
  directory that actually exists in the tree when non-null.

## Optional top-level fields

- `identity_note` (string). Explanatory text for a placeholder identity.
  Only meaningful while `identity` is a `local:<slug>` placeholder.

## Constitution reference

The `constitution` object MUST contain:

- `repository` (string). The git remote URL of the repo hosting the
  constitution, in the same shape as top-level `identity`. The special
  value `"self"` is permitted when the constitution lives in the same
  repo as `.haex-hive.json` (haex-hive itself is currently the only
  case).
- `revision` (string). A full 40-character git commit SHA pinning the
  version of the constitution the operator committed to. Branch
  references and short SHAs are NOT permitted (Principle IV).
- `path` (string). Repo-relative path to the constitution file within
  the referenced repository. Typically `.specify/memory/constitution.md`.
- `note` (string, optional). Free-form explanation, e.g. describing the
  self-reference case.

## External sources

The `external_sources` object MUST contain:

- `allowed` (array of objects, may be empty). Each entry represents an
  external harness this project has opted in to per Principle V. Entry
  shape (per Principle V, spec 001's contract, and ADR 0002):
  - `repository` (string), `revision` (string, full SHA), `path` (string
    or array of strings).

## Example (haex-hive itself, prototype state)

```json
{
  "haex_hive_version": "1",
  "identity": "local:haex-hive",
  "identity_note": "Placeholder while this repo has no git remote. Becomes the canonical remote URL once the repo is pushed.",
  "constitution": {
    "repository": "self",
    "revision": "d7a9c6475568bb5484bdf9491daf9eeef1f4fa91",
    "path": ".specify/memory/constitution.md",
    "note": "Self-referential during the prototype: the constitution lives in this same repo."
  },
  "groups": [],
  "external_sources": {
    "allowed": []
  },
  "active_feature": "specs/003-config-file-based-delivery"
}
```

## Session-time integrity checks

A CLI session executing the global detection snippet SHOULD:

1. Confirm the schema by verifying `haex_hive_version == "1"` and the
   presence of the required top-level fields.
2. Resolve `constitution.path` relative to either the repo root (if
   `constitution.repository == "self"`) or the appropriate external
   checkout, and read the file.
3. Verify integrity: either the commit currently referring to the
   constitution file matches `constitution.revision`, or the blob hash
   of the on-disk file matches the blob hash at `constitution.revision`.
   Any drift MUST be reported to the operator before the session
   applies the constitution.
4. If `active_feature` is non-null, confirm the referenced directory
   exists and report a drift finding otherwise.

## Contract tests

- **T1**: `jq .haex_hive_version .haex-hive.json` returns `"1"`.
- **T2**: `constitution.revision` matches `^[0-9a-f]{40}$`.
- **T3**: `constitution.path` resolves to a real file when
  `constitution.repository == "self"`.
- **T4**: `active_feature` is `null` OR a directory that exists.

The 2026-08-27 validation run demonstrated T1-T4 emergently — both
Claude Code and Codex sessions confirmed the fields, verified integrity
via blob-hash comparison, and (in Claude's T-A response) surfaced the
T4 violation that led to commit `c5f83de`.
