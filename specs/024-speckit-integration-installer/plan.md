# Implementation Plan: Declarative Spec Kit Integration Installer

**Branch**: `024-speckit-integration-installer` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/024-speckit-integration-installer/spec.md`

## Summary

Add a first-class, declarative Spec Kit contribution to spaex molecules. The
contribution will describe an exact or lower-bound `specify` CLI version and a
set of official integration keys/options, but will not carry Spec Kit skills.
`spaex install` will resolve the declaration, obtain an explicit/persisted or
interactive agent selection, validate the installed CLI, and invoke
`specify integration install <key>` serially for selected project-local agents.
The official CLI remains authoritative for agent-specific files and behavior.

The implementation extends the molecule manifest and install-lock contracts,
adds a small subprocess adapter, adds install/add selection flags, and keeps
external agent-file side effects outside spaex's rename-swap rollback. Generic
`install_hook` remains unrelated to the normal Spec Kit path.

## Technical Context

**Language/Version**: Python 3.14.x
**Primary Dependencies**: Existing standard library (`subprocess`, `shlex` only for validation, `hashlib`, `json`) plus `jsonschema`, `pyyaml`, and the runtime `uv` tool runner
**Storage**: Existing `.spaex/manifest.json` compound configuration and `.spaex/install.lock`; publisher molecule `manifest.json` gains `speckit` metadata
**Testing**: pytest unit, contract, and integration tests; deterministic fake `specify` executable; opt-in live smoke check
**Target Platform**: Linux/macOS/Windows where the official `specify` CLI and selected agent integration are supported; subprocess invocation uses argument arrays and no shell
**Project Type**: Python CLI/library
**Performance Goals**: No additional external CLI invocation on an unchanged successful install; local validation and lock comparison remain sub-second for normal molecule sets
**Constraints**: Project-local installation only; pinned `specify-cli` provisioning through uv; no agent-runtime provisioning; no copied Spec Kit skill content; external CLI changes are not transactionally reversible by spaex
**Scale/Scope**: One or more selected Spec Kit integrations for one consumer repository; first conformance targets Claude Code and Codex CLI

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Spec-Kit constitution

- **Specifications are the product contract**: PASS. This plan is derived from Spec 024 and adds contracts before implementation.
- **Spec-Kit workflow**: PASS. The active workflow is being followed on the feature branch; no source implementation is started in this planning phase.
- **Separation from spaex**: PASS. Spec Kit remains the external workflow/skill owner; spaex only composes, selects, invokes, and records.

### spaex constitution

- **Immutable external references**: PASS. Molecule revisions remain full SHA pins; the Spec Kit CLI policy forbids mutable `latest`, branches, and wildcards.
- **Pinned CLI provisioning**: PASS. The molecule may declare an exact `specify-cli` package version, which spaex runs through its `uv` runtime dependency without modifying the user's PATH.
- **Input validation and data-loss prevention**: PASS. Manifest, selection, version, command, and lock inputs are validated before invocation; external partial changes are reported rather than falsely rolled back.
- **Install side effects**: PASS with explicit boundary. This is a first-class declared action, not an arbitrary `install_hook`; external CLI effects are documented as non-transactional and project-local.
- **Tests**: PASS in plan. Contract tests, fake-CLI integration tests, failure cases, and idempotence coverage are required.
- **ADR requirement**: PASS. ADR 0019 records the external Spec Kit delegation, pinning, and side-effect boundary.
- **Graphify-first authoring**: PASS for planning. Graphify was consulted for the existing install path; all returned candidates were evaluated. No existing Spec Kit integration runner or model was found, so the planned adapter is an independent artifact. Implementation must repeat graphify consultation before authoring each new named code artifact.

No constitution gate is blocked. The root `CLAUDE.md` referenced by the
upstream plan skill is absent in this repository; no global instruction file
will be edited as a substitute.

## Phase 0: Research Summary

Research is captured in [research.md](research.md). The load-bearing decisions
are:

1. Delegate integration layout and conflict behavior to official Spec Kit.
2. Add a typed molecule declaration rather than using `install_hook`.
3. Verify an exact/lower-bound CLI policy and provision an exact package through
   the bundled `uv` tool runner when the molecule declares one.
4. Persist the selection and successful outcomes in the install lock.
5. Invoke selected integrations serially outside the spaex generation swap.
6. Use the lock fingerprint for the clean no-op path.
7. Support project-local integrations first.

## Phase 1: Design

### Data model

See [data-model.md](data-model.md). The implementation will add:

- `SpeckitDeclaration` and per-integration option parsing to
  `src/spaex/model/molecule_manifest.py`;
- an optional `speckit` record to `MoleculeEntry` in
  `src/spaex/model/install_lock.py`;
- declaration, selection, fingerprint, and outcome validation helpers in the
  new `src/spaex/integrations/speckit.py` module; and
- schema support in `src/spaex/schema/data/molecule-manifest.v4.schema.json`
  and `src/spaex/schema/data/install-lock.v4.schema.json`.

Consumer compound configuration remains the existing `values` map; no new
top-level consumer-manifest field is introduced.

### Runtime flow

1. Resolve all selected molecules through the existing resolver.
2. Collect and validate all Spec Kit declarations before any external install.
3. Refuse incompatible declarations from multiple molecules.
4. Determine the agent selection from command-line override, matching lock,
   interactive prompt, or non-interactive refusal.
5. Run `specify version` and `specify integration list` through the adapter.
6. Compare declaration fingerprint, CLI version, selection, and previous
   successful outcomes. Return a no-op for an unchanged satisfied state.
7. Invoke `specify integration install <key>` for each affected key in sorted
   order, passing the declared integration option as one argument and using the
   consumer repository as `cwd`.
8. On all successful/skip outcomes, extend the staged lock record and publish
   the normal spaex generation. On failure, keep the previous spaex generation
   and emit a typed diagnostic; do not attempt to delete external files.
9. On molecule removal, omit the record and emit the external-artifact warning
   without invoking Spec Kit uninstall.

### Source structure

```text
src/spaex/
├── cli/
│   ├── main.py                 # install/add flags and dispatch values
│   ├── install.py              # orchestration boundary before publication
│   └── add.py                  # forward selection/options to internal install
├── integrations/
│   └── speckit.py              # official CLI adapter, selection, outcomes
├── model/
│   ├── molecule_manifest.py    # SpeckitDeclaration parsing
│   └── install_lock.py         # published Spec Kit lock record
└── schema/data/
    ├── molecule-manifest.v4.schema.json
    └── install-lock.v4.schema.json

