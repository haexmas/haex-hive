# Implementation Plan: Cross-Repo References (Phase 1)

**Branch**: `004-cross-repo-refs` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-cross-repo-refs/spec.md`
**Design authority**: [docs/plans/2026-08-27-spec-004-cross-repo-refs-design.md](../../docs/plans/2026-08-27-spec-004-cross-repo-refs-design.md)

## Summary

Ship the Phase 1 mechanism for haex-hive-opted-in repositories to reference
and consume harness content pinned in Git repositories by immutable SHA.
Land as a small Python-stdlib resolver tool (`spec-resolve`) with three
subcommands (`resolve`, `prefetch`, `status`), a unified `harness_sources`
array in `.haex-hive.json` (collapsing the earlier split `constitution`
slot + `external_sources.allowed` list from Spec 003), a canonical JSON
Schema, and the enforcement logic required by Constitutional Principles
IV and V. The retired `.specify/system.yaml` disappears; the constitution
receives a PATCH-bump (v1.1.0 → v1.1.1) rewriting Principle V's wording
to cite the new location. All open design decisions have been resolved
via `/speckit.clarify` (5 questions, session 2026-08-27); no NEEDS
CLARIFICATION remains at the plan level.

## Technical Context

**Language/Version**: Python 3.10+ (stdlib only — `json`, `subprocess`,
`hashlib`, `pathlib`, `argparse`, `os`, `sys`, `re`). Chosen for JSON/CLI
ergonomics without third-party deps.
**Primary Dependencies**: Git 2.30+ (invoked via `subprocess`). Nothing
else.
**Storage**: Per-user object cache under `~/.cache/haex-hive/repos/<repo-hash>/`
(XDG-compliant; honors `$XDG_CACHE_HOME`; falls back to
`~/Library/Caches/haex-hive/` on macOS when Phase-2/3 satellites appear).
Bare-clone-shaped Git object directories, populated on demand.
**Testing**: Shell-driven tests under `tests/` invoking the tool against
synthetic Git fixtures built at test-setup with `git init` + commits.
No pytest / no test framework — plain bash + `set -e` + `[[ ]]`
assertions. Rationale: matches Spec 001–003's shell-driven validation
pattern; no runtime dep just to run tests.
**Target Platform**: Linux (primary; validated in Spec 004). macOS and
Windows/WSL2 deferred per spec Assumptions.
**Project Type**: CLI tool + versioned config schema. Not a service, not
a library.
**Performance Goals**: Session-start prefetch of ~1 pinned reference
(the constitution self-ref today) MUST complete in < 500ms cached,
< 5s cold on typical broadband. Validation of `.haex-hive.json`
< 50ms. These are engineering budgets, not user-facing metrics.
**Constraints**: Offline-safe when cache populated (Constitutional
Principle VII spirit). No secrets in cache (Principle I). No absolute
local paths in any committed file (Principle II). SHA pinning
enforced in refs (Principle IV). Allowlist-gated external sources
(Principle V).
**Scale/Scope**: One CLI tool (~200-400 LOC target), one JSON Schema
(~80 LOC), one migration of `.haex-hive.json` (one file), constitution
PATCH (Principle V wording only), snippet extension (one added step).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version referenced: `v1.1.0` at commit `406fc78`
(as pinned in `.haex-hive.json`, verified via
`git show 406fc78:.specify/memory/constitution.md`).

| Principle | Check | Verdict |
|-----------|-------|---------|
| I — No Secrets in Git | The cache is per-device (never versioned). The tool ships no credentials. Fetched Git objects contain only what upstream committed. | **PASS** |
| II — No Local Absolute Paths in Versioned Config | `.haex-hive.json` accepts only URLs and the `"self"` keyword (Q3 answer). Cache path lives in per-device `~/.cache/`, unversioned. Schema at repo-relative `.specify/schemas/haex-hive.schema.json`. | **PASS** |
| III — Project Identity Is Device-Independent | `.haex-hive.json`'s `identity` field is unchanged. No local paths cross the version-boundary. Cache dir named by `hash(repository-string)`, not path. | **PASS** |
| IV — Cross-Repo References Pin Immutable Revisions | `revision` field pattern is `^[0-9a-f]{7,40}$` — SHA only (Q5 answer). Branch/HEAD references rejected at load-time. `"self"` disallowed in `revision`. | **PASS** |
| V — External Sources Are Opt-in Per Project | Empty `harness_sources` → resolver refuses everything (spec edge case). Any non-`self` reference requires a matching allowlist entry (FR-008). Constitution PATCH updates the wording to cite `harness_sources`. | **PASS** |
| VI — Self-Modifying Instructions Are Always Review-Gated | Spec 004 ships no auto-modification path. The design-doc's `bump` command is explicitly deferred to Spec 005. This plan's changes to `.haex-hive.json`, constitution, and snippet are all reviewable Git commits. | **PASS** |
| VII — Relay Unavailability Never Blocks Local Work | Resolver is offline-safe when cache is populated (FR-015, edge case). Snippet fetches only if network is available and cache is missing; otherwise refuses cleanly, never hangs. No relay involvement. | **PASS** |
| VIII — No Concealment Instructions in Agent Output | Spec 004 emits no agent-facing instructions at all; the tool prints resolved content, cache metadata, and error messages — none of which instruct downstream readers to hide anything. | **PASS** |

**Result**: No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/004-cross-repo-refs/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec (already exists)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output — entities + schema
├── quickstart.md        # Phase 1 output — fresh-clone walkthrough
├── contracts/           # Phase 1 output
│   ├── spec-resolve.cli.md            # CLI command contracts
│   └── haex-hive.schema.draft.json    # Draft JSON Schema (canonical goes to .specify/schemas/)
├── checklists/
│   └── requirements.md  # From /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

Spec 004 adds:

```text
.specify/
├── schemas/
│   └── haex-hive.schema.json      # NEW — canonical JSON Schema
└── scripts/
    └── spec-resolve                # NEW — executable Python entry
                                    #   (or spec-resolve.py + wrapper; see research)

