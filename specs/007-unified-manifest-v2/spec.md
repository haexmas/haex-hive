# Feature Specification: Unified Manifest v3 (Molecule + Kind + Delivers)

**Feature Branch**: `007-molecule-manifest` (v3 amendment on top of the merged v2 spec)
**Created**: 2026-08-29 (v2 original), 2026-09-03 (v3 amendment)
**Status**: Draft (simplification and rename amendment)
**Input**: User description: "Spec 007 - Unified Manifest v2 + Migration + Constitution Assemble. Deliver the CLI-level surface for the .haex-hive.json v2 schema, the publisher-side root and per-atom manifest.json schemas, the review-gated `haex migrate` command, the `haex constitution assemble` and `haex constitution show` commands, and the root+atom manifests for this repo itself so haex-hive becomes its own first publisher."

**Design source of truth**: [docs/plans/2026-08-28-spec-007-unified-manifest-design.md](../../docs/plans/2026-08-28-spec-007-unified-manifest-design.md) (17 decisions D1..D17, migration path v1→v2 table). This spec inherits the still-valid D-decisions from the design doc; the retirements and additions this amendment introduces supersede any conflicting passages there.

## 2026-09-03 amendment: Molecule Manifest v3 (rename + kind + delivers)

Two operator-driven realisations motivated a substantial simplification and rename of the Spec 007 v2 model:

1. **Wrong noun**: what Spec 007 v2 called an "atom" is structurally a **molecule**: a directory containing a manifest plus multiple bonded artifacts. The **individual delivered files** (a `workflow.yml`, a `constitution.md`, a single hook script, a single skill markdown) are the atoms in the chemistry metaphor. Under this reframe:
   - **Molecule** (formerly "atom"): the packaging unit. Directory + `manifest.json` + delivered files.
   - **Atom** (new formal term): a single delivered artifact inside a molecule.
   - **Assembly** (formerly "molecule" in the Spec 010 preview's prose-only sense): a composition of Molecules across publishers (for example, an operator's personal harness bundling multiple publisher molecules).
2. **Single-file-per-kind is too restrictive**: Spec 007 v2's `contributes.<kind>: <path>` grammar (scalar path per kind) does not model a molecule shipping two constitution fragments, three skills, or four hooks. Real-world publishers will ship multi-artifact molecules.

**Retired from Spec 007 v2**:

- **"Atom" as the packaging-unit term**: renamed to **Molecule** throughout the runtime, schemas, docs, ADRs, and constitution.
- **`contributes.<kind>: <path>`** mechanism: retired. Replaced by `kind` + `delivers` on the molecule manifest (see FR-001, FR-002).
- **"Molecule" as the Spec 010 preview's prose-only bundle-of-atoms concept**: retired. The new term for a composition of Molecules is **Assembly**.
- **`.haex-hive.json.atoms[]`**: renamed to `.haex-hive.json.molecules[]`. Consumer manifests migrate; under pre-user policy no compat shim.
- **`atom-manifest.v2.schema.json`**: retired. Replaced by `molecule-manifest.v3.schema.json` (new file at the same schema/ directory).

**Added by this amendment**:

- **`kind` field** on the molecule manifest: required, string. Enum in v1: `constitution`, `speckit-workflow`, `skill`, `hook`, `mcp-server`. Enum is intentionally extensible: adding a new value is a downstream-spec responsibility (Spec 011 for `speckit-workflow`, future specs for `skill`, `hook`, `mcp-server`).
- **`delivers` field** on the molecule manifest: required, shape `dict[str, list[str]]`. Maps a category name (matching a `kind` semantic slot) to a list of repo-relative paths inside the molecule directory. Every declared path passes `RepoRelativePath.validate` and canonical containment against the molecule root at manifest-load time.
- **New consumer-side field**: `.haex-hive.json.molecules[]` (renamed from `atoms[]`); every entry keeps its existing shape `{ source, revision, includes[] }` with `revision` being the full 40-char SHA (Principle IV, unchanged).
- **New diagnostic keys** (reuse existing exit-code categories):
  - `molecule-manifest-schema-invalid` (`INPUT_REFUSE=2`)
  - `unknown-molecule-kind` (`INPUT_REFUSE=2`)
  - `delivers-path-escape` (`INPUT_REFUSE=2`)
  - `delivers-path-duplicate` (`INPUT_REFUSE=2`)
  - `delivers-category-overlap` (`INPUT_REFUSE=2`)
  - `delivers-cardinality-violation` (`INPUT_REFUSE=2`)
