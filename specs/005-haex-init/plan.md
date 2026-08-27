# Implementation Plan: `haex-init` — CLI-Driven Project Initialization

**Branch**: `005-haex-init` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-haex-init/spec.md`

## Summary

Ship a single standalone Python 3.10+ stdlib CLI, `haex-init`, that a new
operator downloads and runs inside their project directory to bootstrap
haex-hive adoption in one interactive pass. The tool covers:

- Two-signal detection of installed LLM tooling (Claude Code, Codex,
  Gemini) and IDE tooling (VSCode-family, JetBrains-family) with a
  multi-select prompt and `--include` override.
- Operator-level setup: `~/.haex-hive/haex-hive.md` from an embedded
  canonical instructions constant, `~/.haex-hive/VERSION`, and surgical
  marker-wrapped reference blocks appended (or replaced on version
  mismatch) into the operator's per-tool user-global config files.
- Project-level setup in two mutually exclusive modes: **self-ref**
  (writes `.haex-hive.json` with `harness_sources: []`, no constitution
  file — operator runs `/speckit-constitution` + `haex-init
  --pin-constitution` afterwards) and **external-ref** (writes
  `.haex-hive.json` with a single `role: "constitution"` entry
  pointing at a pre-verified external repository triple).
- Idempotent re-run with `--dry-run` and `--yes` modes; strict
  refusal of any change outside marker boundaries; version-aware
  block replacement gated by unified-diff preview.
- Follow-up `--pin-constitution` sub-mode: adds the
  `role: "constitution"` entry to `.haex-hive.json` at HEAD SHA once
  the operator has authored the constitution content, and offers a
  follow-up commit.

The tool ships next to `spec-resolve` in `.specify/scripts/haex-init`.
It has no runtime dependency on the haex-hive repo — the canonical
session-instructions text is embedded as a string constant with a
CI-enforced byte-identity guarantee against
`.specify/templates/haex-hive-session-instructions.md`. Testing follows
Spec 004's shell-driven pattern with the added isolation guarantee that
every filesystem access under `$HOME` resolves into a fake sandbox.

All open design decisions have been resolved via `/speckit-clarify`
(4 questions, session 2026-08-27); no NEEDS CLARIFICATION remains at
the plan level.

## Technical Context

**Language/Version**: Python 3.10+ (stdlib only — `argparse`, `json`,
`os`, `sys`, `re`, `pathlib`, `subprocess`, `shutil`, `difflib`,
`hashlib`, `tempfile`). Chosen to match `spec-resolve` and to keep the
tool a single self-contained file the operator can wget.
**Primary Dependencies**: Git 2.30+ (invoked via `subprocess`) for
external-ref verification and for the optional scaffolding commit.
Nothing else.
**Storage**: Two on-disk regions:
  1. **User-global**: `~/.haex-hive/haex-hive.md` and
     `~/.haex-hive/VERSION` (per operator, per machine).
  2. **Ephemeral scratch cache**: `$XDG_CACHE_HOME/haex-init/verify/`
     (default `~/.cache/haex-init/verify/`) — used only by
     external-ref mode to run the pre-write git fetch that verifies
     `(url, sha, path)` before touching `.haex-hive.json`. Deliberately
     separate from `spec-resolve`'s `~/.cache/haex-hive/repos/` cache
     so that a haex-init verification-fetch does not silently populate
     the operator's runtime resolver cache.
**Testing**: Shell-driven under `tests/haex-init/`, following the
Spec 004 pattern. Every test runs in an isolation sandbox
(`HOME=$TMPDIR/fake-home`, `PATH=$TMPDIR/fake-bin:…` with fake
executables). Fixture builder mirrors
`tests/spec-resolve/fixtures/build-fixtures.sh`. No pytest.
**Target Platform**: Linux (primary; validated in Spec 005). macOS and
Windows/WSL2 deferred per spec Assumptions.
**Project Type**: Single CLI tool. Not a service, not a library.
**Performance Goals**: Interactive prompts respond within one animation
frame of operator input (<50ms). Full self-ref init (no external
network) completes in under 3 seconds wall-clock excluding operator
prompt-reading time. `--dry-run` (no writes, no network) completes in
under 1 second. External-ref verification fetch bounded by network,
targets a 30 s soft-cap.
**Constraints**: Every write Y/N-gated with diff preview (Principle
VI review-gate spirit); no absolute local paths committed (Principle
II); external-ref URL scheme allowlist same as `spec-resolve`
(Principle IV/V spirit); user-global patches are byte-safe outside
markers (SC-002); the tool ships no credentials and reads no secrets
(Principle I). No `--force` flag — deliberate cleanup is manual.
**Scale/Scope**: One CLI tool (~500-800 LOC target — larger than
`spec-resolve` because it has more surfaces to touch); one embedded
schema constant identical to `.specify/schemas/haex-hive.schema.json`;
one embedded canonical session-instructions constant;
`.specify/templates/haex-hive-session-instructions.md` as the
source-of-truth for that constant (new file created by this spec);
one shell test suite (~10 tests); one operator-facing doc file
`docs/haex-init.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution version referenced: `v1.1.1` at commit `dd80f6f`
(as pinned in `.haex-hive.json`, verified via
`git show dd80f6f:.specify/memory/constitution.md`).

