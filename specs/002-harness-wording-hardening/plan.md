# Implementation Plan: Harness Wording Hardening (Phase 0 Follow-up)

**Branch**: `002-harness-wording-hardening` | **Date**: 2026-08-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-harness-wording-hardening/spec.md`

## Summary

Land the wording changes decided in ADRs
[0002](../../docs/adr/0002-disambiguate-apply-vs-permit-external-harness.md),
[0003](../../docs/adr/0003-agents-must-not-emit-hide-instructions.md), and
[0004](../../docs/adr/0004-eager-checkbox-update-rule.md) into the constitution
and the global-snippet reference implementation, then verify via fresh-CLI
validation runs that Codex refuses Test 3.2b in the same shape as Claude,
that no supported CLI emits hide-instructions on the test prompts, and that
handoff Q&A stays clean against a freshly-ticked task list.

**Delivery-target note**: this spec was originally drafted against the
committed `CLAUDE.md`/`AGENTS.md` pilot adapters. Spec 003 retired those
in favor of a per-repo `.haex-hive.json` marker plus an operator-owned
global snippet. This spec was rebased on the new main after spec 003
merged; the pointer-side edit target changed accordingly, but the
constitution-side edits and the fresh-CLI validation methodology are
unchanged.

Technical approach: pure content edits to `.specify/memory/constitution.md`,
`specs/003-config-file-based-delivery/contracts/global-snippet.contract.md`,
and the `.specify/templates/tasks-template.md`. Constitution version bump
1.0.0 → 1.1.0 (MINOR: new principle VIII, V wording expanded). Then real
fresh-CLI validation runs against a written quickstart.md, results recorded
in `.validation-runs/`. No code, no services, no build step.

## Technical Context

**Language/Version**: N/A — Markdown and YAML edits only.
**Primary Dependencies**: git; the spec-kit toolchain already installed
under `.specify/`; the supported agent CLIs (Claude Code + Codex 0.147.0)
already validated in Phase 0.
**Storage**: git objects and the working tree.
**Testing**: manual fresh-session validation on both CLIs (identical
methodology to Phase 0 US1/US3), plus a pattern-based grep pass over raw
agent output for hide-instruction detection (US2).
**Target Platform**: same Linux workstation used for Phase 0. Windows/WSL2
and macOS remain out of scope for author-run validation, deferred to a
future validation-machine expansion feature.
**Project Type**: harness/documentation content edit + verification. Not
a runnable code artifact.
**Performance Goals**: N/A.
**Constraints**:
- Constitution amendment MUST use the Governance section's own procedure:
  ADR under `docs/adr/` + file update + version bump in one commit.
  ADRs 0002/0003/0004 already exist and satisfy the ADR-precondition.
- Phase 0 records (`.validation-runs/2026-08-26.md`,
  `.smoke-tests/2026-08-26.md`, `checklists/requirements.md`) MUST NOT be
  rewritten. This feature adds; it does not rewrite history (FR-006).
- Validation runs MUST happen in fresh CLI sessions, per the same
  discipline as Phase 0. Sub-agent proxies are NOT acceptable as
  substitutes for FR-003/FR-004 (they were explicitly labeled
  content-only proxies in the smoke test).
**Scale/Scope**: one constitution, one CLAUDE.md, one tasks template, three
user stories, seven FRs, five SCs. Same order of magnitude as Phase 0.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v1.0.0 — the seven
NON-NEGOTIABLE principles as of feature start. Feature 002 itself modifies
the constitution — that requires special care.

| Principle | Status | Notes |
|-----------|--------|-------|
| I. No Secrets in Git | ✅ PASS | Plan introduces no secret material. |
| II. No Local Absolute Paths in Versioned Config | ✅ PASS | Only Markdown/YAML edits to files that already comply. Test 3.2b rerun uses per-operator instructions in quickstart, not committed paths. |
| III. Project Identity Is Device-Independent | ✅ PASS | Single-machine feature; no cross-device addressing introduced or removed. |
| IV. Cross-Repo References Pin Immutable Revisions | ✅ PASS | Empty allowlist remains empty after this feature; no cross-repo refs added. |
| V. External Sources Are Opt-in Per Project | ✅ PASS | **This principle's wording is what the feature strengthens** — the strengthening is additive (more precise, not more permissive), so V is satisfied both before and after. |
| VI. Self-Modifying Instructions Are Always Review-Gated | ⚠️ GATE-SENSITIVE | **The feature literally modifies harness instructions (the constitution).** Satisfying VI requires: (a) every edit lands as a commit on a feature branch, (b) no in-session auto-write in the sense VI forbids, (c) the amendment goes through the review flow (this plan, the ADR precondition, and the eventual merge to main). All three hold if the plan is followed as written. |
| VII. Relay Unavailability Never Blocks Local Work | ✅ PASS | No relay dependency introduced. |

**Special note on VI**: the constitution's Governance section explicitly
allows amendments; VI does not forbid amendment, it forbids **silent
in-place edits by an agent inside a session**. This feature's edits are
made deliberately by the operator (or the operator's session, under
direct instruction) as reviewable commits on a feature branch — the
mechanism VI is designed to permit.

**Gate result**: PASS on all seven principles. VI carries the operational
constraint above; the plan below is written to satisfy it.

## Project Structure

### Documentation (this feature)

```text
specs/002-harness-wording-hardening/
├── plan.md              # This file
├── research.md          # Phase 0 (research): no open questions, brief file
├── quickstart.md        # Phase 1 (design): validation checklist for the reruns
├── contracts/
│   └── constitution-diff.schema.md   # (Phase 1) — the shape of the amended constitution: what MUST change, what MUST NOT
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