- **Rename sweep** across the codebase (see Assumptions for full scope): runtime symbols (`AtomManifest` → `MoleculeManifest`, `.atoms` field → `.molecules`), schemas, docs, ADRs, spec dirs, existing molecule migrations (haex-hive constitution + graphify).

**Preserved from Spec 007 v2**:

- The D1..D17 decisions from the design doc still hold, modulo the rename (they described the packaging-unit shape, which is still valid: only the noun changes).
- Reverse-DNS ids on molecules (formerly atoms).
- `.haex-hive.json` version discipline (`haex_hive_version: "2"`).
- Publisher-root manifest.json shape (lists molecules with their paths).
- Cross-repo reference discipline (Principle IV).
- Every existing molecule's committed content survives byte-identically; only its manifest.json fields change (contributes → kind + delivers).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publisher authors and consumer adopts a molecule under v3 (Priority: P1) MVP

A publisher authors a molecule directory containing `manifest.json` (declaring `kind` + `delivers` inside a publisher-root `manifest.json` that lists the molecule), a constitution fragment file, and any additional atoms per the kind's contract. A consumer adds the molecule to `.haex-hive.json.molecules[]` with a full 40-char SHA. Running `haex install` publishes every atom the molecule's `delivers` map names into its kind-specific publication targets. The rename atom→molecule surfaces in every diagnostic, log line, and file the operator interacts with.

**Why this priority**: This is the MVP. Without a working v3 publisher-and-consumer round-trip, no downstream spec (011, 012, future kinds) can use the new mechanism.

**Independent Test**: On a fresh publisher checkout, create a `constitution`-kind molecule at `test-constitution/` with `manifest.json` declaring `kind: constitution, delivers: { constitution: ["constitution.md"] }` and a `constitution.md` file. Register it in the publisher-root `manifest.json.molecules`. Clone into a state-root. On a consumer checkout, add `molecules: [{ source, revision, includes: ["<molecule-id>"] }]` to `.haex-hive.json`. Run `haex install`. Verify (a) publisher's molecule manifest validates against `molecule-manifest.v3.schema.json`; (b) consumer's `.haex-hive.json` validates against the updated consumer manifest schema; (c) `haex install` completes; (d) `.haex-hive/constitution.md` contains the delivered atom's content.

**Acceptance Scenarios**:

1. **Given** a publisher molecule with `kind: constitution` and `delivers: { constitution: ["constitution.md"] }` and a valid `constitution.md`, **When** a consumer adopts it and runs `haex install`, **Then** the atom's content appears in the assembled `.haex-hive/constitution.md` per Spec 008's multi-source merge, and `install.lock.molecules[]` records the molecule's `(id, source, revision, contributed_paths)`.
2. **Given** a publisher molecule with `kind: speckit-workflow` and multi-artifact `delivers` (workflow + 1 constitution fragment + 2 hooks + 3 skills), **When** the consumer adopts it, **Then** every atom named in `delivers` publishes into its kind-specific target (per Spec 011); cardinality-one categories (workflow) refuse if the list has 0 or 2+ entries.
3. **Given** a v2-style molecule manifest that still uses the retired `contributes` field, **When** `haex install` loads it, **Then** the install refuses with `key=molecule-manifest-schema-invalid` and stderr names the offending file and the retired field.

