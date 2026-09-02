# Feature Specification: Speckit Workflow Atom

**Feature Branch**: `011-simplify-workflow-atom` (rewrite of the previously-merged spec on the same slot)
**Created**: 2026-09-02 (original), 2026-09-02 (simplified re-specification)
**Status**: Draft (simplification amendment)
**Input**: User description: "haex-hive gains a new `speckit-workflow` atom kind that lets a project pin a specific speckit workflow (workflow.yml plus optional constitution.md fragment, extensions.yml with required community-extension pins, and per-hook scripts) via `.haex-hive.json`; on `haex install` the workflow files publish under `.specify/workflows/<atom-id>/`, the constitution fragment merges into `.haex-hive/constitution.md` via the existing multi-source flow, and the adopted workflow atom becomes automatically binding."

**Authoritative requirements source**: [docs/plans/2026-09-02-spec-011-speckit-workflow-atom-design.md](../../docs/plans/2026-09-02-spec-011-speckit-workflow-atom-design.md).

## 2026-09-02 amendment: simplified model

The originally-merged spec 011 (PRs #51 spec + #52 plan + #53 tasks) introduced a `workflow-registry.json` file with an `active_workflow` selector, an `extension_contributions` provenance cache, a `.registry` cross-check with `installed-extension-metadata-mismatch` diagnostic, and bytewise-UTF-8 atom-id ordering rules for multi-atom merges. An operator review on the same day identified all four as over-engineering that two simplifications obviate:

1. **One workflow atom active per repository** (no coexistence). A workflow is a whole (specify -> plan -> tasks -> implement + review gates + hooks), not a slice to be blended with another workflow. A project either follows one full workflow or the bundled default. Multi-workflow slicing per branch or role is out of scope.
2. **Trust-git for our content; trust the extension-installer's own metadata for third-party extensions.** SHA-pinned atoms guarantee our own bytes; specifyr's installed `extension.yml` is authoritative for a third-party extension's version. haex-hive does not second-check specifyr's `.registry` file for internal consistency.

**Retired from the merged spec 011**:

- **FR-006 (workflow registry)** retired. No `.specify/workflows/workflow-registry.json` file. No `active_workflow` field. No workflow catalogue. Adoption alone determines binding.
- **FR-008 (reader resolution)** simplified: the reader inspects `.haex-hive.json` for a `contributes.speckit_workflow` atom; found -> that workflow is binding; absent -> the bundled `.specify/workflows/speckit/workflow.yml` is binding. No registry lookup.
- **US4 (coexistence)** retired. Under one-active-per-repo the scenario cannot exist.
- **Bytewise UTF-8 atom-id ordering** retired. With one workflow atom max, no cross-atom order ambiguity exists.
- **`extension_contributions` provenance cache** retired. `.specify/extensions.yml` regenerates from scratch on every install from the current adopted workflow atom's fragment plus local declarations.
- **`installed-extension-metadata-mismatch` diagnostic key** retired.
- **`.registry` cross-check against `extension.yml`** retired.
- **`workflow-atom-reset-to-default` diagnostic key** retired (no active_workflow to reset).

**Added by this amendment**:

- **New FR (fills FR-006 slot)**: `haex install` MUST refuse when `.haex-hive.json`'s adopted atoms declare two or more atoms whose manifest carries `contributes.speckit_workflow`. Refusal is `key=multiple-workflow-atoms-refused`, exit code reuses `INPUT_REFUSE`.

Everything else the merged spec 011 required (atom-manifest field shape and path containment, publication targets, hook-script publication and namespace collisions, constitution-fragment merge, extensions-fragment merge with required/optional constraints, required-extension install-time gate, delete-orphans on removal, concealment guard) survives unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Adopt a workflow atom and it becomes binding (Priority: P1) MVP

An operator wants their project to follow a specific speckit workflow (a stricter TDD variant, a bugfix-first flow) instead of the bundled `Full SDD Cycle`. They add one `speckit-workflow` atom to `.haex-hive.json` pinned by full 40-char SHA and run `haex install`. On success, the atom's `workflow.yml` publishes under `.specify/workflows/<atom-id>/`, its constitution fragment merges into `.haex-hive/constitution.md` under a `## Workflow-Contributed Rules` section, and the workflow is automatically binding. No selector step, no registry edit.

**Why this priority**: This is the MVP. Without a working adopt-and-bind path, no other user story matters.

**Independent Test**: On a fresh consumer checkout with one `speckit-workflow` atom in `.haex-hive.json`, run `haex install --llm=file` + `--accept-merged <candidate>` end-to-end. Assert (a) `.specify/workflows/<atom-id>/workflow.yml` is byte-identical to the atom's contribution; (b) hook scripts publish under `.specify/extensions/workflow-atoms/<atom-id>/`; (c) `.haex-hive/constitution.md` contains a `## Workflow-Contributed Rules` section with the atom's fragment under a `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` byline; (d) reader helper called against the consumer returns the atom-workflow's path (not the bundled path).

**Acceptance Scenarios**:

1. **Given** a consumer `.haex-hive.json` adopting exactly one `speckit-workflow` atom at a pinned SHA reachable under `$HAEX_HIVE_STATE/repos/`, **When** the operator runs `haex install`, **Then** the atom's `workflow.yml` publishes at `.specify/workflows/<atom-id>/workflow.yml`, its per-hook scripts publish under `.specify/extensions/workflow-atoms/<atom-id>/`, the constitution fragment merges into the shared `## Workflow-Contributed Rules` section under a `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` byline, `.specify/extensions.yml` gains the atom's required/optional extensions and hook wiring, and `install.lock.atoms[]` records `(id, source, revision, contributed_paths)` for the atom.
2. **Given** a workflow atom whose `contributes.speckit_workflow` path or any `contributes.speckit_hooks/**` source path escapes the atom root (absolute, backslash-qualified, `.`/`..` traversal, symlink escape), **When** `haex install` resolves the atom, **Then** the install refuses before any file publication with a diagnostic naming the offending path and citing Principle II.
3. **Given** a workflow atom declaring a hook whose script has no matching source file, maps to a non-regular source, is mapped twice, or maps outside the atom's reserved `workflow-atoms/<atom-id>/` namespace, **When** `haex install` validates the hook mapping, **Then** the install refuses before publication with `key=workflow-hook-mapping-invalid` naming the source and destination paths on stderr.
4. **Given** a workflow atom whose reserved atom-owned destination under `.specify/extensions/workflow-atoms/<atom-id>/` would collide with a community-extension file already installed at that path, **When** `haex install` validates the publication targets, **Then** the install refuses before publication with `key=workflow-atom-extension-id-collision` naming the colliding path.

### User Story 2 - Required-extension validator refuses missing or incompatible extensions (Priority: P2)

An operator adopts a workflow atom whose `required_extensions` names a speckit-community extension that is either absent under `.specify/extensions/` or installed at a version outside the atom's declared constraint. `haex install` MUST refuse before any file publication with a clear operator-facing diagnostic.

**Why this priority**: Without this refusal, the workflow silently binds while the tooling it depends on is missing; every downstream `/speckit-<step>` invocation fails opaquely inside a spec-authoring session. Install-time refusal beats runtime failure.

**Independent Test**: Adopt a workflow atom declaring `required_extensions: [{id: v-model-extension-pack, version_constraint: ">=0.7.2"}]` while ensuring `.specify/extensions/v-model-extension-pack/` does NOT exist. Run `haex install`. Assert exit code non-zero, stderr contains `key=required-workflow-extension-missing`, and no files under `.specify/workflows/` or `.haex-hive/` were written.

**Acceptance Scenarios**:

1. **Given** a workflow atom declaring a required extension that is not installed locally, **When** `haex install` runs, **Then** it refuses with `key=required-workflow-extension-missing` before any file publication and stderr names the missing extension id and version constraint.
2. **Given** a workflow atom declaring `required_extensions: [{id: bugfix-workflow, version_constraint: "1.0.0"}]` and a locally installed `bugfix-workflow` whose `extension.yml` records version `2.0.0`, **When** `haex install` runs, **Then** it refuses with `key=required-workflow-extension-incompatible` and stderr names the found and expected versions.
3. **Given** a workflow atom whose `optional_extensions` names a missing extension, **When** `haex install` runs, **Then** the install proceeds successfully and the missing optional extension surfaces only as a stderr warning.
4. **Given** a workflow atom's fragment that declares the same extension id twice within `required_extensions[]`, **When** `haex install` loads the fragment, **Then** it refuses with `key=workflow-atom-extension-id-collision`.
5. **Given** a workflow atom whose extension declaration uses an unparseable version-constraint syntax (unsupported grammar), **When** `haex install` parses the fragment, **Then** it refuses with `key=invalid-constraint` naming the offending value.
6. **Given** a workflow atom whose fragment declares the same extension id with contradictory `homepage` metadata values across `required_extensions` and `optional_extensions`, **When** `haex install` validates the fragment, **Then** it refuses with `key=conflicting-extension-metadata` naming the extension id and both values.

### User Story 3 - Downgrade path removes the workflow atom's artifacts (Priority: P2)

An operator decides they no longer want the atom-adopted workflow. They remove the atom entry from `.haex-hive.json` and run `haex install`. The atom's previously-published files disappear, its constitution fragment stops appearing in the merged output, and the bundled workflow becomes binding again by virtue of no atom claiming that role.

**Why this priority**: Removal must be a first-class operation, not a manual `rm -rf`. Under Spec 008 US4 (delete-orphans), removing an atom from `.haex-hive.json` automatically clears its contributions.

**Independent Test**: Start from US1 endpoint (workflow atom adopted). Remove the atom entry from `.haex-hive.json`. Run `haex install`. Assert (a) `.specify/workflows/<atom-id>/` is absent; (b) `.specify/extensions/workflow-atoms/<atom-id>/` is absent; (c) the atom's `## Workflow-Contributed Rules` subsection no longer appears in `.haex-hive/constitution.md`; (d) `.specify/extensions.yml` no longer contains the atom's requirements or hook entries; (e) the reader helper returns the bundled `.specify/workflows/speckit/workflow.yml` path.

**Acceptance Scenarios**:

1. **Given** a consumer with a previously-adopted workflow atom, **When** the operator removes the atom from `.haex-hive.json` and runs `haex install`, **Then** the atom's `.specify/workflows/<atom-id>/` directory, its `.specify/extensions/workflow-atoms/<atom-id>/` hook scripts, and its constitution fragment are removed atomically as part of the R1 rename-swap generation; unrelated atoms and local declarations survive verbatim.
2. **Given** an in-flight install that crashed mid-swap during a downgrade, **When** the operator retries `haex install`, **Then** Spec 008's detect-and-retry recovery converges to the fully-downgraded state on the retry; the removed atom's files are absent afterward.

### User Story 4 - Refuse multiple workflow-atom adoptions (Priority: P2)

An operator accidentally adopts two `speckit-workflow` atoms in the same `.haex-hive.json`. Because the workflow is a whole (steps + review gates + hook wiring), two workflows cannot both be binding at the same time. `haex install` MUST refuse before any file publication with a clear diagnostic naming both atoms.

**Why this priority**: Without this refusal, the second-adopted atom would silently shadow or clobber the first (depending on merge order), producing a project that follows some blend the operator never approved.

**Independent Test**: Author a consumer `.haex-hive.json` adopting two atoms both carrying `contributes.speckit_workflow`. Run `haex install`. Assert exit code non-zero, stderr contains `key=multiple-workflow-atoms-refused` and names both atom ids, and no files under `.specify/workflows/` or `.haex-hive/` were written.

**Acceptance Scenarios**:

1. **Given** a consumer `.haex-hive.json` adopting two `speckit-workflow` atoms simultaneously, **When** `haex install` resolves the atoms, **Then** it refuses with `key=multiple-workflow-atoms-refused`, names both atom ids and their sources on stderr, and no files are written under `.specify/workflows/` or `.haex-hive/`.
2. **Given** a consumer transitioning from workflow atom A to workflow atom B, **When** the operator sequences the change as two commits (remove A then add B) and runs `haex install` after each, **Then** each individual `haex install` sees exactly one workflow atom and succeeds; the intermediate state after removing A but before adding B leaves the bundled workflow binding, matching US3's semantics.

### Edge Cases

- **Atom carries `contributes.speckit_extensions` or `contributes.speckit_hooks` without `contributes.speckit_workflow`**: refused before staging. An atom declaring extension or hook wiring is only meaningful under a workflow atom; without the workflow field it is a broken atom.
- **Atom carries `contributes.speckit_workflow` but no `constitution.md` fragment**: valid. The atom binds a workflow without imposing constitution rules; only the workflow.yml + hooks land.
- **Adopted workflow atom's `constitution.md` fragment contains concealment instructions**: refused by the existing Principle VIII validator during the multi-source merge, identical to any other constitution fragment.
- **Adopted workflow atom's fragment declares an extension id under both `required_extensions[]` and `optional_extensions[]`**: the required declaration wins for install-time refusal purposes; if the required and optional version constraints on the same id are compatible, the optional entry is retained; if incompatible, the optional entry is dropped and stderr emits `key=optional-workflow-extension-conflict` as a warning.
- **Empty adopted-atoms set (no workflow atom at all)**: the bundled `.specify/workflows/speckit/workflow.yml` is binding by fallback; `haex install` publishes it as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (Workflow atom shape): The atom-manifest schema MUST accept three new optional `contributes.*` fields: `speckit_workflow` (path to workflow.yml, required for workflow-atom kind), `speckit_extensions` (path to extensions.yml fragment), and `speckit_hooks` (path to a hooks directory). Every declared path MUST pass `RepoRelativePath.validate` and a canonical containment check against both the atom root at load time and the consumer repo root at publication time. Absolute paths, backslash- or drive-qualified paths, `.`/`..` traversal, and symlink or reparse-point targets that escape either root MUST refuse before publication with a Principle II citation. An atom declaring `speckit_extensions` or `speckit_hooks` without `speckit_workflow` MUST refuse before publication.
- **FR-002** (Publication location): When exactly one workflow atom is adopted, `haex install` MUST publish its `workflow.yml` to `.specify/workflows/<atom-id>/workflow.yml` where `<atom-id>` is the atom's reverse-DNS id. The bundled `.specify/workflows/speckit/workflow.yml` remains untouched by atom adoption. There is no registry file to update.
- **FR-003** (Hook scripts and namespace): When the workflow atom declares `contributes.speckit_hooks`, `haex install` MUST copy every file under the source directory to `.specify/extensions/workflow-atoms/<atom-id>/` with the same relative structure. `workflow-atoms/` is a reserved atom-owned namespace under `.specify/extensions/`; community extensions occupy sibling direct-child paths. Before publication, the installer MUST refuse with `key=workflow-hook-mapping-invalid` for any hook whose declared `script` destination has no matching source file, whose source is not a regular file, whose destination escapes the atom-owned directory, or which is declared more than once within the fragment. The installer MUST refuse with `key=workflow-atom-extension-id-collision` if any atom-owned destination would overwrite a community-extension file already installed at that path. Hook cleanup on downgrade MUST touch only paths under the matching atom-owned directory.
- **FR-004** (Constitution fragment merge): When the adopted workflow atom declares `contributes.constitution`, its fragment MUST participate in the existing multi-source constitution merge. The merged output MUST contain one `## Workflow-Contributed Rules` section; the fragment is appended under a `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` byline. The merge MUST retain the review-gated two-phase flow (`haex install --llm=file` / `--accept-merged`) per Principle VI. When no workflow atom contributes a fragment, the `## Workflow-Contributed Rules` section is omitted.
- **FR-005** (Extensions fragment merge): When the adopted workflow atom declares `contributes.speckit_extensions`, its `required_extensions[]`, `optional_extensions[]`, and any `hooks.<stage>[]` entries MUST merge into the consumer's `.specify/extensions.yml`. Under one-active-per-repo, there is no cross-atom merge; the only merge dimension is atom-first + local-last precedence per stage for hooks, atom-declared vs locally-declared requirements for extensions. A local hook entry with the same `(stage, extension, command, script)` identity as an atom-contributed entry REPLACES the atom entry (operator override), otherwise both survive with the atom entry ordered before the local entry. Conflicting non-constraint metadata for the same extension id (e.g. different `homepage` values across the atom's own required/optional lists) MUST refuse before publication with `key=conflicting-extension-metadata`. Unparseable version-constraint syntax MUST refuse with `key=invalid-constraint`. Same extension id declared twice within `required_extensions[]` or twice within `optional_extensions[]` MUST refuse with `key=workflow-atom-extension-id-collision`. The resulting `.specify/extensions.yml` is regenerated from scratch on every install; no persisted provenance cache is kept.
- **FR-006** (Multi-workflow refusal): `haex install` MUST refuse when the resolved atom set contains two or more atoms whose manifests declare `contributes.speckit_workflow`. Refusal uses `key=multiple-workflow-atoms-refused` and exits with `INPUT_REFUSE`; stderr names all offending atom ids and their sources. Zero files under `.specify/workflows/`, `.specify/extensions/workflow-atoms/`, `.specify/extensions.yml`, or `.haex-hive/` are written.
- **FR-007** (Required-extensions gate): Before any file publication, `haex install` MUST validate that every `required_extensions[]` entry declared by the adopted workflow atom resolves to an installed extension under the direct-child path `.specify/extensions/<extension-id>/`, never under the reserved `.specify/extensions/workflow-atoms/` namespace, whose authoritative version is the `version` field in that extension's `extension.yml`. A missing extension MUST refuse with `key=required-workflow-extension-missing`; an installed extension whose version fails the atom's declared constraint MUST refuse with `key=required-workflow-extension-incompatible`. Both refusal cases exit non-zero and name the extension id and constraint or versions on stderr. Optional-extension misses MUST NOT refuse but MUST emit a stderr warning. Constraint parsing MUST use Spec 007's `VersionConstraint` grammar; unsupported syntax refuses with `key=invalid-constraint`.
- **FR-008** (Reader resolution): A reader (an agent, an editor extension, a validator) determines which workflow is binding by inspecting `.haex-hive.json`'s adopted atoms. If exactly one atom's manifest carries `contributes.speckit_workflow`, that atom's published `workflow.yml` at `.specify/workflows/<atom-id>/workflow.yml` is binding. If none do, the bundled `.specify/workflows/speckit/workflow.yml` is binding. There is no separate selector file to consult. The reader helper's return value carries a `source` field (`atom` or `bundled`) for diagnostic display.
- **FR-009** (Delete-orphans on removal): When the operator removes the workflow atom from `.haex-hive.json` and re-runs `haex install`, the transaction MUST delete the corresponding `.specify/workflows/<atom-id>/` directory, the matching `.specify/extensions/workflow-atoms/<atom-id>/` hook directory, the atom's requirement and hook entries from `.specify/extensions.yml`, and the atom's constitution fragment from `.haex-hive/constitution.md`, all atomically as part of the R1 rename-swap generation. Unrelated atoms, community-extension files under sibling direct-child paths, and local `.specify/extensions.yml` entries survive verbatim. There is no registry file to update.
- **FR-010** (Concealment guard for workflow-contributed constitution fragment): The Principle VIII safety validator (`validate_no_concealment_instructions`) MUST run against the adopted workflow atom's `constitution.md` fragment as part of the merged constitution acceptance. Concealment instructions in the fragment refuse the install identically to concealment instructions in any other constitution fragment.

