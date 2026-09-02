# Phase 0 Research: Speckit Workflow Atom (simplified)

**Feature**: Spec 011 (simplified re-specification, PR #54 merged)
**Date**: 2026-09-02
**Purpose**: Resolve every load-bearing implementation decision the plan reserved as "chosen in research". Each section records the decision, rationale, and alternatives considered under the simplification amendment.

---

## R1. No registry file

**Decision**: Spec 011 does NOT introduce `.specify/workflows/workflow-registry.json`. Adoption via `.haex-hive.json` is the sole signal of which workflow is binding: exactly one adopted `speckit-workflow` atom -> that workflow; none adopted -> bundled `speckit`. Two or more adopted refuse with `key=multiple-workflow-atoms-refused` at manifest load (see R3).

**Rationale**: Under one-active-per-repo (FR-006), any registry would be a single-element index. The state it would encode (which workflow is binding) is already encoded by the presence of `contributes.speckit_workflow` inside an adopted atom's manifest. A registry file is redundant state that can only drift.

**Alternatives considered**:
- **Explicit registry file with `active_workflow` selector** (the previously-merged spec 011 approach, PR #52). Rejected: adds state that can drift from `.haex-hive.json`, requires a manual selector step to make the adopted workflow binding, and enables coexistence (which we deliberately retire).
- **Registry file, no selector, only cataloguing**: rejected as strictly less informative than reading `.haex-hive.json` directly.

**Residual risk**: none identified. Reader implementations MUST NOT rely on a registry file; a legacy `workflow-registry.json` inherited from the previously-merged spec 011 draft is ignored (and should be manually deleted by the operator during migration).

## R2. Extensions ownership boundary

**Decision**: two files, disjoint responsibilities:

- **`.specify/extensions.local.yml`** is **consumer-owned**: the operator authors it, edits it, and commits it. `haex install` NEVER writes to it, deletes it, or modifies it in any way. Absent file is equivalent to empty declarations. Top-level shape uses the same keys as the generated output: `installed`, `settings`, `required_extensions`, `optional_extensions`, `hooks`.
- **`.specify/extensions.yml`** is **generated**: `haex install` regenerates it from scratch on every invocation. Inputs are the adopted workflow atom's `contributes.speckit_extensions` fragment plus `.specify/extensions.local.yml`. Merge follows FR-005 rules. The output is never used as its own next-install input; removed or downgraded atom entries never survive as stale output.

**Rationale**: this separation is the load-bearing detail of PR #54's reviewer hardening. Two goals are served:
- **Operator state preservation**: the operator's own extension declarations are in a file we never touch. They survive any atom adoption/downgrade cycle byte-for-byte. This is a Principle II-adjacent invariant (versioned config the operator owns should not be silently mutated).
- **No stale output**: because `.specify/extensions.yml` is regenerated from `.specify/extensions.local.yml` + the currently-adopted atom fragment on every install, removed atom contributions cannot leak into the next install as ghost entries.

**Alternatives considered**:
- **One file, merged in-place** (previously-merged spec 011 draft): rejected. Any file we merge into loses the "consumer-owned" invariant; every install mutates it and the operator's original entries become indistinguishable from atom contributions.
- **Persisted `extension_contributions` provenance cache in generated output** (previously-merged spec 011 draft, PR #52): rejected. The regeneration-from-scratch model makes the cache pointless (the current-adopted atom's fragment is available at every install), and the cache introduces a stale-provenance risk when the atom is downgraded.
- **Runtime re-parse of `.specify/extensions.yml` on downgrade** (to figure out what to remove): rejected. Same regeneration argument obviates the need.

**Residual risk**: an operator who edited `.specify/extensions.yml` directly (thinking it was source-of-truth) loses those edits at the next install. Mitigation: quickstart.md documents the ownership split explicitly; the generated file SHOULD carry a top-of-file comment naming itself as generated.

## R3. Single-atom refusal placement

**Decision**: `ConsumerManifest.from_json` detects the multi-workflow-atom case at manifest-load time, before any workflow resolver, fragment loader, or install pipeline runs. Refusal raises `MultipleWorkflowAtomsRefusedError` (`key=multiple-workflow-atoms-refused`, `INPUT_REFUSE`) with stderr naming every offending atom's `id` and `source`.

**Rationale**:
- **Fail early**: the refusal fires before any fragment YAML is loaded, so a broken adopted set cannot exercise the merge / resolver code paths.
- **Single home**: putting the check on `ConsumerManifest.from_json` means every consumer of `ConsumerManifest` (install, verify, potential future consumers) sees the same refusal without each having to add its own guard.
- **Consistent diagnostic surface**: uses the existing `HaexError` machinery.

**Alternatives considered**:
- **Detect at resolver time**: rejected, allows some intermediate state (parsed fragments) that a refusing manifest should not produce.
- **Detect at `cli/install.py::run` time only**: rejected, would leave other future callers of `ConsumerManifest` (verify-only, hypothetical `haex workflow list`) without the guard.

**Residual risk**: none identified. The check is O(n) in the adopted atom count.

## R4. Constraint-merge algorithm (simplified)

**Decision**: under one-active-per-repo, extension requirement merging is only atom-vs-local (one adopted atom's fragment against `.specify/extensions.local.yml`). This is strictly simpler than PR #52's cross-atom multi-fragment reduction. Algorithm per extension id:

1. Collect declarations for the id from atom fragment and local source.
2. Determine effective kind: if either declares `required`, effective kind is required; else optional.
3. Reduce constraints per kind using canonical form:
   - Two exact constraints: same -> keep; different -> refuse (`key=conflicting-constraint`) if effective kind is required; drop local optional and warn (`key=optional-workflow-extension-conflict`) if effective kind is optional and local disagrees.
   - Exact vs lower-bound / upper-bound / compatible-release: exact must satisfy the range; else refuse-or-drop per effective kind.
   - Two lower-bounds: keep higher.
   - Two upper-bounds: keep lower.
   - Lower > upper: refuse-or-drop.
4. Emit `MergedRequirement(extension_id, effective_constraint, is_required, sources)`.

**Rationale**: same correctness properties as PR #52's algorithm but with only two participants per id, the reduction is a single pair. No sort order across atoms is needed because there are no cross-atom pairs.

**Alternatives considered**:
- **Cross-atom multi-fragment algorithm from PR #52**: retired with the previously-merged spec 011; incompatible with FR-006.
- **Local always wins**: rejected. The atom's constraint is a hard requirement the workflow depends on; a local override that weakens it below the atom's floor breaks the workflow's stated dependency.
- **Atom always wins**: rejected for optional-vs-optional cases; the local optional MAY still be dropped when incompatible, but a compatible local optional should be preserved.

**Residual risk**: SemVer's compatible-release intersects awkwardly with lower-bound and exact; the algorithm handles common cases and refuses exotic disjoints.

## R5. Reader-side resolution fallback

**Decision**: `resolve_active_workflow(repo_root: Path) -> WorkflowResolution` returns a typed object with a `source: Literal["atom", "bundled"]` field and a `diagnostics: tuple[str, ...]` field. Algorithm:

1. Load `.haex-hive.json` via `ConsumerManifest.from_json`. If parse fails, return `bundled` with a diagnostic naming the parse error. If FR-006 refusal fires here, propagate the error rather than falling back (the refusal is a manifest error, not a resolver fallback case).
2. Enumerate adopted atoms. Look up their manifests via existing atom-resolution machinery.
3. Find the atom whose `contributes` map includes `speckit_workflow`.
4. If found: return `WorkflowResolution(source="atom", workflow_path=<atom's published path>, atom_id=<id>, diagnostics=[])`.
5. If not found: return `WorkflowResolution(source="bundled", workflow_path=<bundled path>, atom_id=None, diagnostics=[])`.

**Rationale**: typed return absorbs "no workflow atom adopted" as a first-class outcome, not an error. Downstream consumers get a stable API surface.

**Alternatives considered**:
- **Return `Optional[Path]`**: rejected, loses the source-attribution information which is useful for diagnostics.
- **Raise on missing bundled path**: rejected, out-of-scope; if the bundled file itself is missing, that's a checkout-broken state, not a resolver-fallback case.

**Residual risk**: none identified. If the operator physically renamed or deleted the bundled `.specify/workflows/speckit/workflow.yml`, callers dereferencing `workflow_path` get a `FileNotFoundError` at their own IO boundary.

## R6. Workflow.yml payload safety guards

**Decision**: the workflow.yml payload itself (the file the atom contributes at `contributes.speckit_workflow`) is validated on load for:

1. **YAML parse validity**: unparseable YAML refuses.
2. **No plaintext secrets**: `validate_no_plaintext_secrets` runs across every string field.
3. **No concealment instructions**: `validate_no_concealment_instructions` runs across every string field.
4. **Path containment on `steps[].script` and `hooks[].script` fields**: each path must pass `RepoRelativePath.validate` and resolve to a file below the atom's declared `speckit_hooks` directory. Absolute paths, backslash paths, `.`/`..` traversal, symlink escapes all refuse with a Principle II diagnostic.

**Rationale**: Principle I and VIII apply to every payload haex-hive publishes into a committed root. A workflow.yml with a secret in its `description` or a concealment instruction in a `prompt` field is exactly the kind of drift these validators exist to catch.

**Alternatives considered**:
- **Trust the publisher**: rejected, contradicts Principle VIII.
- **Deep schema validation of workflow.yml against a formal schema**: deferred. The bundled `.specify/workflows/speckit/workflow.yml` is a shape reference; a formal `workflow.v1.schema.json` is a Spec 011 successor concern.

## R7. Publisher-side atom directory shape

**Decision**: a reference workflow-atom directory looks like:

```text
com.example.publisher.strict-tdd-workflow/
├── manifest.json                       # atom-manifest v2 shape (from Spec 007)
├── workflow.yml                        # workflow declaration
├── constitution.md                     # optional; MUST-rules the workflow imposes
├── extensions.yml                      # optional; required-extensions + hook mappings
└── hooks/                              # optional; hook scripts referenced by extensions.yml.hooks[]
    ├── pre-implement.sh
    └── post-tasks.sh
```

The atom's `manifest.json` MUST declare `contributes.speckit_workflow: "workflow.yml"` and MAY declare `contributes.constitution`, `contributes.speckit_extensions`, `contributes.speckit_hooks: "hooks/"`.

**Rationale**: mirrors the bundled `.specify/workflows/speckit/workflow.yml` shape for the workflow file; other files follow standard atom-contribution conventions from Spec 007.

**Alternatives considered**:
- **A single-file atom (workflow.yml only)**: valid, permitted. The design supports minimal atoms that contribute only the workflow declaration.
- **All-in-one `speckit-workflow.yml` conflating workflow + extensions + constitution**: rejected, breaks the atom-contribution convention where each field is its own file.

## R8. Hook identity for replace-by-identity

**Decision**: a hook entry's identity is the tuple `(stage, extension, command, script)`. Two entries with the same tuple are considered the same hook; a local declaration with an identity-matching atom entry REPLACES the atom entry in the generated `.specify/extensions.yml`'s `hooks.<stage>[]` list. Non-identity-matching local entries append after atom entries.

**Rationale**: this is the load-bearing detail from PR #54's reviewer hardening of FR-005. The identity tuple is:
- `stage`: which lifecycle stage the hook attaches to.
- `extension`: which speckit extension defines the hook (may be `null` for local hooks not sourced from an extension).
- `command`: the dotted command name.
- `script`: the script path.

Two atom-contributed entries with the same identity refuse with `key=workflow-hook-mapping-invalid` (duplicate within the fragment). Two local entries with the same identity refuse similarly (duplicate within the local source).

**Alternatives considered**:
- **Identity = `(stage, command)` only**: rejected, allows two different hooks (different scripts, different extensions) with the same command to silently overwrite each other.
- **Identity = full entry hash**: rejected, would mean two entries differing only in `description` are considered different hooks; the user-intent for override is clearer with the 4-tuple.

**Residual risk**: the `extension` field is nullable, and a local hook without an extension might identity-match an atom hook with an empty extension. This is fine: the local entry replaces per FR-005 rule.

---

## Summary of Phase 0 outputs

- R1 registry-alternative: no registry file
- R2 extensions ownership boundary: `.specify/extensions.local.yml` (consumer) vs `.specify/extensions.yml` (generated)
- R3 single-atom refusal placement: `ConsumerManifest.from_json`
- R4 constraint-merge algorithm: simplified to atom-vs-local
- R5 reader resolution fallback: typed `WorkflowResolution` with `source` field
- R6 workflow.yml payload safety guards
- R7 publisher-side atom directory shape
- R8 hook identity for replace-by-identity: `(stage, extension, command, script)` tuple

Phase 1 (data-model + contracts + quickstart) consumes these decisions.