### User Story 2 - Delivers paths are safety-checked (Priority: P2)

A publisher accidentally or maliciously ships a molecule whose `delivers` map contains a path that escapes the molecule root (absolute, `.`/`..` traversal, symlink escape), duplicates a path across categories, or violates a kind's cardinality. `haex install` refuses before any file is published, naming the specific safety violation.

**Why this priority**: Path safety is a Principle II NON-NEGOTIABLE. Without pre-publication refusal, a malicious or careless publisher could clobber consumer files outside the molecule's owned publication targets.

**Independent Test**: Author test molecules that violate each invariant in turn; run `haex install` for each; assert non-zero exit with the correct diagnostic key and zero files published under any managed root.

**Acceptance Scenarios**:

1. **Given** a molecule whose `delivers.constitution` contains `"../evil.md"`, **When** `haex install` loads its manifest, **Then** the install refuses with `key=delivers-path-escape` and stderr names the path and cites Principle II. Zero files are published.
2. **Given** a molecule whose `delivers.hooks` list contains `"hooks/a.sh"` twice, **When** `haex install` loads its manifest, **Then** the install refuses with `key=delivers-path-duplicate` and stderr names the offending category and path.
3. **Given** a molecule whose `delivers.skills` and `delivers.hooks` both list `"shared/foo.sh"`, **When** `haex install` loads its manifest, **Then** the install refuses with `key=delivers-category-overlap` and stderr names the shared path and both categories.
4. **Given** a molecule with `kind: speckit-workflow` whose `delivers.workflow` list has zero entries (or two entries), **When** `haex install` loads its manifest, **Then** the install refuses with `key=delivers-cardinality-violation` and stderr names the kind, category, and expected cardinality.
5. **Given** a molecule with `kind: alien-frobber` (not in the enum), **When** `haex install` loads its manifest, **Then** the install refuses with `key=unknown-molecule-kind` and stderr names the offending kind and lists the known-kind enum.

### User Story 3 - Spec 011 workflow molecules work under v3 without bespoke fields (Priority: P2)

A workflow-atom author (Spec 011) declares `kind: speckit-workflow` and puts every delivered artifact (workflow.yml, constitution fragment, extensions fragment, hooks) into `delivers`. No bespoke `contributes.speckit_workflow` / `contributes.speckit_extensions` / `contributes.speckit_hooks` fields exist; the workflow-atom kind's discovery mechanism is the shared `kind` + `delivers`.

