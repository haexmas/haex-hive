# Implementation Plan: Multi-Spec External-Ref

**Branch**: `006-multi-spec-external-refs` | **Date**: 2026-08-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/006-multi-spec-external-refs/spec.md`
**Design source of truth**: [`docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md`](../../docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md)

## Summary

Consumer projects declare inheritance from external speckit-shaped
producer repositories through a new `role: "external-harness"` entry in
`.haex-hive.json`, with per-producer item lists, coarse `auto_include:
"speckit-defaults"` preset, and explicit `additional_include`
opt-ins. The producer is cloned in full (no shallow) to a device-local
haex-hive state area (`$HAEX_HIVE_STATE/repos/<name>/`) and content is
resolved at pinned revisions via content-addressed extract directories
(`.extracts/@<sha>/…`) using `git show <sha>:<path>`. A gitignored,
device-local `.haex-hive.local.json` maps deterministic
consumer-facing keys to absolute filesystem paths — Path-Return,
Windows-portable, no copying into the consumer repo. Two new
`haex-init` sub-commands (`sync` and `add-source`) drive the operator
workflow. Speckit's own template/workflow lookups are NOT overridden
by producer content. Spec-004 legacy references continue to work
unchanged via dual-store compatibility.

## Technical Context

**Language/Version**: Python 3.10+ (extending existing
`.specify/scripts/haex-init` and `.specify/scripts/spec-resolve`,
both single-file stdlib-only Python established in Spec 005).
**Primary Dependencies**: Git ≥ 2.30 on `$PATH`. Python stdlib only
(json, hashlib, pathlib, subprocess, shutil, os, sys, argparse,
tempfile, fcntl on Unix / msvcrt on Windows for the directory-scoped
lock, urllib.parse for URL validation). No third-party runtime
dependencies. Follows Spec 005's constraint.
**Storage**: Consumer-committed files: `.haex-hive.json` (unchanged
location, extended schema). Device-local: `$HAEX_HIVE_STATE/repos/<name>/`
= full producer clones + per-SHA content-addressed extracts. Consumer
device-local: `.haex-hive.local.json` (gitignored). Spec-004
`$XDG_CACHE_HOME/haex-hive/repos/<hash>/` remains authoritative for
legacy references (dual-store per FR-034).
**Testing**: Shell scripts (bash) using local bare-repo fixtures, no
network dependency (same pattern as Spec 004's `tests/`, Spec 005's
`tests/haex-init/`). New test root: `tests/multi-spec-external-ref/`.
Fixture producer setup mirrors Spec 004 patterns.
**Target Platform**: Linux mechanical target (mechanical validation).
macOS + Windows-under-WSL2 receive smoke validation in a
`.validation-runs/` document, not gating the merge (per A9).
**Project Type**: Single-project CLI extension. Extends existing
Python CLIs (`haex-init` sub-commands, `spec-resolve` sub-commands).
No new project directories; new tests directory, new spec/design
files under `specs/006-.../`.
**Performance Goals**: See SC-002 (`sync` idempotent under 1 second),
SC-007 (rename-refuse diagnostic under 5 seconds), SC-010 (full test
suite under 2 minutes). No throughput requirements — CLI is
operator-invoked, not high-frequency.
**Constraints**: Windows-portability by construction (no symlinks,
no junctions, no bind mounts — FR-036). Cross-user privacy on
Unix-like systems (FR-038 owner-only permissions). Backwards
compatibility with Spec 004 shape (FR-033 through FR-035). Structured
stderr diagnostics for every failure (FR-026, FR-037).
**Scale/Scope**: Producer repos assumed < 500 MB full history (A2).
No hard upper bound on `items[]` or `additional_include` list size in
the spec, but bounded in practice by producer content size.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.2.0 — eight NON-NEGOTIABLE principles checked below.

| Principle | Status | Justification |
|---|---|---|
| I. No Secrets in Git | ✅ Pass | Config carries repository refs and pinned SHAs only. FR-007 rejects HTTPS URLs with embedded userinfo before writing, so no credential material enters version-controlled state. |
| II. No Local Absolute Paths in Versioned Config | ✅ Pass | `.haex-hive.json` remains free of local paths. `.haex-hive.local.json` IS device-local absolute paths — but is gitignored (FR-018) and per-device by construction (each device generates its own). |
| III. Project Identity Device-Independent | ✅ Pass | Producer identity is the git remote URL. `.haex-hive.json` never carries a local filesystem path or device identifier. |
| IV. Cross-Repo References Pin Immutable Revisions | ✅ Pass | Every `external-harness` entry MUST pin a full 40-char SHA (FR-002, FR-029). No branch/HEAD references introduced. The device-local clone's working tree tracks producer's HEAD only for operator browsing (FR-015-016) — never consulted by `spec-resolve` or Path-Return; content always read via `git show <sha>:<path>` from extracts. |
| V. External Sources Are Opt-in Per Project | ✅ Pass | `harness_sources[]` remains the sole trust boundary (FR-009). Coarse `auto_include: "speckit-defaults"` is still an explicit consumer opt-in ("I opt into this producer's speckit-defaults set at this SHA"). Producer-side manifests were explicitly rejected in the design (D1). |
| VI. Self-Modifying Instructions Review-Gated | ✅ Pass | `.haex-hive.local.json` is device-local, gitignored, regenerated from committed config — not self-modifying instructions. `haex-init add-source` writes to `.haex-hive.json`, but this is exactly the review-gated act the constitution expects: the operator invokes it, reviews the diff, commits through the PR flow required by v1.2.0's Development Workflow. |
| VII. Relay Unavailability Never Blocks Local Work | ✅ Pass | Nostr relay not touched. Every operation works offline against local disk once producers are cloned. `haex-init sync` requires network only on first fetch of an unseen pinned SHA. |
| VIII. No Concealment Instructions in Agent Output | ✅ Pass | Feature produces no agent-facing output that could conceal information. Session-start snippet embeds inherited Constitution content byte-for-byte with fixed source labels between documents (FR-011) — transparency by construction. |

**Result**: All eight principles pass. No Complexity Tracking
justifications required.

## Project Structure

### Documentation (this feature)

```text
specs/006-multi-spec-external-refs/
├── plan.md              # This file (/speckit-plan output)
├── research.md          # Phase 0 output (see below)
├── data-model.md        # Phase 1 output (see below)
├── quickstart.md        # Phase 1 output (see below)
├── contracts/           # Phase 1 output (see below)
│   ├── haex-init-sync.cli.md
│   ├── haex-init-add-source.cli.md
│   ├── haex-hive.schema.json.patch.md
│   └── haex-hive-local.schema.json.md
├── checklists/
│   └── requirements.md  # from /speckit-specify
├── spec.md              # from /speckit-specify + /speckit-clarify
└── tasks.md             # Phase 2 output (created by /speckit-tasks — NOT here)
```

### Source Code (repository root)

Extends the existing Spec 005 Python CLI layout — no new project
scaffolding.

```text
.specify/
├── scripts/
│   ├── haex-init                # extended: new sub-commands `sync`, `add-source`; new state-area handling
│   ├── spec-resolve             # extended: new external-harness expansion, path-return via .haex-hive.local.json
│   └── bash/                    # unchanged
├── schemas/
│   ├── haex-hive.schema.json    # extended: discriminated harness_sources entries (external-harness added)
│   └── haex-hive-local.schema.json  # NEW: validates .haex-hive.local.json
├── templates/                   # unchanged
├── memory/
│   └── constitution.md          # unchanged (v1.2.0 already landed)
└── workflows/                   # unchanged

