# Phase 0 Research: Pilot Harness Prerequisites

**Feature**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Date**: 2026-08-26

Three items were left open by the spec and plan. Resolved here.

## Decision 1: Which second CLI for the cross-tool handoff test

**Decision**: Codex CLI.

**Rationale**: `codex-cli 0.147.0` is installed and runnable on this machine
at `~/.local/bin/codex`; `codex doctor` reports a healthy install with a
consistent standalone runtime. The spec's default assumption (Codex) holds
without a substitution, so `spec.md` FR-006 is satisfied with the primary
choice, not the fallback.

**Alternatives considered**: `goose` is also available on the validation
machine and would be a valid substitute per FR-006's "any other supported CLI
listed by the spec-kit `--ai` options" clause. It is kept as an available
fallback if Codex fails during validation for any reason (auth, network,
upstream change) — the switch is documented but not exercised.

**Ratified as**:
[ADR 0001 — Codex as the second validation CLI](../../docs/adr/0001-codex-as-second-cli.md).

## Decision 2: What per-tool adapter file does Codex read at the repo root

**Decision**: `AGENTS.md` at the repository root.

**Rationale**: `AGENTS.md` is Codex CLI's documented convention for
per-project agent instructions, the same slot `CLAUDE.md` occupies for Claude
Code. spec-kit's own `--ai codex` support (visible in `specify init --help`)
confirms `AGENTS.md` is the file spec-kit's Codex integration writes and
expects. The fresh-session validation checklist (quickstart) will exercise
this — if the test in User Story 1's second acceptance scenario fails
because Codex does not in fact read `AGENTS.md`, that is a real finding
against the assumption and must be corrected before the feature can be marked
complete.

**Alternatives considered**: `codex.md` and `codex/instructions.md` were
considered but neither is a Codex convention — `AGENTS.md` is. No alternative
is a serious contender.

## Decision 3: Symlink or thin-reference for the adapter files

**Decision**: symlink both `CLAUDE.md` and `AGENTS.md` to
`.specify/memory/constitution.md`.

**Rationale**: this Linux workstation supports symlinks trivially. Symlinking
maximises the "single source of truth" property — a change to the constitution
is visible immediately through both adapters with zero drift risk, no compile
step, and no chance of the two adapter files diverging. This matches the
design doc's stated approach for pure-instruction files.

Caveat: `CLAUDE.md` currently exists at the repo root as a thin real file
containing the `<!-- SPECKIT START -->…<!-- SPECKIT END -->` marker block
produced by `specify init`. Replacing it with a symlink to the constitution
would strip that marker block, and future `specify` commands may depend on
that block being editable text. The tension is resolved in favour of the
thin-reference form for `CLAUDE.md` specifically: keep the existing file,
update the block to point at the plan/constitution, and add a short line
directing the reader to the canonical constitution and the active spec.
`AGENTS.md` has no such constraint and is created as a real symlink to
`.specify/memory/constitution.md`.

**Alternatives considered**:

1. *Both files as real thin-reference files*. Rejected because it introduces
   two places where the "read the canonical instruction" instruction has to
   be spelled out, and drift risk is nonzero.
2. *Both files as symlinks*. Rejected for `CLAUDE.md` only because of the
   spec-kit marker-block constraint noted above. If a future spec-kit
   version removes that constraint, this decision should be revisited and
   `CLAUDE.md` promoted to a symlink too.
3. *Both files as symlinks to a new `HARNESS.md` at repo root that itself
   contains the imports*. Rejected as an unnecessary layer — the constitution
   is already the canonical file; a second canonical file would be
   duplication for no gain.

## Filesystem/platform notes captured for the future

For future contributors on constrained filesystems (Windows without
Developer Mode, network mounts that flatten symlinks): the symlink for
`AGENTS.md` is a nicety, not a hard requirement. On a filesystem where
symlinks are unavailable, `AGENTS.md` MUST be produced as a real thin-
reference file whose entire body is a pointer to
`.specify/memory/constitution.md` and to `specs/001-phase-0-pilot-harness/plan.md`.
The fresh-session test in User Story 1 remains valid in either shape — what
the agent reads is the same content, just via a different filesystem
mechanism.