**Why this priority**: The bespoke fields in the previously-merged Spec 011 (PR #54) become obsolete under this v3 amendment. Spec 011 rebuilds on the v3 fundament, retiring three new `contributes.speckit_*` fields. This user story locks that expected simplification into the v3 contract.

**Independent Test**: Author a `speckit-workflow`-kind molecule with `delivers.workflow: ["workflow.yml"]`, `delivers.constitution: ["constitution.md"]`, `delivers.extensions: ["extensions.yml"]`, `delivers.hooks: ["hooks/pre.sh", "hooks/post.sh"]`. Adopt on a consumer. Assert the Spec 011 publication semantics apply verbatim (workflow.yml under `.specify/workflows/<molecule-id>/`, hooks under reserved namespace, etc.) with no bespoke fields consulted.

**Acceptance Scenarios**:

1. **Given** a `speckit-workflow`-kind molecule adopted per v3, **When** `haex install` publishes it (per Spec 011 semantics), **Then** every atom named in `delivers` publishes to the same target that Spec 011 v1 published to when using the retired `contributes.speckit_*` fields.
2. **Given** two adopted molecules both `kind: speckit-workflow` in a single `.haex-hive.json.molecules[]`, **When** `haex install` runs, **Then** it refuses per Spec 011 FR-006 (`key=multiple-workflow-atoms-refused`). This v3 amendment does not change Spec 011's per-kind uniqueness invariants; it only replaces the discovery mechanism.

### User Story 4 - Migration of existing molecules (Priority: P3)

The two haex-hive-self molecules (`com.github.haexmas.haex-hive.constitution`, `com.github.haexmas.haex-hive.graphify-first-authoring`) migrate their `manifest.json` from `contributes.constitution: "constitution.md"` to `kind: constitution, delivers: { constitution: ["constitution.md"] }`. Both molecule manifest versions bump MAJOR because the field schema is a breaking change.

**Why this priority**: haex-hive is its own first consumer. If self-adopt fails after landing this amendment, the whole system is unusable. This user story anchors the migration as part of the amendment landing, not as a follow-up.

**Independent Test**: On the haex-hive checkout at the amendment-landing commit, verify (a) `manifest.json` (publisher root) lists both molecules with correct paths; (b) both molecules' `manifest.json` files declare `kind: constitution` and `delivers: { constitution: ["constitution.md"] }`; (c) both molecule versions have MAJOR-bumped (e.g. constitution 1.4.1 → 2.0.0, graphify 0.1.0 → 1.0.0). Run `haex install` against a scratch consumer; assert both molecules resolve and publish.

**Acceptance Scenarios**:

1. **Given** the amendment-landing commit, **When** the operator inspects `.specify/memory/manifest.json`, **Then** it declares `kind: constitution` and `delivers: { constitution: ["constitution.md"] }`, and its `version` field is a MAJOR bump from 1.4.1.
2. **Given** the same commit's `.specify/atoms/graphify-first-authoring/manifest.json`, **When** the operator inspects it, **Then** it declares the same shape with graphify's atom-id and a MAJOR-bumped version from 0.1.0.
3. **Given** the amendment-landing commit's `manifest.json` at repo root, **When** the operator inspects it, **Then** its top-level key `atoms` is renamed to `molecules` (breaking change), and every molecule's entry contains its path and version.

### Edge Cases

- **Molecule declaring `delivers: {}` (empty map)**: refused during schema validation. Every molecule kind requires at least one category populated; the schema enforces this per-kind via `required` fields under `delivers` for known kinds.
- **Molecule declaring an unknown category** (e.g. `delivers.wibble: ["something.yaml"]`): accepted by the schema (the enum is intentionally open) but ignored by the current runtime dispatch (no known kind has a `wibble` category). Publication proceeds for the known categories only; unknown categories are recorded in the diagnostic log for forward-compat visibility.
- **Molecule declaring `kind: constitution` but no `delivers.constitution`**: refused with `key=delivers-cardinality-violation` (constitution kind requires at least one file).
- **Directory listed in `delivers.hooks` instead of individual file paths**: for kinds that specify per-file lists (hooks, skills), directories refuse with `key=delivers-cardinality-violation` variant naming "expected regular file, got directory". Kinds that explicitly accept directory categories (if any exist in a future spec) call this out in their per-kind contract.
- **Two molecules in `.haex-hive.json.molecules[]` with the same reverse-DNS id but different sources**: refused with the existing `atom-id-collision` diagnostic (unchanged Spec 007 v2 rule, now renamed to `molecule-id-collision`).
- **Consumer manifest still using top-level `atoms[]` (pre-amendment v2 shape)**: refused with `key=molecule-manifest-schema-invalid` at manifest-load. Under pre-user policy no automatic migration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (Molecule manifest schema): The molecule manifest at `<molecule-dir>/manifest.json` MUST match `molecule-manifest.v3.schema.json`. Required fields: `haex_hive_version: "2"` (unchanged), `id` (reverse-DNS), `version` (SemVer 2.0.0), `priority` (integer), `kind` (string, enum-validated against the current known-kind list), `delivers` (object mapping category name to a list of repo-relative paths). Optional fields: any that Spec 007 v2 already accepted at the top level and remain applicable. The retired `contributes` field MUST NOT be present; presence refuses with `key=molecule-manifest-schema-invalid`.
- **FR-002** (delivers path safety): Every path in `delivers.<category>[i]` MUST pass `RepoRelativePath.validate` and a canonical containment check against the molecule root at manifest-load time. Absolute paths, backslash- or drive-qualified paths, `.`/`..` traversal, and symlink or reparse-point targets that escape the molecule root MUST refuse with `key=delivers-path-escape` citing Principle II. Refusal MUST fire before any file is written to consumer roots.
- **FR-003** (delivers uniqueness invariants): (a) No path appears more than once within a single `delivers.<category>` list; violation refuses with `key=delivers-path-duplicate`. (b) No path appears in more than one category within the same `delivers` map; violation refuses with `key=delivers-category-overlap`. (c) For a kind whose semantic slot is cardinality-one (e.g. `speckit-workflow.delivers.workflow` requires exactly one path per Spec 011), the runtime MUST refuse with `key=delivers-cardinality-violation` when the list has 0 or 2+ entries. Per-kind cardinality rules are documented in each kind's owning spec.
- **FR-004** (kind enum): The known-kind enum in v1 of this amendment is `{constitution, speckit-workflow, skill, hook, mcp-server}`. A molecule declaring a `kind` value not in the enum MUST refuse with `key=unknown-molecule-kind` and stderr MUST list the known values. The enum is extensible: a new spec introducing a new kind adds its value here without needing to re-version the molecule manifest schema.
- **FR-005** (consumer manifest field rename): `.haex-hive.json` MUST use the top-level key `molecules` (list of `{source, revision, includes[]}`), NOT the retired `atoms`. Consumers using `atoms` refuse at manifest-load with `key=molecule-manifest-schema-invalid`. Every entry's `revision` MUST be a full 40-char SHA per Principle IV.
- **FR-006** (runtime rename discipline): Every runtime-visible identifier that names the packaging-unit concept MUST use the "molecule" spelling: dataclasses (`MoleculeManifest`), fields (`ConsumerManifest.molecules[]`), functions (`resolve_molecule_contributions` where applicable), diagnostic keys (`molecule-manifest-schema-invalid`), file paths (`molecule-manifest.v3.schema.json`, `install.lock.molecules[]`). Old "atom" names refer only to the individual delivered artifact concept, never to the packaging unit.
- **FR-007** (documentation rename sweep): Every reference to the retired "atom" term in the packaging-unit sense across `.specify/memory/constitution.md`, `docs/plans/*.md`, `docs/adr/*.md`, `specs/*/` (spec.md + plan.md + research.md + data-model.md + contracts/ + quickstart.md + tasks.md for every merged spec) MUST be updated to "molecule". The word "atom" survives only in the new meaning (an individual delivered artifact). The Spec 010 preview doc's usage of "molecule" (as bundle-of-atoms) MUST be renamed to "assembly". Reverse-DNS ids do NOT contain "atom" and do not change.
- **FR-008** (haex-hive-self molecule migration): The two haex-hive-self molecules (`com.github.haexmas.haex-hive.constitution` at `.specify/memory/` and `com.github.haexmas.haex-hive.graphify-first-authoring` at `.specify/atoms/graphify-first-authoring/`) MUST migrate their manifest.json in this amendment landing to `kind: constitution` + `delivers: { constitution: ["constitution.md"] }`. Both version fields bump MAJOR. The publisher-root `manifest.json` at the repo root MUST rename its top-level `atoms` key to `molecules`.
- **FR-009** (constitution v1.4.0 → v1.5.0 alignment): The haex-hive constitution's inline wording that uses "atom" in the packaging-unit sense MUST update to "molecule" as part of this amendment landing. Version bumps to 1.5.0 (MINOR) because the terminology change is a materially-expanded governance clarification, not a mere PATCH. An ADR (numbered 0010 in sequence after ADR 0009) records the rename decision.
- **FR-010** (schema retirement discipline): The retired `atom-manifest.v2.schema.json` file MUST be deleted (not shimmed) as part of this amendment landing. `molecule-manifest.v3.schema.json` takes its place. The schema loader's `_KNOWN_SCHEMAS` registry updates accordingly. Under pre-user policy no compat shim; any external consumer stuck on v2 must migrate.

### Key Entities

- **Molecule** (packaging unit): a directory containing `manifest.json` (declaring `id`, `version`, `priority`, `kind`, `delivers`) plus the atoms named in `delivers.*[]`. Formerly called "atom".
- **Atom** (individual delivered artifact): a single file inside a molecule's directory that the molecule's `delivers.<category>[]` list names. Examples: a `constitution.md`, a `workflow.yml`, a single `hook.sh`, a single `skill.md`. Not manifest-level; conceptual.
- **Assembly** (composition of molecules): a named bundle of molecules an operator adopts together, typically expressed as a "personal harness" that references multiple publisher molecules from `.haex-hive.json.molecules[]`. Formerly called "molecule" in Spec 010 preview prose.
- **Kind**: the primary discriminator on a molecule manifest, driving runtime dispatch to per-kind publication targets. Extensible enum: `{constitution, speckit-workflow, skill, hook, mcp-server}` in v1, extended by downstream specs.
- **Delivers map**: the `delivers` field on a molecule manifest. Maps a category name (matching a kind's semantic slot) to a list of repo-relative atom paths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A publisher molecule with `kind: constitution` + `delivers: { constitution: ["constitution.md"] }` validates against `molecule-manifest.v3.schema.json` and adopts cleanly on a fresh consumer. Verified by an integration test using the migrated haex-hive-self constitution molecule.
- **SC-002**: A publisher molecule with any of the delivers-safety violations (path escape, duplicate, cross-category overlap, cardinality violation, unknown kind) refuses `haex install` with the documented diagnostic key and zero files written under any managed root. Verified by five separate refusal integration tests (US2 acceptance scenarios 1-5).
- **SC-003**: The haex-hive-self checkout at the amendment-landing commit has both molecule manifests migrated to `kind` + `delivers`, and `haex install` on a scratch consumer that adopts them succeeds and produces a byte-identical `.haex-hive/constitution.md` compared to the pre-amendment output. Verified by a self-adopt regression test.
- **SC-004**: Every runtime-visible identifier for the packaging unit uses "molecule" spelling; every doc reference to the packaging-unit sense of "atom" is renamed. Verified by a repo-wide grep: `grep -rn "\batom\b"` returns zero packaging-unit hits and only individual-atom-artifact hits.
- **SC-005**: The Spec 011 workflow-atom mechanism works under v3 without any bespoke `contributes.speckit_*` field: the same workflow.yml + constitution + extensions + hooks publish to their Spec 011 targets when adopted as a v3 molecule with `kind: speckit-workflow`. Verified by an integration test that adopts a `speckit-workflow`-kind molecule.
- **SC-006**: The retired `atom-manifest.v2.schema.json` is absent from the repo after this amendment lands. A grep for `atom-manifest.v2.schema.json` in the tree returns zero results. Verified by a repo-wide grep.

## Assumptions

- **Rename is comprehensive**: the sweep touches (a) runtime symbols (`AtomManifest` → `MoleculeManifest`, `ConsumerManifest.atoms` → `.molecules`, `AtomIdCollisionError` → `MoleculeIdCollisionError`, etc.); (b) schema files (`atom-manifest.v2.schema.json` deleted, `molecule-manifest.v3.schema.json` added); (c) diagnostic keys (`atom-manifest-not-found` → `molecule-manifest-not-found`, etc.); (d) all merged spec directories (`specs/*/spec.md` + supporting artifacts wherever "atom" appears in the packaging sense); (e) design plans (`docs/plans/*.md`); (f) ADRs (`docs/adr/*.md`); (g) constitution (`.specify/memory/constitution.md` and its mirror `.haex-hive/constitution.md`); (h) haex-hive-self manifest files (`manifest.json` at repo root, `.specify/memory/manifest.json`, `.specify/atoms/graphify-first-authoring/manifest.json`). The rename sweep is a large diff; it lands in the plan/tasks phase, not this spec.
- **Pre-user policy applies**: no external adopters of haex-hive exist as of 2026-09-03. Retiring `atom-manifest.v2.schema.json`, renaming `.haex-hive.json.atoms[]` → `.molecules[]`, and bumping haex-hive-self molecule versions MAJOR requires no compat shim and no migration tooling.
- **Keep-artifacts UX is out of scope**: molecule removal remains all-or-nothing per Spec 008 R7 delete-orphans semantics. A `haex install --keep-artifacts <atom-list>` flag is a future spec's concern; this amendment intentionally does not introduce it.
- **Cross-molecule dependency graph is out of scope**: no formal model of "molecule A's skill referenced by molecule B's workflow" in v1. Publishers are expected to make each molecule self-contained.
- **Kind enum extensibility is by-spec, not by-config**: adding `skill`, `hook`, `mcp-server` to the enum is done by downstream specs (Spec 014, 015, ...) each of which adds its per-kind publication contract. This amendment lands the enum with 5 initial values; further additions do NOT require re-versioning `molecule-manifest.v3.schema.json`.
- **Directory name for spec 007 unchanged**: `specs/007-unified-manifest-v2/` keeps its "v2" suffix historically; renaming the directory would break every existing link in commits and merged PRs. The amendment preamble at the top of this spec.md is the canonical marker that the underlying manifest schema is now v3.
- **ADR 0010 for the rename**: a new ADR under `docs/adr/0010-rename-atom-molecule.md` records the decision context, per constitution §Governance requirement that amendments include an ADR.
- **Constitution v1.5.0 bump**: MINOR (materially-expanded governance guidance introducing the molecule/atom/assembly terminology). Version bump lands in the same commit as the constitution wording sweep.
- **Existing merged specs 008 + 010 preview docs**: sweep them for terminology in a follow-up commit sequence during the plan phase. Spec 010 is preview-only (no merged spec directory); its terminology change is a doc edit. Spec 008 is fully merged; its terminology change touches every file that mentions "atom" in the packaging sense.
- **Runtime migration is code-only**: no operator-side migration script needed. On upgrade to the amendment-landing haex-hive version, `haex install` on a v2-shape `.haex-hive.json` refuses cleanly; the operator edits the file to rename `atoms` → `molecules` and re-runs.

## Dependencies

- **Constitution v1.4.0** (currently landed): its inline wording uses "atom" in the packaging-unit sense in several places. This amendment updates the constitution to v1.5.0 as part of its landing (FR-009).
- **Spec 008** (Install Transaction, landed): its `install.lock.atoms[]` field renames to `install.lock.molecules[]`. Every merged doc under `specs/008-install-transaction/` is swept.
- **Spec 011** (Speckit Workflow Atom, in draft on branch): the previously-drafted spec 011 introduced bespoke `contributes.speckit_*` fields. Under this amendment those become unnecessary; Spec 011 rebuilds on the v3 fundament with `kind: speckit-workflow` + `delivers`. Spec 011's draft artifacts (currently unmerged on any branch after PR-56 was merged then abandoned via this amendment) will be re-drafted in a follow-up cycle after v3 lands.
- **Spec 010** (preview only): terminology sweep atom→molecule + molecule→assembly across the preview doc. No merged spec directory to update.
- **Existing haex-hive-self molecules**: `com.github.haexmas.haex-hive.constitution` and `com.github.haexmas.haex-hive.graphify-first-authoring` migrate their manifests in this amendment landing (FR-008).