| Principle | Check | Verdict |
|-----------|-------|---------|
| I — No Secrets in Git | Tool ships no credentials, reads no secrets. External-ref mode invokes `git fetch` against operator-provided URLs; any auth (SSH agent, git credential helper) is the operator's, not haex-init's, and stays out of the tool. | **PASS** |
| II — No Local Absolute Paths in Versioned Config | `.haex-hive.json` writes only `"self"` or an accepted-scheme URL for `repository`, `^[0-9a-f]{7,40}$` for `revision`, and repo-relative paths for `path`. Embedded schema constant is byte-identical to the canonical repo copy. Marker block references `~/.haex-hive/haex-hive.md` (a per-machine known location, not a committed path). | **PASS** |
| III — Project Identity Is Device-Independent | Tool creates and reads `.haex-hive.json`; the file's `identity` field (from Spec 003) is unchanged. No path-based identity introduced. External-ref triple is a device-independent Git object address. | **PASS** |
| IV — Cross-Repo References Pin Immutable Revisions | External-ref mode enforces `^[0-9a-f]{7,40}$` at input-validation time (pre-network) and re-verifies the SHA is reachable at the URL before writing. `--pin-constitution` reads `HEAD`'s full SHA via `git rev-parse HEAD` and writes that exact value. Branch/tag/`HEAD` string references are impossible to write through the tool. | **PASS** |
| V — External Sources Are Opt-in Per Project | Self-ref mode writes `harness_sources: []` (the constitutionally-consistent "opted in, no permissions granted" state); external-ref mode writes exactly the one entry the operator confirmed. No implicit inheritance, no defaults from environment. `haex-init` never edits `.haex-hive.json` in response to any "apply this" prompt — only in response to explicit `--pin-constitution` or the initial init flow. | **PASS** |
| VI — Self-Modifying Instructions Are Always Review-Gated | Every write (both user-global and project-local) is Y/N-gated with a unified-diff preview. `--yes` bypasses only in scripted contexts the operator explicitly enters. No auto-writes. No amendments to the constitution or its references happen through `haex-init`. | **PASS** |
| VII — Relay Unavailability Never Blocks Local Work | Self-ref mode is entirely offline. External-ref mode requires network only for the pre-write verification fetch; when the network is down, verification fails cleanly, no partial state on disk, operator can retry later. `--dry-run` never touches the network. No relay involvement anywhere. | **PASS** |
| VIII — No Concealment Instructions in Agent Output | Tool prints an explicit action-report at the end of every run listing exactly what was done and what was skipped. No hide-instructions in prompts, block content, next-step guidance, or error messages. The embedded canonical session-instructions carry no concealment directives (verified by the sync test). | **PASS** |

