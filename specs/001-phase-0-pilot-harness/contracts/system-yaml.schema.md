# Contract: `.specify/system.yaml`

**Owner**: this feature (spec 001) defines the shape; every subsequent
haex-hive-managed repo consumes it.
**Location**: `.specify/system.yaml` at the repo root.
**Status**: v1.0 — first defined here.

## Purpose

Declare, per repository, which external harness sources this repo may
consume. Constitutional Principle V (External Sources Are Opt-in Per Project)
requires an explicit statement per project — no implicit inheritance from
sibling directories, sibling repos, or global agent instruction files.

## Schema

```yaml
system:
  id: <string>                     # REQUIRED. Lower-kebab-case project identifier.
                                   # Stable across renames of the working directory.

external_sources:
  allowed: []                      # REQUIRED. List of allowlisted external harness sources.
                                   # Empty list means: no external harness content, ever.
                                   # Each entry (when non-empty) has the shape:
                                   #   - repository: <string>   # e.g. "itemis/solutions/pltf/secana-specs"
                                   #     revision:   <string>   # full Git commit SHA — no branch, no tag ref
                                   #     paths:      [<string>] # optional; list of repo-relative paths this repo
                                   #                            # is permitted to consume from that source.
                                   #                            # Omit or empty = whole repo permitted.
```

### Required top-level keys

- `system.id` — human-legible project identifier. Referenced by the harness
  registry and by cross-repo tooling. MUST NOT change once a project starts
  producing cross-repo references, since references may pin it.
- `external_sources.allowed` — MUST be present, MAY be empty. Absent
  interpretation is not permitted: haex-hive-aware tooling MUST treat a
  missing key the same as "file malformed, refuse to proceed" — never as an
  implicit empty list. The strict interpretation is deliberate: silent
  fall-through to "no sources" would hide typos that would otherwise be
  caught.

### Optional keys

None in v1.0. Future extensions (e.g. tool-specific overrides, capability
declarations for satellite selection) will be added under new top-level
keys, never by overloading existing ones.

### Rules

1. **Immutable revisions only**: every `revision` value in `allowed[]` MUST
   be a full Git commit SHA, never a branch name or `HEAD`. Enforced by
   inspection at review time; will be enforced mechanically by CI in a later
   phase.
2. **No local filesystem paths**: nothing in this file may resolve to a
   local absolute path. `paths[]` entries are repo-relative to the external
   `repository`, not to this repo.
3. **No secrets**: the file may reference identity aliases (Principle I) but
   never keys, tokens, or credentials.

## Example (this repo, Phase 0)

```yaml
system:
  id: haex-hive
external_sources:
  allowed: []
```

Meaning: haex-hive at Phase 0 is fully isolated. No external harness content
is inherited. This is the strictest possible legal state and the one User
Story 3 in `../spec.md` validates.

## Example (future — for reference only)

```yaml
system:
  id: some-work-service
external_sources:
  allowed:
    - repository: itemis/solutions/pltf/secana-specs
      revision: 7ae4c218e140abc123def456789012345678abcd
      paths:
        - .specify/memory/constitution.md
        - features/PAY-142-refund-flow/spec.md
```

Meaning: `some-work-service` is permitted to resolve exactly the two named
paths from that exact revision of secana-specs, and nothing else — not other
files in that repo, not other revisions, and no other external repos.

## Contract test

The Phase 0 feature validates this contract at the instance level (the
concrete `.specify/system.yaml` in haex-hive parses as v1.0-conformant and
declares an empty allowlist). Broader validation — a schema-conformance
checker used by CI — is deferred to Phase 7 per the design doc.
