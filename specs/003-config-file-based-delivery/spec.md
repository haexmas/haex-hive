---
description: "Config-file-based delivery of the haex-hive harness via `.haex-hive.json` opt-in and a global instruction snippet, replacing committed CLAUDE.md/AGENTS.md."
---

# Spec 003 — Config-file-based Delivery of the haex-hive Harness

**Status**: DRAFT after validation. All success criteria PASS in the
2026-08-27 validation run. Ready for review + merge.

## Summary

Replace the pilot-era practice of committing `CLAUDE.md` and `AGENTS.md`
adapter files at the repo root with a per-repo `.haex-hive.json` opt-in
marker plus a global instruction snippet each operator installs in their
own CLI's user-level config. Repos that do not carry the marker are
untouched. Repo-local `CLAUDE.md` / `AGENTS.md` files are respected
additively; conflicts with the constitution are surfaced to the operator
rather than silently resolved.

## Motivation

The pilot harness (spec 001) committed a `CLAUDE.md` file with a `<!--
SPECKIT ... -->` block and an `AGENTS.md` symlink to the constitution at
the repo root. That approach forced the haex-hive workflow on every
future contributor to the repo — anyone opening the repo with any
compatible CLI would auto-load the harness, whether they had opted in or
not. Repo-local instruction files are the repo owner's territory and
must not be commandeered by an external harness. Spec 003 corrects that
by making opt-in a marker file the repo owner explicitly chose to commit,
and by moving the detection logic to the operator's own user-level config.

## User Stories

### US1 — Opt-in to haex-hive by committing `.haex-hive.json`

**As** a repo owner, **I want** to opt this repo into the haex-hive
harness **so that** any operator using a CLI with the detection snippet
installed will treat the repo's canonical constitution as binding.

Acceptance: a fresh CLI session opened in a repo containing
`.haex-hive.json` reads the file, follows its `constitution` reference
to load the canonical constitution, verifies the pinned revision matches
the on-disk file, and confirms it is applying the constitution's
principles for the session.

### US2 — Coexist additively with repo-local `CLAUDE.md` / `AGENTS.md`

**As** a repo owner, **I want** my existing repo-local `CLAUDE.md` or
`AGENTS.md` files to be respected alongside the haex-hive constitution
**so that** haex-hive does not overwrite my project-specific instructions
just because I opted in.

Acceptance: a fresh CLI session opened in a repo containing both
`.haex-hive.json` and one or more repo-local instruction files reads all
of them, integrates the repo-local instructions additively with the
constitution, and reports the effective instruction set with both
sources visible to the operator.

### US3 — Detect conflicts between repo-local instructions and constitution

**As** an operator, **I want** any direct contradiction between the
repo's own instructions and a NON-NEGOTIABLE constitutional principle to
be surfaced immediately, with both sides quoted **so that** I can make
an informed decision rather than have the CLI silently pick a side.

Acceptance: given a repo where `CLAUDE.md` and/or `AGENTS.md` contain
instructions that directly contradict one or more constitutional
principles, a fresh CLI session reports every conflict in its first
response with both sides quoted verbatim, names the affected principle,
declares its default position (apply the principle) while awaiting
operator direction, and refuses hypothetical enforcement requests that
would violate a NON-NEGOTIABLE principle even if the repo-local
instructions endorse the violation.

### US4 — Opt-in discipline (repos without `.haex-hive.json` are untouched)

**As** a repo owner who has NOT committed `.haex-hive.json`, **I want**
my repo to be treated as a normal repo **so that** the haex-hive harness
does not leak workflow assumptions onto contributors who never opted in.

Acceptance: a fresh CLI session opened in a repo that lacks
`.haex-hive.json` at the root reports the file as absent, does NOT load
or apply the constitution, and does not cite constitutional principles
even when spec-kit-shaped directories (`.specify/`, `specs/`) happen to
exist in the tree — those artifacts are not the opt-in trigger.

## Success Criteria

- **SC-001** (US1): Fresh CLI session in a haex-hive-opted-in repo loads
  the constitution and applies its principles for the session.
- **SC-002** (US1): The `.haex-hive.json` `constitution.revision` field
  is a full 40-character git SHA, and the CLI verifies the on-disk
  constitution matches (blob-hash comparison acceptable; SHA equality of
  the referring commit acceptable when the same SHA is honoured for both
  fetch and integrity check).
- **SC-003** (US2): Fresh CLI session reads BOTH `CLAUDE.md` AND
  `AGENTS.md` when both are present at the repo root (verifiable by
  distinctive content each file uniquely carries).
- **SC-004** (US2): The session integrates repo-local instructions
  additively and reports the effective instruction set with the
  constitutional origin and repo-local origin both visible.
- **SC-005** (US3): For every conflict between repo-local and
  constitutional rules, the session quotes both sides verbatim and names
  the affected principle.
- **SC-006** (US3): The session's default position on each conflict is
  the constitutional principle, and it explicitly states so while
  awaiting operator direction.
