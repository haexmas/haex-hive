# Feature Specification: Speckit workflow molecule

**Feature Branch**: `011-simplify-workflow-molecule` (rewrite of the previously-merged spec on the same slot)
**Created**: 2026-09-02 (original), 2026-09-02 (simplified re-specification)
**Status**: Draft (simplification amendment)
**Input**: User description: "haex-hive gains a workflow molecule whose v3 manifest delivers workflow, constitution, extension, and hook files through its `atoms` category map; a project adopts it via `.haex-hive.json.compounds[]` pinned to a specific revision; on `haex install` the files publish under `.specify/workflows/<molecule-id>/`, the constitution fragment merges into `.haex-hive/constitution.md` via the existing multi-source flow, and the adopted workflow molecule becomes automatically binding."

**Authoritative requirements source**: [docs/plans/2026-09-02-spec-011-speckit-workflow-atom-design.md](../../docs/plans/2026-09-02-spec-011-speckit-workflow-atom-design.md) for requirements preserved by this amendment. This amendment supersedes conflicting passages in that design document, specifically all requirements for `workflow-registry.json`, `active_workflow`, `extension_contributions` provenance, and workflow coexistence; FR-005 below is authoritative for local extension ownership and regeneration.

## 2026-09-02 amendment: simplified model

The originally-merged spec 011 (PRs #51 spec + #52 plan + #53 tasks) introduced a `workflow-registry.json` file with an `active_workflow` selector, an `extension_contributions` provenance cache, a `.registry` cross-check with `installed-extension-metadata-mismatch` diagnostic, and bytewise-UTF-8 molecule-id ordering rules for multi-atom merges. An operator review on the same day identified all four as over-engineering that two simplifications obviate:

1. **One workflow molecule active per repository** (no coexistence). A workflow is a whole (specify -> plan -> tasks -> implement + review gates + hooks), not a slice to be blended with another workflow. A project either follows one full workflow or the bundled default. Multi-workflow slicing per branch or role is out of scope.
2. **Trust-git for our content; trust the extension-installer's own metadata for third-party extensions.** SHA-pinned atoms guarantee our own bytes; specifyr's installed `extension.yml` is authoritative for a third-party extension's version. haex-hive does not second-check specifyr's `.registry` file for internal consistency.

**Retired from the merged spec 011**:

- **FR-006 (workflow registry)** retired. No `.specify/workflows/workflow-registry.json` file. No `active_workflow` field. No workflow catalogue. Adoption alone determines binding.
- **FR-008 (reader resolution)** simplified: the reader inspects `.haex-hive.json.compounds[]` for a molecule with a non-empty `atoms.workflow` list; found -> that workflow is binding; absent -> the bundled `.specify/workflows/speckit/workflow.yml` is binding. No registry lookup.
- **US4 (coexistence)** retired. Under one-active-per-repo the scenario cannot exist.
- **Bytewise UTF-8 molecule-id ordering** retired. With one workflow molecule max, no cross-atom order ambiguity exists.
- **`extension_contributions` provenance cache** retired. `.specify/extensions.yml` regenerates from scratch on every install from the current adopted workflow molecule's fragment plus local declarations.
- **`installed-extension-metadata-mismatch` diagnostic key** retired.
- **`.registry` cross-check against `extension.yml`** retired.
- **`workflow-molecule-reset-to-default` diagnostic key** retired (no active_workflow to reset).

**Added by this amendment**:

- **New FR (fills FR-006 slot)**: `haex install` MUST refuse when `.haex-hive.json.compounds[]` adopts two or more molecules whose manifest carries a non-empty `atoms.workflow` list. Refusal is `key=multiple-workflow-molecules-refused`, exit code reuses `INPUT_REFUSE`.

Everything else the merged spec 011 required (molecule-manifest v3 field shape and path containment, publication targets, hook publication and namespace collisions, constitution-fragment merge, extensions-fragment merge with required/optional constraints, required-extension install-time gate, delete-orphans on removal, concealment guard) survives unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Adopt a workflow molecule and it becomes binding (Priority: P1) MVP

An operator wants their project to follow a specific speckit workflow (a stricter TDD variant, a bugfix-first flow) instead of the bundled `Full SDD Cycle`. They add one workflow molecule to `.haex-hive.json.compounds[]` pinned by full 40-char SHA and run `haex install`. On success, the molecule's `workflow.yml` publishes under `.specify/workflows/<molecule-id>/`, its constitution fragment merges into `.haex-hive/constitution.md` under a `## Workflow-Contributed Rules` section, and the workflow is automatically binding. No selector step, no registry edit.

**Why this priority**: This is the MVP. Without a working adopt-and-bind path, no other user story matters.

**Independent Test**: On a fresh consumer checkout with one workflow molecule in `.haex-hive.json.compounds[]`, run `haex install --llm=file` + `--accept-merged <candidate>` end-to-end. Assert (a) `.specify/workflows/<molecule-id>/workflow.yml` is byte-identical to the molecule's contribution; (b) hook scripts publish under `.specify/extensions/workflow-molecules/<molecule-id>/`; (c) `.haex-hive/constitution.md` contains a `## Workflow-Contributed Rules` section with the molecule's fragment under a `### From molecule \`<molecule-id>\` (revision \`<short-sha>\`)` byline; (d) reader helper called against the consumer returns the molecule-workflow's path (not the bundled path).

**Acceptance Scenarios**:

1. **Given** a consumer `.haex-hive.json` with one compound adopting exactly one workflow molecule at a pinned SHA reachable under `$HAEX_HIVE_STATE/repos/`, **When** the operator runs `haex install`, **Then** the molecule's `atoms.workflow` file publishes at `.specify/workflows/<molecule-id>/workflow.yml`, its hook files publish under `.specify/extensions/workflow-molecules/<molecule-id>/`, the constitution fragment merges into the shared `## Workflow-Contributed Rules` section under a `### From molecule \`<molecule-id>\` (revision \`<short-sha>\`)` byline, `.specify/extensions.yml` gains the molecule's required/optional extensions and hook wiring, and `install.lock.molecules[]` records `(id, source, revision, contributed_paths)` for the molecule.
2. **Given** a workflow molecule whose `atoms.workflow[]` or any `atoms.hooks[]` source path escapes the molecule root (absolute, backslash-qualified, `.`/`..` traversal, symlink escape), **When** `haex install` resolves the molecule, **Then** the install refuses before any file publication with a diagnostic naming the offending path and citing Principle II.
3. **Given** a workflow molecule declaring a hook whose script has no matching source file, maps to a non-regular source, is mapped twice, or maps outside the molecule's reserved `workflow-molecules/<molecule-id>/` namespace, **When** `haex install` validates the hook mapping, **Then** the install refuses before publication with `key=workflow-hook-mapping-invalid` naming the source and destination paths on stderr.
4. **Given** a community extension with the id `workflow-molecules` is already installed at the direct-child path `.specify/extensions/workflow-molecules/`, which is reserved for molecule-owned workflow hooks, **When** `haex install` validates the publication targets, **Then** the install refuses before publication with `key=workflow-molecule-extension-id-collision` naming `.specify/extensions/workflow-molecules/` as the colliding path.

### User Story 2 - Required-extension validator refuses missing or incompatible extensions (Priority: P2)

An operator adopts a workflow molecule whose `required_extensions` names a speckit-community extension that is either absent under `.specify/extensions/` or installed at a version outside the molecule's declared constraint. `haex install` MUST refuse before any file publication with a clear operator-facing diagnostic.

**Why this priority**: Without this refusal, the workflow silently binds while the tooling it depends on is missing; every downstream `/speckit-<step>` invocation fails opaquely inside a spec-authoring session. Install-time refusal beats runtime failure.

**Independent Test**: Adopt a workflow molecule declaring `required_extensions: [{id: v-model-extension-pack, version_constraint: ">=0.7.2"}]` while ensuring `.specify/extensions/v-model-extension-pack/` does NOT exist. Run `haex install`. Assert exit code non-zero, stderr contains `key=required-workflow-extension-missing`, and no files under `.specify/workflows/` or `.haex-hive/` were written.

**Acceptance Scenarios**:

1. **Given** a workflow molecule declaring a required extension that is not installed locally, **When** `haex install` runs, **Then** it refuses with `key=required-workflow-extension-missing` before any file publication and stderr names the missing extension id and version constraint.
2. **Given** a workflow molecule declaring `required_extensions: [{id: bugfix-workflow, version_constraint: "1.0.0"}]` and a locally installed `bugfix-workflow` whose `extension.yml` records version `2.0.0`, **When** `haex install` runs, **Then** it refuses with `key=required-workflow-extension-incompatible` and stderr names the found and expected versions.
3. **Given** a workflow molecule whose `optional_extensions` names a missing extension, **When** `haex install` runs, **Then** the install proceeds successfully and the missing optional extension surfaces only as a stderr warning.
4. **Given** a workflow molecule's fragment that declares the same extension id twice within `required_extensions[]`, **When** `haex install` loads the fragment, **Then** it refuses with `key=workflow-molecule-extension-id-collision`.
5. **Given** a workflow molecule whose extension declaration uses an unparseable version-constraint syntax (unsupported grammar), **When** `haex install` parses the fragment, **Then** it refuses with `key=invalid-constraint` naming the offending value.
6. **Given** a workflow molecule whose fragment declares the same extension id with contradictory `homepage` metadata values across `required_extensions` and `optional_extensions`, **When** `haex install` validates the fragment, **Then** it refuses with `key=conflicting-extension-metadata` naming the extension id and both values.

### User Story 3 - Downgrade path removes the workflow molecule's artifacts (Priority: P2)

An operator decides they no longer want the molecule-adopted workflow. They remove the molecule entry from `.haex-hive.json` and run `haex install`. The molecule's previously-published files disappear, its constitution fragment stops appearing in the merged output, and the bundled workflow becomes binding again by virtue of no atom claiming that role.

**Why this priority**: Removal must be a first-class operation, not a manual `rm -rf`. Under Spec 008 US4 (delete-orphans), removing a molecule from `.haex-hive.json` automatically clears its contributions.

**Independent Test**: Start from US1 endpoint (workflow molecule adopted). Remove the molecule entry from `.haex-hive.json`. Run `haex install`. Assert (a) `.specify/workflows/<molecule-id>/` is absent; (b) `.specify/extensions/workflow-molecules/<molecule-id>/` is absent; (c) the molecule's `## Workflow-Contributed Rules` subsection no longer appears in `.haex-hive/constitution.md`; (d) `.specify/extensions.yml` no longer contains the molecule's requirements or hook entries; (e) the reader helper returns the bundled `.specify/workflows/speckit/workflow.yml` path.

**Acceptance Scenarios**:

1. **Given** a consumer with a previously-adopted workflow molecule, **When** the operator removes the molecule from `.haex-hive.json` and runs `haex install`, **Then** the molecule's `.specify/workflows/<molecule-id>/` directory, its `.specify/extensions/workflow-molecules/<molecule-id>/` hook scripts, and its constitution fragment are removed atomically as part of the R1 rename-swap generation; unrelated atoms and local declarations survive verbatim.
2. **Given** an in-flight install that crashed mid-swap during a downgrade, **When** the operator retries `haex install`, **Then** Spec 008's detect-and-retry recovery converges to the fully-downgraded state on the retry; the removed molecule's files are absent afterward.

### User Story 4 - Refuse multiple workflow-molecule adoptions (Priority: P2)

An operator accidentally adopts two `speckit-workflow` atoms in the same `.haex-hive.json`. Because the workflow is a whole (steps + review gates + hook wiring), two workflows cannot both be binding at the same time. `haex install` MUST refuse before any file publication with a clear diagnostic naming both atoms.

**Why this priority**: Without this refusal, the second-adopted molecule would silently shadow or clobber the first (depending on merge order), producing a project that follows some blend the operator never approved.

**Independent Test**: Author a consumer `.haex-hive.json` adopting two molecules whose manifests both carry non-empty `atoms.workflow` lists. Run `haex install`. Assert exit code non-zero, stderr contains `key=multiple-workflow-molecules-refused` and names both molecule ids, and no files under `.specify/workflows/` or `.haex-hive/` were written.

**Acceptance Scenarios**:

1. **Given** a consumer `.haex-hive.json` adopting two workflow molecules simultaneously, **When** `haex install` resolves the molecules, **Then** it refuses with `key=multiple-workflow-molecules-refused`, names both molecule ids and their sources on stderr, and no files are written under `.specify/workflows/` or `.haex-hive/`.
2. **Given** a consumer transitioning from workflow molecule A to workflow molecule B, **When** the operator sequences the change as two commits (remove A then add B) and runs `haex install` after each, **Then** each individual `haex install` sees exactly one workflow molecule and succeeds; the intermediate state after removing A but before adding B leaves the bundled workflow binding, matching US3's semantics.

### Edge Cases

- **Molecule carries `atoms.extensions` or `atoms.hooks` without `atoms.workflow`**: refused before staging. A molecule declaring extension or hook wiring is only meaningful under a workflow molecule.
- **Molecule carries `atoms.workflow` but no constitution fragment**: valid. The molecule binds a workflow without imposing constitution rules; only the workflow and any hooks land.
- **Adopted workflow molecule's `constitution.md` fragment contains concealment instructions**: refused by the existing Principle VIII validator during the multi-source merge, identical to any other constitution fragment.
- **Adopted workflow molecule's fragment declares an extension id under both `required_extensions[]` and `optional_extensions[]`**: the required declaration wins for install-time refusal purposes; if the required and optional version constraints on the same id are compatible, the optional entry is retained; if incompatible, the optional entry is dropped and stderr emits `key=optional-workflow-extension-conflict` as a warning.
- **Empty adopted-atoms set (no workflow molecule at all)**: the bundled `.specify/workflows/speckit/workflow.yml` is binding by fallback; `haex install` publishes it as today.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (workflow molecule shape): the v3 molecule manifest MUST deliver workflow, constitution, extension, and hook atoms through `atoms.workflow[]`, `atoms.constitution[]`, `atoms.extensions[]`, and `atoms.hooks[]`. Workflow and extensions/hook atoms require a non-empty workflow category. Every declared source path MUST pass `RepoRelativePath.validate` and a canonical containment check against the molecule root at load time; every published destination MUST remain under its consumer-owned target. Absolute paths, backslash- or drive-qualified paths, `.`/`..` traversal, and symlink or reparse-point targets that escape either root MUST refuse before publication with a Principle II citation.
- **FR-002** (Publication location): When exactly one workflow molecule is adopted, `haex install` MUST publish its `workflow.yml` to `.specify/workflows/<molecule-id>/workflow.yml` where `<molecule-id>` is the molecule's reverse-DNS id. The bundled `.specify/workflows/speckit/workflow.yml` remains untouched by molecule adoption. There is no registry file to update.
- **FR-003** (Hook scripts and namespace): When the workflow molecule declares `atoms.hooks`, `haex install` MUST copy every listed hook file to `.specify/extensions/workflow-molecules/<molecule-id>/` with the same relative structure. `workflow-molecules/` is a reserved molecule-owned namespace under `.specify/extensions/`; community extensions occupy sibling direct-child paths. Before publication, the installer MUST refuse with `key=workflow-hook-mapping-invalid` for any hook whose declared destination has no matching source file, whose source is not a regular file, whose destination escapes the molecule-owned directory, or which is declared more than once within the fragment. The installer MUST refuse with `key=workflow-molecule-extension-id-collision` if the reserved namespace is occupied by a direct-child community extension or if a molecule-owned destination would overwrite a community-extension file. Hook cleanup on downgrade MUST touch only paths under the matching molecule-owned directory.
- **FR-004** (Constitution fragment merge): When the adopted workflow molecule declares `atoms.constitution`, its fragment MUST participate in the existing multi-source constitution merge. The merged output MUST contain one `## Workflow-Contributed Rules` section; the fragment is appended under a `### From molecule \`<molecule-id>\` (revision \`<short-sha>\`)` byline. The merge MUST retain the review-gated two-phase flow (`haex install --llm=file` / `--accept-merged`) per Principle VI. When no workflow molecule contributes a fragment, the `## Workflow-Contributed Rules` section is omitted.
- **FR-005** (Extensions fragment merge): When the adopted workflow molecule declares `atoms.extensions`, its `required_extensions[]`, `optional_extensions[]`, and any `hooks.<stage>[]` entries MUST merge into the generated consumer file `.specify/extensions.yml`. Consumer-local declarations MUST come from the separate, consumer-owned `.specify/extensions.local.yml`; that file is the authoritative local source, is never generated, deleted, or modified by `haex install`, and uses the same `installed`, `settings`, `required_extensions`, `optional_extensions`, and `hooks` keys. A missing local source denotes an empty local declaration set; a consumer with existing local declarations MUST place them in this source before adopting a workflow molecule. The generated `.specify/extensions.yml` MUST be rebuilt on every install from only the current workflow molecule fragment plus that local source, so removed or downgraded molecule entries cannot survive as stale output. The local source remains byte-for-byte unchanged; in the generated output, non-conflicting local values and their relative list order are preserved, subject to the molecule-first ordering and canonical ordering rules below. Under one-active-per-repo, molecule entries are processed before local entries. Requirement entries are merged by extension ID with no source taking precedence: compatible constraints use the existing exact/lower-bound intersection rules; required status wins over optional status; an incompatible optional declaration is omitted with `key=optional-workflow-extension-conflict`; incompatible required declarations refuse with `key=conflicting-constraint`; and conflicting non-constraint metadata for the same extension ID refuses before publication with `key=conflicting-extension-metadata`. A local hook entry with the same `(stage, extension, command, normalized script_path)` identity as a molecule-contributed entry REPLACES the molecule entry in its position and its local values are authoritative; otherwise both survive, with molecule entries ordered before local entries and remaining local entries retaining their relative order. Duplicate identities within the molecule fragment or within the local source refuse with `key=workflow-hook-mapping-invalid`. Unparseable version-constraint syntax MUST refuse with `key=invalid-constraint`. Same extension ID declared twice within `required_extensions[]` or twice within `optional_extensions[]` MUST refuse with `key=workflow-molecule-extension-id-collision`. No persisted provenance cache is kept. Molecule-to-molecule conflicts are out of scope because only one workflow molecule may be adopted; the merge contract covers the adopted molecule versus the consumer-local source.
- **FR-006** (Multi-workflow refusal): `haex install` MUST refuse when the resolved molecule set contains two or more molecules whose manifests declare a non-empty `atoms.workflow` list. Refusal uses `key=multiple-workflow-molecules-refused` and exits with `INPUT_REFUSE`; stderr names all offending molecule ids and their sources. Zero files under `.specify/workflows/`, `.specify/extensions/workflow-molecules/`, `.specify/extensions.yml`, or `.haex-hive/` are written.
- **FR-007** (Required-extensions gate): Before any file publication, `haex install` MUST validate that every `required_extensions[]` entry declared by the adopted workflow molecule resolves to an installed extension under the direct-child path `.specify/extensions/<extension-id>/`, never under the reserved `.specify/extensions/workflow-molecules/` namespace, whose authoritative version is the `version` field in that extension's `extension.yml`. A missing extension MUST refuse with `key=required-workflow-extension-missing`; an installed extension whose version fails the molecule's declared constraint MUST refuse with `key=required-workflow-extension-incompatible`. Both refusal cases exit non-zero and name the extension id and constraint or versions on stderr. Optional-extension misses MUST NOT refuse but MUST emit a stderr warning. Constraint parsing MUST use Spec 007's `VersionConstraint` grammar; unsupported syntax refuses with `key=invalid-constraint`.
- **FR-008** (Reader resolution): A reader (an agent, an editor extension, a validator) determines which workflow is binding by inspecting `.haex-hive.json`'s adopted compounds. If exactly one molecule's manifest carries a non-empty `atoms.workflow` list, that molecule's published `workflow.yml` at `.specify/workflows/<molecule-id>/workflow.yml` is binding. If none do, the bundled `.specify/workflows/speckit/workflow.yml` is binding. There is no separate selector file to consult. The reader helper's return value carries a `source` field (`molecule` or `bundled`) for diagnostic display.
- **FR-009** (Delete-orphans on removal): When the operator removes the workflow molecule from `.haex-hive.json` and re-runs `haex install`, the transaction MUST delete the corresponding `.specify/workflows/<molecule-id>/` directory, the matching `.specify/extensions/workflow-molecules/<molecule-id>/` hook directory, the molecule's requirement and hook entries from the generated `.specify/extensions.yml`, and the molecule's constitution fragment from `.haex-hive/constitution.md`, all atomically as part of the R1 rename-swap generation. Unrelated atoms, community-extension files under sibling direct-child paths, and the consumer-owned `.specify/extensions.local.yml` survive verbatim. There is no registry file to update.
- **FR-010** (Concealment guard for workflow-contributed constitution fragment): The Principle VIII safety validator (`validate_no_concealment_instructions`) MUST run against the adopted workflow molecule's `constitution.md` fragment as part of the merged constitution acceptance. Concealment instructions in the fragment refuse the install identically to concealment instructions in any other constitution fragment.

### Key Entities

- **workflow molecule**: a Spec-007 molecule whose `atoms` map includes a non-empty `workflow` list and optionally `constitution`, `extensions`, and `hooks` lists.
- **Adopted workflow**: at most one per consumer project. Selection is implicit from `.haex-hive.json` adoption; if none adopts a workflow molecule, the bundled `speckit` workflow is the default.
- **Workflow-contributed rules section**: a `## Workflow-Contributed Rules` section in `.haex-hive/constitution.md` where the merger appends the adopted workflow molecule's constitution fragment under a `### From molecule \`<molecule-id>\` (revision \`<short-sha>\`)` byline.
- **Local extension source**: the consumer-owned `.specify/extensions.local.yml` file containing declarations that must survive workflow-molecule changes; it is distinct from generated `.specify/extensions.yml`.
- **Extensions-fragment merge**: the deterministic combination of the adopted molecule's `required_extensions[]`, `optional_extensions[]`, and hook entries with the consumer-owned `.specify/extensions.local.yml`, producing generated `.specify/extensions.yml` with molecule-first + local-last precedence and local replace-by-identity for hooks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adopting exactly one `speckit-workflow` atom via `.haex-hive.json` and running `haex install` publishes `.specify/workflows/<molecule-id>/workflow.yml` byte-for-byte matching the molecule's contribution. Verified by a file-hash comparison in the US1 integration test.
- **SC-002**: The adopted workflow molecule's `constitution.md` fragment appears verbatim under a `### From atom \`<molecule-id>\` (revision \`<short-sha>\`)` byline inside a shared `## Workflow-Contributed Rules` section in the assembled `.haex-hive/constitution.md` after `haex install --accept-merged`. Verified by a subsection-content check in the US1 integration test.
- **SC-003**: When a workflow molecule is adopted, the reader helper resolves to the molecule's `workflow.yml` and returns `source=atom`; when no workflow molecule is adopted, it resolves to the bundled `.specify/workflows/speckit/workflow.yml` and returns `source=bundled`. Verified by unit tests over both cases.
- **SC-004**: Removing the workflow molecule from `.haex-hive.json` and re-running `haex install` removes `.specify/workflows/<molecule-id>/`, `.specify/extensions/workflow-molecules/<molecule-id>/`, the molecule's entries from `.specify/extensions.yml`, and the molecule's constitution fragment from `.haex-hive/constitution.md`. Verified by a US3 downgrade integration test.
- **SC-005**: A workflow molecule whose required extension is missing, whose installed extension fails its constraint, or whose fragment uses an unparseable constraint MUST cause `haex install` to exit non-zero with the documented diagnostic key and zero file publications. Verified by a US2 refusal integration test.
- **SC-006**: A `.haex-hive.json` adopting two or more `speckit-workflow` atoms MUST cause `haex install` to exit non-zero with `key=multiple-workflow-molecules-refused` and zero file publications. Verified by a US4 refusal integration test.

## Assumptions

- **One workflow molecule active per repository** (amendment 2026-09-02): a workflow is a whole; two workflows cannot be binding at once. Adopting two `speckit-workflow` atoms refuses at install time.
- **Trust-git for our own bytes and trust `extension.yml` for third-party extensions** (amendment 2026-09-02): SHA-pinned atoms guarantee our own content byte-identity; specifyr's installed `extension.yml` is authoritative for a third-party extension's version. haex-hive does not cross-check specifyr's `.registry` for internal consistency.
- **No persisted provenance**: `.specify/extensions.yml` is regenerated on every install from the currently-adopted workflow molecule's fragment plus `.specify/extensions.local.yml`. The local file is the ownership boundary and remains untouched; the generated file is never used as input. No cache, no `extension_contributions` field.
- **Constitution-fragment merge machinery is reused**: the multi-source merge from Spec 007 / Spec 008 handles the workflow molecule's fragment identically to any other constitution fragment. This spec adds the `## Workflow-Contributed Rules` section header convention on top; it does not introduce a new merge algorithm.
- **Automatic extension installation is out of scope**: `haex install` refuses when a workflow molecule's `required_extensions[]` are missing or version-incompatible; it does NOT install them. Extension installation is a specifyr concern.
- **Runtime enforcement is out of scope**: the constitution's Declared speckit workflow adherence clause remains advisory-to-the-agent. A mechanical pre-commit hook or CI gate is deferred to a Phase-7 successor spec per constitution §Governance.
- **Pre-user policy applies**: no external adopters of haex-hive exist as of 2026-09-02. Retiring `workflow-registry.json` / `active_workflow` / `extension_contributions` from the merged spec 011 requires no migration path.

## Dependencies

- **Spec 007 (Unified Manifest v2)**: baseline atom-manifest schema, `ConsumerManifest`, `VersionConstraint`. FR-001 adds three new `contributes.*` fields.
- **Spec 008 (Install Transaction)**: landed. FR-002, FR-003, FR-004, FR-005, FR-009 rely on the rename-swap primitive, the multi-source constitution merge, and Spec 008 US4 delete-orphans semantics.
- **Constitution v1.4.0**: § Development Workflow → Declared speckit workflow adherence bullet resolves at read time via FR-008. Once Spec 011 lands, a PATCH-level constitution amendment MAY retire the "planned Spec 011" forward-reference in that bullet.
- **specifyr's extension-install mechanism** (external): `required_extensions[]` names extensions specifyr (or an equivalent) installs. `extension.yml` is the file specifyr places at `.specify/extensions/<id>/extension.yml`; haex-hive reads its `version` field as authoritative.