**Result**: No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/005-haex-init/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature spec (already exists)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output — entities + state machine
├── quickstart.md        # Phase 1 output — fresh-operator walkthrough
├── contracts/           # Phase 1 output
│   ├── haex-init.cli.md            # CLI command / prompt / exit-code contract
│   ├── marker-block.format.md      # marker block syntax + versioning contract
│   ├── haex-hive.md.template.md    # canonical session-instructions template contract
│   └── ide-mapping.format.md       # VSCode / JetBrains mapping-file contract
├── checklists/
│   └── requirements.md  # From /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

Spec 005 adds:

```text
.specify/
├── scripts/
│   └── haex-init                       # NEW — executable Python entry
└── templates/
    └── haex-hive-session-instructions.md
                                        # NEW — canonical instructions source
                                        #   (embedded byte-identical inside haex-init)

tests/
└── haex-init/                          # NEW — shell-driven test harness
    ├── lib/
    │   └── sandbox.sh                  # HOME + PATH isolation helpers
    ├── fixtures/
    │   ├── build-fixtures.sh           # builds synthetic homes + fake bins + bare repo
    │   └── ...                         # generated fixtures (gitignored)
    ├── test-fresh-operator.sh
    ├── test-idempotent-rerun.sh
    ├── test-partial-state.sh
    ├── test-marker-safety.sh
    ├── test-version-upgrade.sh
    ├── test-dry-run.sh
    ├── test-self-ref.sh
    ├── test-pin-constitution.sh
    ├── test-external-ref.sh
    ├── test-embedded-content-sync.sh
    └── run-all.sh                      # entry point

docs/
└── haex-init.md                        # NEW — operator-facing docs
                                        #   (install, command surface, edge cases,
                                        #   manual editor setup for non-detected IDEs)

.validation-runs/
└── haex-init-real-remote.md            # NEW — manual smoke test log
                                        #   (external-ref against a real public repo)
```

Spec 005 does NOT modify:

- `.haex-hive.json` in this repo (this repo's config is already correct
  from Spec 004; `haex-init` is written and tested here but not
  re-invoked against this repo).
- The canonical JSON Schema at `.specify/schemas/haex-hive.schema.json`
  — `haex-init`'s embedded constant is byte-identical to it, enforced
  by a sync check in the test suite.
- Anything under `specs/001-*/` through `specs/004-*/` (historical).
- Anything under `.specify/extensions/` (spec-kit's territory).
- `.specify/scripts/spec-resolve` — unchanged; `haex-init` runs it in
  self-ref tests only as a post-condition check.

**Structure Decision**: Single-project layout (Option 1). Matches
Spec 004 precedent: repo-local CLI tool + tests + docs. No frontend/
backend split. `.specify/scripts/haex-init` lives adjacent to
`spec-resolve` so operators discover both together.
`.specify/templates/haex-hive-session-instructions.md` is a new
directory because it is a source-of-truth text file, not a script.

## Complexity Tracking

Not applicable — Constitution Check passed without violations. Table
intentionally left empty.

## Post-design re-check (after Phase 1)

Re-run the Constitution Check gate after Phase 1 artifacts land (data
model, contracts, quickstart). Recorded here for traceability:

- All Phase 1 artifacts must respect Principles I–VIII as verified above.
- `data-model.md` MUST NOT introduce state that lets the tool bypass
  the Y/N-gate on any write (would violate VI).
- `contracts/haex-init.cli.md` MUST NOT introduce a "quiet mode" that
  suppresses the action-report at the end of a run (would border on
  VIII); `--yes` may skip prompts but MUST NOT skip the report.
- `contracts/marker-block.format.md` MUST specify that the block is
  the ONLY territory the tool writes to inside a user-global config
  file, and that a version-mismatched block requires an explicit
  operator Y before replacement (proves VI compliance).
- `quickstart.md` MUST include the self-ref + `--pin-constitution`
  walkthrough (proves SC-001a + SC-001b together).

Post-design result: **PASS** (see the Phase 1 artifacts committed
alongside this plan).