- **SC-007** (US3): Given a hypothetical operator instruction to perform
  an action that would violate a NON-NEGOTIABLE principle, the session
  refuses and cites the principle — even if the repo-local instructions
  authorize the action.
- **SC-008** (US4): Fresh CLI session in a repo without `.haex-hive.json`
  reports the marker as absent and does NOT apply constitutional
  constraints.
- **SC-009** (US4): The presence of `.specify/` or `specs/` in the tree
  does not by itself trigger opt-in — the session correctly identifies
  `.haex-hive.json` as the sole opt-in signal.
- **SC-010** (US4): Given a hypothetical operator instruction that would
  violate what a haex-hive principle would forbid if opted in, a session
  in a non-opted repo refuses on general grounds (baseline
  professional-hygiene) without citing constitutional principles it
  cannot legitimately claim to have adopted.

All ten criteria PASS across two CLIs (Claude Code 2.x, Codex CLI
0.147.0) in the 2026-08-27 validation run. See
`.validation-runs/2026-08-27.md` for verbatim prompts, answers, and
grading.

## Adopted Artifacts

- **`.haex-hive.json`** at the repo root, per
  [contracts/haex-hive-json.schema.md](./contracts/haex-hive-json.schema.md).
- **Global detection snippet** per
  [contracts/global-snippet.contract.md](./contracts/global-snippet.contract.md),
  installed by each operator in their user-level CLI config
  (`~/.claude/CLAUDE.md` for Claude Code, `~/.codex/AGENTS.md` for Codex
  CLI).
- **Retirement of committed `CLAUDE.md` / `AGENTS.md`** at the haex-hive
  repo root — the pilot-era files were removed in commit `f1a7e48` of
  branch `003-config-file-based-delivery` and remain removed on merge to
  `main`.

## Non-Goals

- Automated tooling to lint `.haex-hive.json` schema conformance
  (proposed as follow-up under the Phase 7 CI-Hardening group).
- Automated tooling to detect and report conflicts between repo-local
  and constitutional instructions (proposed as follow-up).
- A CLI-embedded loader for `.haex-hive.json` (the mechanism is
  deliberately prosaic: the operator's user-level config carries the
  detection instructions, and the CLI executes them like any other
  operator instruction — no bespoke integration required).
- Migration of the behavioral craft rules currently in the operator's
  user-level config into a haex-hive-managed `craft-guidelines.md`
  (proposed as future work, Weg A).

## Assumptions

- The operator installs the global snippet in their user-level config
  themselves. There is no `~/.haex-hive/install` script.
- The two supported CLIs at prototype time are Claude Code (any recent
  version) and Codex CLI 0.147.0 or newer. Codex CLI's global
  instruction path is `~/.codex/AGENTS.md` per the binary's built-in
  reference ("Failed to read global AGENTS.md instructions from ...").
- The `.haex-hive.json` `identity` field is a `local:<slug>` placeholder
  during the prototype phase and becomes the git remote URL once the
  repo is pushed.

## Open Questions / Follow-ups

- **F-1**: `active_feature` drift lint. The 2026-08-27 T-A run surfaced
  that `.haex-hive.json` declared `active_feature:
  specs/003-config-file-based-delivery` before the directory existed.
  A future lint step (Phase 7) should catch this class of config-vs-tree
  drift automatically.
- **F-2**: Constitution self-reference. `.haex-hive.json` currently uses
  `"repository": "self"` because the haex-hive repo is itself the
  constitution's home. Downstream repos will use a real remote URL. The
  self-reference case needs its own explicit contract note so downstream
  implementations do not fall through it.
- **F-3**: Codex CLI does not natively read `CLAUDE.md`. Claude Code
  does read `AGENTS.md` (recent versions). Both CLIs read both files
  under the global snippet — but only because the snippet says "any
  `CLAUDE.md` or `AGENTS.md` at the repo root". If a future CLI is
  added, the snippet needs to be extended to cover its native
  convention path.
- **F-4**: Spec 002 (Harness Wording Hardening) needs to be resurrected
  on the new delivery target. The wording changes (strengthened
  Principle V, new Principle VIII, checkbox-freshness note) still apply
  to the constitution and to the global snippet; only the delivery
  target changed. Rework the T-006 draft (CLAUDE.md block update) to
  become a global-snippet update instead.
- **F-5**: Craft Guidelines split (Weg A). The operator's user-level
  config carries behavioral craft rules (think-before-coding, simplicity-
  first, surgical changes, accuracy over agreement). If these are worth
  formalizing under haex-hive governance, they land as a separate
  `craft-guidelines.md` next to the constitution — not folded into the
  constitution itself. Kept as future work.

## References

- Design plan: `docs/plans/2026-08-26-haex-hive-design.md`
- Constitution (v1.0.0): `.specify/memory/constitution.md`
- ADRs on Phase 0 findings: `docs/adr/0001-*` through `docs/adr/0004-*`
- Prior specs: `specs/001-phase-0-pilot-harness`, `specs/002-harness-wording-hardening`
- Validation record: `specs/003-config-file-based-delivery/.validation-runs/2026-08-27.md`
