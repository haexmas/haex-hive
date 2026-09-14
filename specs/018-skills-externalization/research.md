# Research: External Skill References

## Decisions

1. Use a top-level `external_skills` list rather than
   `atoms.external_skills`. The `atoms` map is defined as delivered file paths;
   putting opaque registry identifiers there would make the installer copy
   them and would corrupt orphan tracking.
2. Use structured source references. A repository, immutable revision, and
   repository-relative path can be recorded for provenance without making
   spaex a skill registry. Installer selection belongs to the consumer policy, not to an
   individual reference.
3. Accept references without `install_hook`. Normal installation leaves them
   pending; the consumer explicitly invokes `spaex skills install`.
4. Keep installer choice on the consumer side. `skillsmd`, the Vercel npm CLI,
   or another compatible adapter may be selected by the user; no provider
   manifest chooses one by default.
5. Keep the v4 manifest envelope. The publisher-facing breaking behavior is
   released in the package 5.x line; existing `spaex_version: "4"` identifies
   the current manifest family and is not silently rewritten.

## Existing Capabilities Reused

- `MoleculeManifest.from_json()` is the public parse boundary.
- `jsonschema` validates shape and rejects unknown top-level properties.
- Spec 016's `install_hook` remains available for unrelated provider side
  effects. Skill installation uses a consumer-selected adapter, with the
  original pinned manifest exposed as `SPAEX_MOLECULE_MANIFEST`.

## Not Implemented Here

- Registry discovery or skill content download by spaex itself.
- Treating `agentskills.io` as an installer; it defines the skill format.
- Skill SHA pinning in the spaex lockfile.
- Editing the external `haexmas/atoms` repository. The contract supports a
  skill stored there, referenced through a revision-specific repository/tree
  source and installed by the consumer-selected adapter.