### Key Entities

- **Workflow atom**: a Spec-007 atom whose `contributes` map includes `speckit_workflow: <path>` and optionally `constitution`, `speckit_extensions`, and `speckit_hooks`.
- **Adopted workflow**: at most one per consumer project. Selection is implicit from `.haex-hive.json` adoption; if none adopts a workflow atom, the bundled `speckit` workflow is the default.
- **Workflow-contributed rules section**: a `## Workflow-Contributed Rules` section in `.haex-hive/constitution.md` where the merger appends the adopted workflow atom's constitution fragment under a `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` byline.
- **Extensions-fragment merge**: the deterministic combination of the adopted atom's `required_extensions[]`, `optional_extensions[]`, and hook entries with the consumer's local `.specify/extensions.yml`, per atom-first + local-last precedence with local replace-by-identity for hooks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adopting exactly one `speckit-workflow` atom via `.haex-hive.json` and running `haex install` publishes `.specify/workflows/<atom-id>/workflow.yml` byte-for-byte matching the atom's contribution. Verified by a file-hash comparison in the US1 integration test.
- **SC-002**: The adopted workflow atom's `constitution.md` fragment appears verbatim under a `### From atom \`<atom-id>\` (revision \`<short-sha>\`)` byline inside a shared `## Workflow-Contributed Rules` section in the assembled `.haex-hive/constitution.md` after `haex install --accept-merged`. Verified by a subsection-content check in the US1 integration test.
- **SC-003**: When a workflow atom is adopted, the reader helper resolves to the atom's `workflow.yml` and returns `source=atom`; when no workflow atom is adopted, it resolves to the bundled `.specify/workflows/speckit/workflow.yml` and returns `source=bundled`. Verified by unit tests over both cases.
- **SC-004**: Removing the workflow atom from `.haex-hive.json` and re-running `haex install` removes `.specify/workflows/<atom-id>/`, `.specify/extensions/workflow-atoms/<atom-id>/`, the atom's entries from `.specify/extensions.yml`, and the atom's constitution fragment from `.haex-hive/constitution.md`. Verified by a US3 downgrade integration test.
- **SC-005**: A workflow atom whose required extension is missing, whose installed extension fails its constraint, or whose fragment uses an unparseable constraint MUST cause `haex install` to exit non-zero with the documented diagnostic key and zero file publications. Verified by a US2 refusal integration test.
- **SC-006**: A `.haex-hive.json` adopting two or more `speckit-workflow` atoms MUST cause `haex install` to exit non-zero with `key=multiple-workflow-atoms-refused` and zero file publications. Verified by a US4 refusal integration test.

