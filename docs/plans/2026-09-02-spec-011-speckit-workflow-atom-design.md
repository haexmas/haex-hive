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
3. Optionally, an `extensions.yml` fragment declaring which speckit-community extensions the workflow depends on (with pinned versions).
4. Optionally, additional per-skill or per-hook payloads (e.g. custom slash commands, per-stage hook scripts).

Adoption is via `.haex-hive.json`, same as any other atom. On `haex install`:

- The workflow.yml payload lands at `.specify/workflows/<atom-workflow-id>/workflow.yml`.
- Any constitution fragment merges into `.haex-hive/constitution.md` via the existing multi-source merge, so the workflow's MUST rules become part of the assembled constitution automatically.
- Any extensions.yml fragment merges into `.specify/extensions.yml` under a new `hooks_from_atoms` key, so per-workflow hook contributions coexist with locally-declared hooks.

## What this does NOT cover (deliberately)

- **Runtime enforcement of workflow adherence**: mechanical refusal on non-workflow task landings. This stays advisory-to-the-agent for now; a future ADR under Phase 7 may add a pre-commit hook, but that is orthogonal to atom distribution.
- **A registry of "approved" workflows**: every publisher is free to publish workflow atoms; there is no central curation. The operator picks their workflow the same way they pick any other atom (by pinning a specific source+revision).
- **Live workflow updates without pinning**: an atom-adopted workflow uses the same `revision` pin as every other atom (Principle IV, NON-NEGOTIABLE). Workflow drift on the operator's device is intentional (it happens when the operator bumps the pin) and not detectable as concurrent replay.
- **Automatic installation of speckit-community extensions** the workflow declares as required. The atom declares which extensions and pinned versions are needed; installation of extensions themselves is delegated to specifyr's extension-install mechanism (or a manual `speckit extensions install <name>@<version>` step). Preventing workflow use when required extensions are missing is a validator concern, not a distribution one.

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
  speckit_extensions: "extensions.yml"      # optional; required extensions with pinned versions
  speckit_hooks: "hooks/"                   # optional; directory of hook scripts to install
