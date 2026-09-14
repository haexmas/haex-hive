# Research: External Skill References

## Decisions

1. Use a top-level `external_skills` list rather than
   `atoms.external_skills`. The `atoms` map is defined as delivered file paths;
   putting opaque registry identifiers there would make the installer copy
   them and would corrupt orphan tracking.
2. Keep references opaque strings. `skills.sh` slugs and agentskills.io
   repository paths are different upstream formats; spaex should validate
   safe input boundaries without inventing a registry grammar.
3. Require `install_hook` when the list is non-empty. A declaration without an
   execution path would look supported while doing nothing.
4. Keep the v4 manifest envelope. The publisher-facing breaking behavior is
   released in the package 5.x line; existing `spaex_version: "4"` identifies
   the current manifest family and is not silently rewritten.

## Existing Capabilities Reused

- `MoleculeManifest.from_json()` is the public parse boundary.
- `jsonschema` validates shape and rejects unknown top-level properties.
- Spec 016's `install_hook` is already the explicit, trusted side-effect
  boundary and supports arbitrary external commands through a publisher-owned
  script.

## Not Implemented Here

- Registry discovery or skill content download.
- Skill SHA pinning in the spaex lockfile.
- Editing the external `haexmas/atoms` repository. The contract supports a
  skill stored there, referenced through a revision-specific repository/tree
  source and installed by the hook.