## Assumptions

- **One workflow atom active per repository** (amendment 2026-09-02): a workflow is a whole; two workflows cannot be binding at once. Adopting two `speckit-workflow` atoms refuses at install time.
- **Trust-git for our own bytes and trust `extension.yml` for third-party extensions** (amendment 2026-09-02): SHA-pinned atoms guarantee our own content byte-identity; specifyr's installed `extension.yml` is authoritative for a third-party extension's version. haex-hive does not cross-check specifyr's `.registry` for internal consistency.
- **No persisted provenance**: `.specify/extensions.yml` is regenerated on every install from the currently-adopted workflow atom's fragment plus local declarations. No cache, no `extension_contributions` field.
- **Constitution-fragment merge machinery is reused**: the multi-source merge from Spec 007 / Spec 008 handles the workflow atom's fragment identically to any other constitution atom. This spec adds the `## Workflow-Contributed Rules` section header convention on top; it does not introduce a new merge algorithm.
- **Automatic extension installation is out of scope**: `haex install` refuses when a workflow atom's `required_extensions[]` are missing or version-incompatible; it does NOT install them. Extension installation is a specifyr concern.
- **Runtime enforcement is out of scope**: the constitution's Declared speckit workflow adherence clause remains advisory-to-the-agent. A mechanical pre-commit hook or CI gate is deferred to a Phase-7 successor spec per constitution §Governance.
- **Pre-user policy applies**: no external adopters of haex-hive exist as of 2026-09-02. Retiring `workflow-registry.json` / `active_workflow` / `extension_contributions` from the merged spec 011 requires no migration path.

## Dependencies

- **Spec 007 (Unified Manifest v2)**: baseline atom-manifest schema, `ConsumerManifest`, `VersionConstraint`. FR-001 adds three new `contributes.*` fields.
- **Spec 008 (Install Transaction)**: landed. FR-002, FR-003, FR-004, FR-005, FR-009 rely on the rename-swap primitive, the multi-source constitution merge, and Spec 008 US4 delete-orphans semantics.
- **Constitution v1.4.0**: § Development Workflow → Declared speckit workflow adherence bullet resolves at read time via FR-008. Once Spec 011 lands, a PATCH-level constitution amendment MAY retire the "planned Spec 011" forward-reference in that bullet.
- **specifyr's extension-install mechanism** (external): `required_extensions[]` names extensions specifyr (or an equivalent) installs. `extension.yml` is the file specifyr places at `.specify/extensions/<id>/extension.yml`; haex-hive reads its `version` field as authoritative.