tests/
└── multi-spec-external-ref/     # NEW: shell-test root, mirrors tests/haex-init/ pattern
    ├── run-all.sh
    ├── fixtures/                # bare-repo producer fixtures
    ├── lib/                     # shared test helpers
    ├── test-fresh-external-harness.sh
    ├── test-auto-include-speckit-defaults.sh
    ├── test-additional-include.sh
    ├── test-additional-include-expansion.sh
    ├── test-explicit-items-aliases.sh
    ├── test-storage-identity-and-origin.sh
    ├── test-atomic-sync-publication.sh
    ├── test-legacy-cache-compatibility.sh
    ├── test-constitution-order.sh
    ├── test-sha-bump-clean.sh
    ├── test-sha-bump-rename-refuses.sh
    ├── test-add-source-fresh.sh
    ├── test-add-source-from-repo.sh
    ├── test-auth-error-clarity.sh
    ├── test-file-permissions.sh          # NEW: covers FR-038 (owner-only)
    ├── test-sync-exit-codes.sh           # NEW: covers FR-027a (0-4 scheme)
    └── test-alias-grammar-validation.sh  # NEW: covers FR-006 (kebab-case slug)

docs/
├── multi-spec-external-ref.md   # NEW: operator documentation for the feature
├── adr/                         # NO new ADR expected — design doc + spec cover the material
└── plans/
    └── 2026-08-28-spec-006-multi-spec-external-refs-design.md  # authoritative design (landed via PR #6)
```

**Structure Decision**: Single-project CLI extension. The feature adds
sub-commands to the existing `haex-init` and `spec-resolve` binaries
(one Python file each, extended in place per Spec 005's
single-file-stdlib-only constraint), extends the JSON Schema, adds
one new JSON Schema for the local-state file, and adds a
sibling test root under `tests/multi-spec-external-ref/`. No new
top-level source-code directories, no new package boundaries, no
third-party runtime dependencies.

### Agent context update

The repository has no root-level `CLAUDE.md` or `AGENTS.md` file, so
the plan-reference marker-block update step in `/speckit-plan` step
3 is a no-op for this repo. Operator agent-instructions live in the
constitution and are pulled through the user-global session-start
snippet by design (Constitution v1.2.0 §Development Workflow scope).

## Complexity Tracking

*Empty — Constitution Check passed with no violations.*

## Post-Phase-1 Constitution Re-Check

*Filled after Phase 1 artifacts (data-model.md, contracts/,
quickstart.md, research.md) are complete.*

The design remains constitution-compliant after Phase 1 detail-work.
No new violations introduced; no `Complexity Tracking` entries added.
See §Constitution Check above for the enumerated pass reasons — none
of the Phase-1 artifacts weaken any of them.

- **FR-006 alias grammar** (kebab-case slug `^[a-z0-9][a-z0-9-]*$`)
  and **FR-020 resolved-key convention** (`<name>:<alias>` for
  explicit items, `<name>:path:<repo-relative-path>` for include
  expansions) are captured in the data model (§Resolved Keys) and in
  `contracts/haex-hive.schema.json.patch.md`; both mechanically enforce
  Principle V's "opt-in per project" trust boundary by making every
  key deterministically derivable from the consumer's own
  declaration.
- **FR-027a exit-code scheme** and **FR-038 file-permissions posture**
  are captured in `contracts/haex-init-sync.cli.md`; neither
  introduces a new principle-relevant surface.
- **FR-034 dual-store compatibility** (Spec-004 cache remains
  authoritative for legacy references) is captured in the data model
  and in `research.md` (Decision 5); this preserves the byte-for-byte
  compatibility promised by SC-008 and by extension Principle IV's
  "byte-identical spec content across satellites" rationale.

Constitution Check result **post-Phase-1**: ✅ Pass. All eight
NON-NEGOTIABLE principles remain honoured. No Complexity Tracking
justifications required.