No `data-model.md` — this feature has no runtime data model. Same deviation
as spec 001, same justification.

### Files edited by this feature (repo root)

```text
.specify/memory/constitution.md   # V wording expanded, VIII added, version 1.0.0 → 1.1.0
specs/003-config-file-based-delivery/contracts/global-snippet.contract.md
                                   # Reference-implementation snippet extended to callout amended V, VIII, and the ADR-0004 checkbox rule
.specify/templates/tasks-template.md   # preamble line documenting checkbox-freshness expectation (FR-005)
```

**Structure Decision**: content-only feature. No code, no tests directory,
no source tree. The "test" is the manual fresh-CLI validation checklist in
this feature's `quickstart.md`.

## Complexity Tracking

None. All seven constitution gates pass at plan time. The VI gate-sensitive
note is a normal operational constraint under the constitution's own
Governance procedure, not a violation requiring justification.

## Phase 0: Outline & Research

Two candidate open questions were considered, both resolved without needing
a research round:

1. **Which SHA of secana-specs to reference in the Test 3.2b prompt?** The
   Codex Test 3.2b failure in Phase 0 used SHA
   `ab39fe57cca76153ed57051ceff229bb9972b141`. The rerun should use the
   same SHA for continuity — same test, comparable results before/after.
   Recorded in `research.md`.
2. **Exact wording for the strengthened V and new VIII?** ADRs 0002 and
   0003 already specify the required properties of the wording (unambiguous
   distinction of "apply" vs. "modify allowlist"; anti-concealment rule
   applying to all output formats). The actual drafting is Phase 2 (tasks)
   work, not research.

Output: brief `research.md` recording decision 1 (SHA continuity) and
explicitly noting no other open questions.

## Phase 1: Design & Contracts

### No `data-model.md`

Justified above.

### Contract: constitution-diff shape

The one contract this feature exposes is *the shape of the amended
constitution*: what edits MUST land, what edits MUST NOT land, and how the
change is versioned. Captured as
`contracts/constitution-diff.schema.md`.

Key contract points:
- V's principle heading, rationale, and NON-NEGOTIABLE tag are unchanged.
- V's body gains explicit paragraphs disambiguating "apply" from "opt-in".
- A new principle VIII lands under a "No Concealment Instructions in Agent
  Output" heading, structured identically to the other seven principles
  (NON-NEGOTIABLE tag, rationale paragraph).
- Version line changes from `1.0.0` to `1.1.0`; `Last Amended` date
  updates; `Ratified` date is unchanged.
- The Governance section is unchanged; the amendment procedure references
  itself.

### Quickstart

`quickstart.md` for this feature is a small runnable-by-a-human validation
checklist covering the three User Stories:
- US1: rerun Tests 3.2a and 3.2b on both CLIs. Compare Codex refusal to
  the ADR 0002 target shape.
- US2: capture raw output of the CLIs on the Test 3.2b and Test 1.3 prompts
  and grep for hide-instruction patterns.
- US3: tick tasks eagerly in a small test work-unit and verify a fresh
  handoff query names the correct next step.

The quickstart is intended to run in one sitting per CLI, with the same
"per-operator, single-machine" scoping as spec 001's quickstart.

### Agent context update

Per the plan skill's outline: update the reference-implementation snippet
in `specs/003-config-file-based-delivery/contracts/global-snippet.contract.md`
after the constitution wording lands, so the snippet the operator installs
in their user-level CLI instruction file references the amended V, VIII,
and the ADR-0004 checkbox rule. This is a specific task in Phase 2
(`tasks.md`), not an in-plan side effect. The operator then re-copies the
updated snippet into the operator's user-level CLI instruction files
(Claude Code's `CLAUDE.md` in its config directory; Codex CLI's
`AGENTS.md` under `$CODEX_HOME`) on each device they use — that copy
step is outside this feature's git scope but belongs on the release
checklist.

### Re-evaluated Constitution Check post-design

All gates still pass. The VI gate-sensitive constraint holds throughout the
plan. No new principle-touching artifacts introduced.

## Next Command

`/speckit-tasks` — decomposes this plan into dependency-ordered tasks under
`tasks.md`. Expected task count is comparable to spec 001's Phase 2
implementation cluster (~10–15 tasks): three groups (edits, real-CLI
validation, polish/merge).