tests/
├── contract/
│   ├── test_molecule_manifest_speckit.py
│   └── test_install_lock_speckit.py
├── unit/
│   └── test_speckit_integration.py
└── integration/
    ├── test_speckit_installation.py
    ├── test_speckit_selection.py
    └── test_speckit_failure_boundary.py
```

### Contracts

The public contracts are:

- [Molecule Spec Kit declaration](contracts/molecule-manifest-speckit.v1.md)
- [spaex CLI surface and diagnostics](contracts/speckit-cli-surface.md)
- [install-lock record](contracts/install-lock-speckit.v1.md)

### Test strategy

- Contract tests validate strict manifest and lock schemas, forbidden global
  options, invalid constraints, duplicate/unknown selections, and canonical
  ordering.
- Unit tests validate version parsing, declaration fingerprints, selection
  precedence, no-op comparison, command argv construction, and outcome mapping.
- Integration tests use a fake executable on `PATH` that records argv and writes
  project-local markers. They verify successful installation, repeat no-op,
  selected-agent delta, non-interactive refusal, opt-out, missing CLI,
  incompatible version, unsupported key, partial external failure, and remove
  warning.
- A live CLI smoke test remains opt-in and read-only by default; it must not
  modify the current repository's real agent directories during normal tests.

## Constitution Check — Post-Design

- **Immutable references**: PASS. The publisher molecule remains full-SHA
  pinned, and CLI policy disallows mutable version references.
- **No arbitrary hook path**: PASS. Spec Kit uses a typed runner and no
  publisher-provided script.
- **Atomicity honesty**: PASS. The plan explicitly preserves the prior spaex
  generation on failure but does not promise rollback for external agent files.
- **No agent-specific reimplementation**: PASS. Destination layout and managed
  file behavior stay with the official `specify` CLI.
- **No unresolved clarifications**: PASS. The spec and research choose project-
  local scope, lock-owned selection, preinstalled CLI, and serial invocation.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Typed `speckit` molecule declaration | A normal capability needs schema validation, selection, lock provenance, and conflict rules. | A generic `install_hook` would hide the capability behind arbitrary code and lose structured validation. |
| Dedicated subprocess adapter | The official CLI is an external process with version/output/error semantics. | Calling `subprocess.run` directly from `install.py` would duplicate orchestration and make unit testing harder. |
| Per-molecule lock record | Selection and idempotence must be tied to the declaration that owns the integration. | A global unscoped agent map would create ownership conflicts between molecules. |
