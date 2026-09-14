# Research: External Skill References

## Decisions

1. Use a top-level `external_skills` list rather than
   `atoms.external_skills`. The `atoms` map is defined as delivered file paths;
   putting opaque registry identifiers there would make the installer copy
   them and would corrupt orphan tracking.
2. Use structured source references. A repository, immutable revision, and
   repository-relative path can be recorded for provenance without making
   spaex a skill registry. Installer selection belongs to the hook, not to an
   individual reference.
3. Require `install_hook` when the list is non-empty. A declaration without an
   execution path would look supported while doing nothing.
4. Use `skillsmd` as the default installer adapter. It is a Python port of the
   Vercel skills CLI and can be executed through the uv runtime already
   available to spaex. The Vercel npm CLI remains an optional adapter.
5. Keep the v4 manifest envelope. The publisher-facing breaking behavior is
   released in the package 5.x line; existing `spaex_version: "4"` identifies
   the current manifest family and is not silently rewritten.

## Existing Capabilities Reused

- `MoleculeManifest.from_json()` is the public parse boundary.
- `jsonschema` validates shape and rejects unknown top-level properties.
- Spec 016's `install_hook` is already the explicit, trusted side-effect
  boundary and supports arbitrary external commands through a publisher-owned
  script.

## Not Implemented Here

- Registry discovery or skill content download by spaex itself.
- Treating `agentskills.io` as an installer; it defines the skill format.
- Skill SHA pinning in the spaex lockfile.
- Editing the external `haexmas/atoms` repository. The contract supports a
  skill stored there, referenced through a revision-specific repository/tree
  source and installed by the hook.