```

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
2. `contributes.speckit_workflow` payload publishes to `.specify/workflows/<atom-workflow-id>/workflow.yml`. The atom's `id` becomes the workflow directory name; multiple workflow atoms may coexist under `.specify/workflows/`. One is designated active via `.specify/workflows/workflow-registry.json` (a new field: `active`).
3. `contributes.constitution` fragment participates in the existing multi-source constitution merge; the constitution's declared-speckit-workflow bullet (v1.4.0) now applies to the adopted workflow's declared steps.
4. `contributes.speckit_extensions` fragment merges into `.specify/extensions.yml` under a new `atom_hooks` list; local overrides win when there is a collision on a `before_*` / `after_*` slot for a stage.
5. `contributes.speckit_hooks/*` scripts land under `.specify/extensions/<atom-id>/` for reuse by declared hooks.

### Active-workflow selection

`.specify/workflows/workflow-registry.json` gains an `active_workflow` field:

```json
{
  "schema_version": "1.0",
  "active_workflow": "com.example.publisher.strict-tdd-workflow",
  "workflows": {
    "speckit":                                   { "source": "bundled",  ... },
    "com.example.publisher.strict-tdd-workflow": { "source": "atom",     ... }
  }
}
```

The constitution's v1.4.0 clause becomes concrete: readers look at `.specify/workflows/workflow-registry.json.active_workflow`, then load the matching `workflow.yml`, and MUST follow those steps. When `active_workflow` is unset, the built-in `speckit` bundled workflow is the default.

### Extension declaration format

Contributed `extensions.yml` fragment shape (new; separate from the local `.specify/extensions.yml` shape):

```yaml
required_extensions:
  - id: v-model-extension-pack
    version: ">=0.7.2, <1.0.0"
    homepage: https://speckit-community.github.io/extensions/v-model-extension-pack
  - id: bugfix-workflow
    version: "~=1.0.0"
    homepage: https://speckit-community.github.io/extensions/bugfix-workflow

optional_extensions:
  - id: speckit-companion
    version: ">=0.21.0"
```

Validator behaviour: on install, if `required_extensions` names a package that is not installed in the local `.specify/extensions/`, `haex install` refuses with `key=required-workflow-extension-missing` (new exit code slot). Version constraints follow Spec 007's existing `VersionConstraint` grammar.

## Constraints (constitution alignment)

- **Principle I**: the workflow atom carries no secrets. `workflow.yml`, contributed `constitution.md` fragments, and `extensions.yml` fragments MUST NOT reference credentials.
- **Principle II**: no absolute paths. All workflow.yml paths are repo-relative or state-root-relative.
- **Principle IV**: the atom is pinned by full 40-char SHA, same as every other atom. No branch/HEAD adoption.
- **Principle VI**: the assembled `.haex-hive/constitution.md` still lands through the `--accept-merged` two-phase flow (or the PR-review gate for haex-hive itself). A newly-adopted workflow atom's constitution fragment MUST NOT change the assembled constitution without the operator explicitly reviewing the merged output.
- **Principle VIII**: a workflow atom's constitution fragment MUST NOT contain concealment instructions (`--haex-confirm` and the safety validators from Spec 007 already enforce this on the merged assembly).

## Open questions for `/speckit-specify`

1. **Multi-active workflow**: does the design permit two workflow atoms adopted simultaneously (e.g. `strict-tdd` for backend + `bugfix-workflow` for hotfix branches), or is `active_workflow` single-valued? Recommend single-valued for the first version; multi-active is a v2 concern.
2. **Precedence of local vs atom hooks**: when a locally-declared hook and an atom-contributed hook both target the same stage (`before_implement`, say), which runs first? Recommend: atom hooks run first, local hooks last. Rationale: local hooks are operator overrides.
3. **Extension installation**: is `haex install` expected to install missing required extensions, or refuse? Recommend: refuse. Installation of external packages is out of scope for the transaction contract; the operator installs extensions separately (via specifyr or a `speckit extensions install` CLI).
4. **Constitution-fragment merging semantics**: how does a workflow atom's constitution fragment merge with the haex-hive core constitution? Two options: (a) append as a new section, (b) merge into an existing `## Development Workflow` section. Recommend: append as a new `## Workflow-Contributed Rules` section, sourced by the workflow atom's ID.
5. **Bundled workflow status**: when a workflow atom is adopted, does the bundled `.specify/workflows/speckit/workflow.yml` remain available as a fallback, or does adoption replace it? Recommend: coexist; `active_workflow` field decides which is binding.
6. **Downgrade path**: what happens when an operator removes a workflow atom from `.haex-hive.json`? The workflow.yml files under `.specify/workflows/<atom-id>/` become orphans: do they get deleted, or retained? Recommend: deleted (delete-orphans semantics from Spec 008 US4 apply).

## Success criteria (measurable outcomes)

- **SC-011.1**: Adopting a workflow atom via `.haex-hive.json` publishes `.specify/workflows/<atom-id>/workflow.yml` byte-for-byte matching the atom's contribution.
- **SC-011.2**: The atom's `constitution.md` fragment appears in the assembled `.haex-hive/constitution.md` after `haex install --accept-merged`.
- **SC-011.3**: Setting `active_workflow` in `workflow-registry.json` to an adopted-atom workflow ID makes the constitution's declared-speckit-workflow bullet resolve to that workflow's steps (verifiable by an agent-behavioural walkthrough test).
- **SC-011.4**: Removing a workflow atom from `.haex-hive.json` and re-installing removes the corresponding `.specify/workflows/<atom-id>/` directory.
- **SC-011.5**: A workflow atom declaring `required_extensions` that are not installed causes `haex install` to refuse with the documented exit code.

## Deferred to later specs

- **Runtime enforcement** of workflow adherence (pre-commit hook, GitHub Action). Advisory-to-agent for now; mechanical enforcement is a Phase 7 concern per constitution §Governance.
- **Automatic extension installation**. The atom declares what it needs; the operator installs. A future specifyr-integration spec may add auto-install.
- **Workflow versioning across satellites**: when two satellites use different workflow atom revisions, how does `/speckit-analyze` reconcile? Deferred to a Spec-011-followup.

## Follow-up notes

- Once landed, retire the "planned Spec 011" forward-reference in constitution v1.4.0's Development Workflow bullet in a v1.4.1 (PATCH) amendment.
- The specifyr project has a `catalog/skills/` + `catalog/tools/` pattern with per-project overrides at `<project>/.specify/org/catalog/`. This spec deliberately does not adopt that catalog shape for workflows; each project pins one active workflow atom directly. If per-role, per-agent workflows are ever needed, the catalog pattern can be layered on top later.