tests/
└── spec-resolve/                   # NEW — shell-driven test harness
    ├── fixtures/
    │   ├── build-fixtures.sh       # builds synthetic git fixtures
    │   └── ...                     # generated fixture repos (gitignored inside)
    ├── test-resolve.sh
    ├── test-prefetch.sh
    ├── test-status.sh
    ├── test-allowlist-refusal.sh
    ├── test-schema-tool-agreement.sh
    └── run-all.sh                  # entry point

docs/
└── spec-resolve.md                 # NEW — user-facing docs
                                    #   (command surface, cache, IDE mapping)
```

Spec 004 modifies:

```text
.haex-hive.json                     # unified harness_sources; constitution slot removed
.specify/system.yaml                # REMOVED
.specify/memory/constitution.md     # Principle V wording; v1.1.1 stamp
CLAUDE.md                           # SPECKIT block: plan reference update
```

Spec 004 does NOT touch:

- Anything under `specs/001-*/`, `specs/002-*/`, `specs/003-*/` (historical).
- Anything under `.specify/extensions/` (spec-kit's territory).
- Anything under `docs/adr/` — except for one new ADR (see research.md).

**Structure Decision**: Single-project layout (Option 1 from the
template). No frontend/backend or mobile split — this is a repo-local CLI
tool + config schema + doc changes. The `.specify/scripts/` location for
`spec-resolve` mirrors where spec-kit itself keeps `create-new-feature.sh`
and `check-prerequisites.sh`; the JSON Schema lives adjacent under
`.specify/schemas/` (new subdirectory).

## Complexity Tracking

Not applicable — Constitution Check passed without violations. Table
intentionally left empty.

## Post-design re-check (after Phase 1)

Re-run the Constitution Check gate after Phase 1 artifacts land (data
model, contracts, quickstart). Recorded here for traceability rather
than as a separate gate:

- All Phase 1 artifacts must respect Principles I–VIII as verified above.
- `data-model.md` MUST NOT introduce new fields that would allow SHA-less
  refs or unbounded scopes (would violate IV/V).
- `contracts/` MUST NOT introduce a "quiet mode" or "output-suppress"
  flag that could hide content from the operator (would border on VIII).
- `quickstart.md` MUST include the fresh-clone/offline-second-run flow
  (proves VII compliance).

Post-design result: **PASS** (see the Phase 1 artifacts committed
alongside this plan).
