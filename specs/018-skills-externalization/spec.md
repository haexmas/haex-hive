# Feature Specification: External Skill References

**Feature Branch**: `018-skills-externalization`
**Created**: 2026-09-14
**Status**: Draft — awaiting operator review
**Input**: Phase A of the composition UI and skills externalization roadmap

## Clarifications

### Session 2026-09-14

- Q: Wie wird ein externer Skill beim Nutzer installiert und woher kommt der
  Installer? → A: `external_skills` wird strukturiert modelliert. Der
  Standardadapter ist das unabhängige Python-Paket `skillsmd`, das der Hook
  über `uvx --from skillsmd==<version> skillsmd add ...` ausführt. Die Vercel-
  `skills`-CLI bleibt eine optionale npm-Alternative; `agentskills.io` ist nur
  die Format-Spezifikation und kein Installer.
- Q: Wie erhält das Hook-Skript die strukturierten Referenzen? → A: Es liest
  das bereits gepinnte Molekül-`manifest.json` direkt. spaex erzeugt keine
  temporäre JSON-Kopie und dupliziert die Referenzen nicht in einer zweiten
  Übergabedatei. Für robuste Pfadauflösung stellt spaex dem Hook den Pfad des
  Originalmanifests über `SPAEX_MOLECULE_MANIFEST` zur Verfügung.
- Q: Gehört der Installer in jede einzelne Skill-Referenz? → A: Nein. Eine
  Referenz enthält nur Quelle, Revision und Pfad. Der Installer ist Hook-Policy
  und wird standardmäßig über `skillsmd` im Hook ausgewählt.

## User Scenarios & Testing

### User Story 1 - Declare an external skill without copying it (Priority: P1)

As a molecule publisher, I can keep a standard Agent Skill in the same
publisher repository (or another repository) and declare its source reference
separately from delivered file atoms, so spaex records the dependency without
materializing the skill itself.

**Independent Test**: Parse a molecule manifest containing `external_skills`
and verify that the references are exposed as immutable values while no skill
file is added to the atom map.

**Acceptance Scenarios**:

1. **Given** a valid external skill reference, **when** a v4 molecule manifest
   is parsed, **then** the reference is preserved in declaration order.
2. **Given** a molecule with external skills but no `install_hook`, **when**
   the manifest is validated, **then** validation refuses it because no
   installation mechanism is declared.
3. **Given** a skill stored under `haexmas/atoms/skills/`, **when** a molecule
   references its revision-specific repository/tree source, **then** the skill
   remains owned by the publisher repository and is installed by the hook's
   external installer rather than by spaex's atom materializer.

### User Story 2 - Prevent the retired skill atom category (Priority: P1)

As a spaex maintainer, I want old `skill`/`skills` atom declarations to fail
clearly, so publishers cannot silently continue shipping registry-owned skill
files through spaex.

**Independent Test**: Validate manifests using either retired category and
assert a schema refusal before any install resolution occurs.

**Acceptance Scenarios**:

1. **Given** `atoms.skill` or `atoms.skills`, **when** the manifest is
   validated, **then** schema validation rejects the manifest.
2. **Given** an unrelated open atom category, **when** the manifest is
   validated, **then** it remains accepted.

### User Story 3 - Delegate installation through the existing hook boundary (Priority: P2)

As a molecule publisher, I can keep the actual Agent Skills installation in
the existing `install_hook`, using the Python/uv-based `skillsmd` adapter by
default, so spaex remains independent of any skill registry and the normal
hook trust/failure semantics apply.

**Independent Test**: Install a fixture molecule with `external_skills` and an
`install_hook`; verify the normal hook runner is used and the skill reference
itself is not treated as a file path.

## Edge Cases

- Empty or whitespace-only references are invalid.
- References containing control characters are invalid.
- Duplicate references are invalid.
- A molecule without `external_skills` remains backwards-compatible.
- `install_hook` failure behavior remains governed by Spec 016; this feature
  does not add a second execution mechanism.

## Requirements

### Functional Requirements

- **FR-001**: A molecule manifest MUST accept an optional top-level
  `external_skills` array of unique, structured skill references. Each
  reference MUST declare a repository, a full immutable revision SHA, and a
  repository-relative skill path. The reference MUST NOT declare an installer.
- **FR-002**: `external_skills` objects MUST be preserved in declaration order
  and MUST be exposed immutably by `MoleculeManifest`.
- **FR-003**: A molecule declaring at least one external skill MUST also
  declare `install_hook`.
- **FR-004**: The schema MUST reject `atoms.skill` and `atoms.skills`.
- **FR-005**: Other atom category names MUST remain open and unchanged.
- **FR-006**: spaex MUST NOT copy, resolve, pin, or otherwise install external
  skill content itself; the declared install hook remains the execution
  boundary. The default hook adapter MUST be invokable through `uvx` and the
  pinned `skillsmd` package. The referenced skill MAY live under the same
  publisher repository as the molecule.
- **FR-007**: Existing molecules without `external_skills` MUST remain valid.
- **FR-008**: Documentation MUST describe the external installer limitation:
  the molecule SHA and installer package version MAY be pinned by the hook,
  but the installed skill content remains outside spaex's lockfile.
- **FR-009**: Phase A MUST NOT require moving skills out of the publisher
  repository. A publisher MAY keep molecule files and standard `SKILL.md`
  directories in `haexmas/atoms`.
- **FR-010**: The install hook MUST read the structured skill references from
  the pinned molecule manifest, using `SPAEX_MOLECULE_MANIFEST` when resolving
  the manifest path. spaex MUST NOT create a second serialized copy solely to
  pass `external_skills` to the hook.

### Key Entities

- **External skill reference**: A structured installer/source declaration that
  may identify a repository, immutable revision, and repository-relative
  skill path. The source content remains external to spaex.
- **Molecule**: A pinned spaex bundle that may deliver files and may declare
  external references whose side effects are delegated to its install hook.

### Scope boundary: ownership versus delivery

The publisher repository owns the source tree for both molecules and any
co-located Agent Skills. The distinction is the delivery mechanism:

- `atoms.<category>` lists files that spaex materializes and records in
  `install.lock`.
- `external_skills` lists structured skill sources that spaex records as
  metadata.
- `install_hook` delegates the actual skill installation to an external
  installer. The default adapter is `uvx skillsmd`; it owns the agent-specific
  target and lifecycle.
- The hook reads the original pinned molecule manifest through
  `SPAEX_MOLECULE_MANIFEST`; no generated external-skills payload is created.

Therefore Phase A does not delete or relocate skills from `haexmas/atoms`; it
removes only the old spaex-delivered `skill`/`skills` atom contract.

## Success Criteria

- **SC-001**: Valid external-skill manifests parse and expose references
  without materializing a skill file.
- **SC-002**: 100% of manifests using the retired skill categories fail schema
  validation before install resolution.
- **SC-003**: Existing non-skill molecule fixtures continue to pass the full
  contract and integration test suite.
- **SC-004**: The feature adds no runtime dependency on Node, skills.sh, or
  agentskills.io; the default installer is obtained through the user's
  existing `uvx` runtime.

## Assumptions

- The existing v4 manifest envelope remains the schema envelope; the spaex
  package major version records the intentional publisher-facing break.
- Hook authors may invoke `uvx --from skillsmd==<version> skillsmd add ...`.
  The Vercel `skills` npm CLI remains an optional alternative, while
  `agentskills.io` is treated as the format specification rather than an
  installer. spaex does not synthesize or execute an installer command
  automatically.
- A skill MAY remain in `haexmas/atoms`; migration changes the molecule's
  delivery contract, not necessarily the skill repository layout.
