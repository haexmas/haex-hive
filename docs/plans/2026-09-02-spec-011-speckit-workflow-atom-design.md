# Spec 011: Speckit Workflow Atom (Design Preview)

**Status**: Design preview. Not yet a spec. Captured 2026-09-02 as the requirements source for the eventual `/speckit-specify` invocation that creates `specs/011-speckit-workflow-atom/`.

**Purpose**: define a mechanism for per-project speckit-workflow selection, so that the "which speckit workflow is binding" question is answered by a versioned atom rather than by ad-hoc convention. This closes the gap identified during the 2026-09-02 amendment of the haex-hive constitution to 1.4.0 (see [ADR 0009](../adr/0009-declared-speckit-workflow-adherence.md)).

**Related**:
- [Constitution v1.4.0 §Development Workflow](../../.specify/memory/constitution.md): the "Declared speckit workflow adherence" bullet the atom concretises.
- [Spec 007: Unified Manifest v2](2026-08-28-spec-007-unified-manifest-design.md): atom-manifest baseline; adds a new `contributes.speckit_workflow` type.
- [Spec 008: Install Transaction](../../specs/008-install-transaction/): landed; `haex install` merges contributions into `.haex-hive/`. Multi-source constitution merge already exists; this design extends the merge surface with a second contribution type.
- [Spec 010: Compiler & Agent Adapters](2026-08-31-spec-010-compiler-preview.md): future compiler will emit per-tool artifacts; workflow.yml is one such artifact.
- [specifyr catalog pattern](https://github.com/haexhub/specifyr): sibling project defining `catalog/skills/*.md` and `catalog/tools/*.yml` with per-project overrides. This design borrows the catalog + override shape.
- [speckit-community extensions](https://speckit-community.github.io/extensions/): the extension ecosystem this atom-kind lets a project bind to.

---

## What this covers

A **speckit-workflow atom**: a new atom kind that carries:

1. A `workflow.yml` payload compatible with `.specify/workflows/<id>/workflow.yml` today.
2. Optionally, a `constitution.md` fragment stating the MUST rules that the workflow imposes.
3. Optionally, an `extensions.yml` fragment declaring which speckit-community extensions the workflow depends on (with version constraints).
4. Optionally, additional per-skill or per-hook payloads (e.g. custom slash commands, per-stage hook scripts).

Adoption is via `.haex-hive.json`, same as any other atom. On `haex install`:

- The workflow.yml payload lands at `.specify/workflows/<atom-workflow-id>/workflow.yml`.
- Any constitution fragment merges into `.haex-hive/constitution.md` via the existing multi-source merge, so the workflow's MUST rules become part of the assembled constitution automatically.
- Any `extensions.yml` fragment contributes its extension requirements and hook declarations to the canonical top-level `required_extensions`, `optional_extensions`, and `hooks` keys in `.specify/extensions.yml`. Requirements remain separate from hook declarations; atom hooks are merged into the same `hooks.<stage>` lists as local hooks, with atom entries first and local entries last.

## What this does NOT cover (deliberately)

- **Runtime enforcement of workflow adherence**: mechanical refusal on non-workflow task landings. This stays advisory-to-the-agent for now; a future ADR under Phase 7 may add a pre-commit hook, but that is orthogonal to atom distribution.
- **A registry of "approved" workflows**: every publisher is free to publish workflow atoms; there is no central curation. The operator picks their workflow the same way they pick any other atom (by pinning a specific source+revision).
- **Live workflow updates without pinning**: an atom-adopted workflow uses the same `revision` pin as every other atom (Principle IV, NON-NEGOTIABLE). Workflow drift on the operator's device is intentional (it happens when the operator bumps the pin) and not detectable as concurrent replay.
- **Automatic installation of speckit-community extensions** the workflow declares as required. The atom declares which extensions and version constraints are needed; installation of extensions themselves is delegated to specifyr's extension-install mechanism (or a manual `speckit extensions install <name>@<version>` step). Preventing workflow use when required extensions are missing or incompatible is a validator concern, not a distribution one.

## Terminology

- **Workflow**: the ordered set of steps + review gates + hook wiring that `/speckit-implement` (and its stage siblings) executes. Concrete on-disk shape: `workflow.yml` (existing).
- **Workflow atom**: a Spec-007 atom whose `contributes` map includes at least `speckit_workflow: <path>` pointing at a `workflow.yml` in the atom's directory.
- **Extension**: a speckit-community-published bundle (e.g. `V-Model Extension Pack@0.7.2`) providing skills, hooks, or workflows. Referenced by a workflow atom but installed separately.

## Architecture

### Atom-manifest addition

`atom-manifest.v2.schema.json` gains a new `contributes.speckit_workflow` field. Shape:

```yaml
haex_hive_version: "2"
id: com.example.publisher.strict-tdd-workflow
version: "1.0.0"
priority: 5
contributes:
  speckit_workflow: "workflow.yml"          # required for this atom kind
  constitution: "constitution.md"           # optional; MUST-rules the workflow imposes
  speckit_extensions: "extensions.yml"      # optional; requirements + hook declarations
  speckit_hooks: "hooks/"                   # optional; directory of hook scripts to install
```

`speckit_workflow`, `constitution`, `speckit_extensions`, and
`speckit_hooks` are atom-directory-relative source paths. Every source path is
validated with `RepoRelativePath.validate`. The resolver then performs a
canonical containment check: the resolved source must remain below the atom
root, and the destination must remain below the consumer repository root.
Absolute paths, backslash or drive-qualified paths, `.`/`..` traversal, and
symlink or reparse-point targets that escape either root are refused. The
validator applies the same checks to every discovered file copied from the
`speckit_hooks` directory. Valid relative paths remain supported. Output paths
are never state-root-relative in committed configuration; the device-local
state root is reserved for caches and transaction internals.

The `constitution.md` fragment is contributed alongside the `speckit_workflow`: same multi-source merge as any other constitution atom. Difference: its content is scoped to workflow discipline (e.g. "every failing test MUST be reported before implementation continues"), not general system principles.

### Adoption flow

Consumer's `.haex-hive.json`:

```json
{
  "atoms": [
    {
      "source": "https://github.com/example/speckit-workflows",
      "revision": "<full 40-char SHA>",
      "includes": ["com.example.publisher.strict-tdd-workflow"]
    }
  ]
}
```

On `haex install`:

1. The publisher's atom is resolved via the existing publisher-clone + pinned-revision machinery.
2. `contributes.speckit_workflow` payload publishes to `.specify/workflows/<atom-workflow-id>/workflow.yml`. The atom's `id` becomes the workflow directory name; multiple workflow atoms may coexist under `.specify/workflows/`. One is designated active through the canonical `active_workflow` field in `.specify/workflows/workflow-registry.json`.
3. `contributes.constitution` fragment participates in the existing multi-source constitution merge; the constitution's declared speckit workflow bullet (v1.4.0) now applies to the adopted workflow's declared steps.
4. `contributes.speckit_extensions` is parsed using the `extensions.yml` contract below. Its requirements merge into the canonical `required_extensions` and `optional_extensions` lists, while its hook declarations merge into the canonical `hooks.<stage>` lists. Required declarations determine the effective requirement when an ID is also optional; a valid conflicting optional declaration is omitted with a stderr warning, while unsupported syntax refuses the install. Atom hooks run before local hooks; a local declaration for the same hook identity (`stage`, `extension`, `command`, and `script`) replaces the atom declaration. Atom entries are ordered by atom ID using bytewise UTF-8 ordering, then by hook identity; local entries follow in their canonical local order.
5. `contributes.speckit_hooks/*` scripts land under the reserved atom-owned namespace `.specify/extensions/workflow-atoms/<atom-id>/` for reuse by the canonical `hooks` declarations. Community extensions remain direct child directories of `.specify/extensions/`; the installer refuses namespace or destination collisions before publication. Every atom-contributed hook has a required `script` field naming the final repository-relative destination (for example, `.specify/extensions/workflow-atoms/com.example.publisher.strict-tdd-workflow/hooks/v_model/prepare.py`). The installer maps that destination back to the atom-relative source below `speckit_hooks`, rejects missing or non-regular targets, and includes the copied files in the same transaction as the declarations that reference them.
6. All outputs from steps 2–5 and the assembled `.haex-hive/constitution.md` are prepared and validated by one repository-wide install transaction. No output is published until every output is valid and any required constitution review has been accepted. A failed review or later validation discards the staged candidate; if publication has already begun, existing in-flight recovery restores the previous marker-consistent generation and all output roots before the install reports failure. The existing `.haex-hive/` generation and rename-swap behavior remains unchanged.

### Active-workflow selection

`.specify/workflows/workflow-registry.json` gains an `active_workflow` field:

```json
{
  "schema_version": "1.0",
  "active_workflow": "com.example.publisher.strict-tdd-workflow",
  "workflows": {
    "speckit":                                   { "source": "bundled",  ... },
    "com.example.publisher.strict-tdd-workflow": { "source": "atom",     ... }
  },
  "extension_contributions": {
    "com.example.publisher.strict-tdd-workflow": {
      "required_extensions": ["v-model-extension-pack"],
      "optional_extensions": ["speckit-companion"],
      "hooks": ["before_implement|v-model-extension-pack|v_model.prepare|.specify/extensions/workflow-atoms/com.example.publisher.strict-tdd-workflow/hooks/v_model/prepare.py"]
    }
  }
}
```

The constitution's v1.4.0 clause becomes concrete: readers look at `.specify/workflows/workflow-registry.json.active_workflow`, then load the matching `workflow.yml`, and MUST follow those steps. The existing registry is the source of truth during reconciliation: preserve its selected ID when the candidate still contains a valid matching `workflow.yml`; reset `active_workflow` to `null` when no valid selection exists or the selected workflow was removed, so readers use the implicit bundled `speckit` default. The registry always writes `active_workflow`, and a registry MUST never retain an active ID whose `workflow.yml` is absent.

### Extension declaration format

The contributed `extensions.yml` fragment uses the same vocabulary as the
consumer file, omitting consumer-owned `installed` and `settings` keys. This
is the one canonical extension contract; no alternate atom-specific hook key
is defined. The manifest contribution names identify source payloads, while
the destination configuration always uses the canonical keys below.

```yaml
required_extensions:
  - id: v-model-extension-pack
    version_constraint: ">=0.7.2"
    homepage: https://speckit-community.github.io/extensions/v-model-extension-pack
  - id: bugfix-workflow
    version_constraint: "1.0.0"
    homepage: https://speckit-community.github.io/extensions/bugfix-workflow

optional_extensions:
  - id: speckit-companion
    version_constraint: ">=0.21.0"

hooks:
  before_implement:
    - extension: v-model-extension-pack
      command: v_model.prepare
      script: ".specify/extensions/workflow-atoms/com.example.publisher.strict-tdd-workflow/hooks/v_model/prepare.py"
      enabled: true
      optional: false
      prompt: Run the V-Model preparation hook?
      description: Prepare the implementation stage
      condition: null
```

The local `.specify/extensions.yml` retains its consumer-owned `installed` and
`settings` keys and uses the same `required_extensions`,
`optional_extensions`, and `hooks` keys shown above. The `script` field is a
repository-relative path in the canonical output; it is required for an
atom-contributed hook and MUST resolve to the copied file described in step 5.
Requirement entries are merged by extension ID. The effective constraint is
the logical intersection of all declarations for that ID, normalized to Spec
007's supported `X.Y.Z` exact or `>=X.Y.Z` lower-bound grammar: exact
constraints must agree, lower bounds retain the strongest lower bound, and an
exact constraint combined with a lower bound remains exact only when it
satisfies that bound. An empty intersection refuses the install with
`key=conflicting-constraint`; an unsupported constraint refuses with
`key=invalid-constraint`; no comma-separated, tilde, caret, or wildcard
constraint is serialized. If an ID is both required and
optional, it appears only in `required_extensions`; required status wins. A
valid optional constraint that conflicts with the required constraint is omitted
and emits `key=optional-workflow-extension-conflict` as a stderr warning.
Conflicting non-constraint metadata also refuses the install. The resulting
lists are sorted by extension ID, and hook entries use
the stable atom-before-local ordering described above.

The generated canonical file records the atom IDs contributing each merged
entry in an `extension_contributions` map in
`workflow-registry.json`. Each map value contains the atom's original
`required_extensions`, `optional_extensions`, and hook identities (including
`script`), so reconciliation can remove all entries owned by an atom and
recompute the three canonical keys from the remaining active atom fragments
plus local declarations. Atom-owned entries are never retained just because
they happen to remain in the previous serialized file; local entries are
preserved. The map is install metadata and is not consumed by the extension
runner.

Validator behaviour: on install, every `required_extensions` entry must name a
community package installed as a direct child of `.specify/extensions/` whose
authoritative semantic version is `extension.version` in `extension.yml`. If
`.registry` also records a version, it must match `extension.yml`; a mismatch
refuses with `key=installed-extension-metadata-mismatch`. A missing package
refuses with `key=required-workflow-extension-missing`; an incompatible
installed version refuses with `key=required-workflow-extension-incompatible`
(new exit-code slots). Optional extensions may be absent. Version constraints
follow Spec 007's existing `VersionConstraint` grammar; every unsupported
declaration refuses with `key=invalid-constraint` rather than being dropped.

## Constraints (constitution alignment)

- **Principle I**: the workflow atom carries no secrets. `workflow.yml`, contributed `constitution.md` fragments, and `extensions.yml` fragments MUST NOT reference credentials.
- **Principle II**: no absolute paths. All workflow and contribution paths in committed configuration are repository-relative and pass `RepoRelativePath.validate` plus canonical containment checks. Device-local state-root paths never enter the committed configuration.
- **Principle IV**: the atom is pinned by full 40-char SHA, same as every other atom. No branch/HEAD adoption.
- **Principle VI**: the assembled `.haex-hive/constitution.md` still lands through the `--accept-merged` two-phase flow (or the PR-review gate for haex-hive itself). This includes exactly one workflow constitution contribution: `haex install` MUST NOT take the `assemble_single_source` shortcut for it. Without accepted merged input, the install refuses before publishing workflow outputs or changing the assembled constitution; a regression test covers this case.
- **Principle VIII**: a workflow atom's constitution fragment MUST NOT contain concealment instructions (`--haex-confirm` and the safety validators from Spec 007 already enforce this on the merged assembly).

## Decisions for `/speckit-specify`

1. **Single active workflow**: `active_workflow` is single-valued in v1. Multi-active selection is deferred to a later version.
2. **Hook precedence and order**: atom hooks run first, grouped by ascending atom ID and then hook identity; local hooks run last in canonical local order. An exact local hook identity (`stage`, `extension`, `command`, `script`) replaces the atom entry.
3. **Extension installation**: `haex install` refuses missing required extensions; the operator installs external packages separately.
4. **Constitution-fragment merging**: append a new `## Workflow-Contributed Rules` section sourced by workflow atom ID through the existing multi-source merge.
5. **Bundled workflow status**: the bundled `speckit` workflow coexists with adopted workflows; `active_workflow` selects the binding workflow.
6. **Downgrade/removal**: removed workflow atoms are delete-orphaned in the same transaction. Their recorded extension requirements and hooks are removed and the canonical extension configuration is recomputed from remaining active atoms plus local declarations. If the removed atom was active, `active_workflow` resets to `null` and readers use the bundled default; otherwise a still-valid existing selection is preserved.

## Success criteria (measurable outcomes)

- **SC-011.1**: Adopting a workflow atom via `.haex-hive.json` publishes `.specify/workflows/<atom-id>/workflow.yml` byte-for-byte matching the atom's contribution.
- **SC-011.2**: The atom's `constitution.md` fragment appears in the assembled `.haex-hive/constitution.md` after `haex install --accept-merged`.
- **SC-011.3**: Setting `active_workflow` in `workflow-registry.json` to an adopted-atom workflow ID makes the constitution's declared-speckit-workflow bullet resolve to that workflow's steps (verifiable by an agent-behavioural walkthrough test).
- **SC-011.4**: Removing a workflow atom from `.haex-hive.json` and re-installing removes the corresponding `.specify/workflows/<atom-id>/` and `.specify/extensions/workflow-atoms/<atom-id>/` directories and that atom's requirements and hooks from `.specify/extensions.yml` in the same transaction, while preserving unrelated atom and local entries. If that atom was active, the transaction resets `active_workflow` to `null`; no registry may retain an ID whose `workflow.yml` was deleted.
- **SC-011.5**: A workflow atom declaring a required extension causes `haex install` to refuse with `required-workflow-extension-missing` when the extension is absent and with `required-workflow-extension-incompatible` when the installed version fails its declared `version_constraint`. The conformance suite includes both cases.

## Required conformance scenarios

- A single workflow atom with a constitution contribution and no accepted
  merged input is refused before publication; the previous constitution,
  workflow files, hooks, extension configuration, and registry remain
  byte-for-byte unchanged.
- Every contribution path and every copied hook file rejects absolute paths,
  `.`/`..` traversal, and symlink or reparse-point escapes, while a valid
  relative path is accepted.
- A transaction that fails after staging or during publication restores all
  previous output roots and leaves no partially published workflow, hook,
  extension, registry, or constitution output.
- Two atoms contributing hooks to one stage are serialized and executed in
  ascending atom-ID order, independent of consumer declaration or resolution
  order; atom hooks still precede local hooks.
- Compatible requirements for one extension ID serialize to the normalized
  constraint intersection; required-versus-optional resolves to required, and
  an empty intersection refuses. The test asserts the exact canonical YAML
  bytes for all three cases.
- Removing one adopted atom and reinstalling removes its workflow, copied
  hooks, requirements, and hook declarations while preserving local entries;
  removing a non-active atom preserves a still-valid adopted
  `active_workflow`, and removing the active atom resets it to `null` so readers
  use the bundled default.
- Every atom hook's `script` resolves to one copied regular file under its
  atom-owned extension directory; missing or mismatched mappings refuse before
  publication.

## Deferred to later specs

- **Runtime enforcement** of workflow adherence (pre-commit hook, GitHub Action). Advisory-to-agent for now; mechanical enforcement is a Phase 7 concern per constitution §Governance.
- **Automatic extension installation**. The atom declares what it needs; the operator installs. A future specifyr-integration spec may add auto-install.
- **Workflow versioning across satellites**: when two satellites use different workflow atom revisions, how does `/speckit-analyze` reconcile? Deferred to a Spec-011-followup.

## Follow-up notes

- Once landed, retire the "planned Spec 011" forward-reference in constitution v1.4.0's Development Workflow bullet in a v1.4.1 (PATCH) amendment.
- The specifyr project has a `catalog/skills/` + `catalog/tools/` pattern with per-project overrides at `<project>/.specify/org/catalog/`. This spec deliberately does not adopt that catalog shape for workflows; each project pins one active workflow atom directly. If per-role, per-agent workflows are ever needed, the catalog pattern can be layered on top later.
