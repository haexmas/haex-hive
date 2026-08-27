# ADR 0004: Eager checkbox updates in tasks.md are load-bearing for cross-tool handoff

**Status**: Accepted
**Date**: 2026-08-27
**Related**: spec 001 User Story 2 (cross-tool handoff); Phase 0 Test 2.2 first attempt

## Context

In Phase 0 Test 2.2 (Codex → Claude Code cross-tool handoff), the first
run was PARTIAL — Claude Code named `T021` as the next step when
`T021` had been completed hours earlier. Claude even noticed that
the T021 candidate work-unit (ADR 0001) was already committed and
asked for a new candidate — a genuine reasoning gap, not a
hallucination.

Root cause: at the time Test 2.2 ran, tasks.md still had `T021`,
`T022`, `T023` marked as `[ ]` (open) even though all three were done
and committed. Claude Code read the checkbox state literally — that
was the "state" tasks.md advertised.

After a bookkeeping commit that ticked the three tasks (commit
`1b245b4`), a rerun of Test 2.2 returned a PASS. The identical harness
content — minus the stale checkboxes — produced a correct next-step
answer. The improvement is causally traceable to the tick.

Full detail: [`.validation-runs/2026-08-26.md`](../../specs/001-phase-0-pilot-harness/.validation-runs/2026-08-26.md).

The finding is not about Claude Code's diligence in one test. It is a
statement about how the haex-hive harness works day-to-day: cross-tool
handoff Q&A ("what was just done, what remains, what is next") reads
tasks.md as the primary state document. If tasks.md's checkbox state
lags behind git's actual state, handoff answers systematically drift
toward pending items that are secretly done.

## Decision

**Task-list checkbox updates in `tasks.md` MUST be treated as part
of the work unit, not as follow-up bookkeeping. A task is done when
(a) its actual output is committed AND (b) its checkbox is committed
as `[x]`. Both must land before the operator moves to the next task.**

Recommended practice at the operator level:

1. When completing a task, tick its checkbox in the same commit that
   lands the task's output — or, if the output is committed by a
   sub-tool (agent CLI, script) that shouldn't touch tasks.md, tick
   the checkbox in the next commit and never in a batched-later
   sweep.
2. Never leave more than one previously-completed task with an open
   checkbox before starting the next. If more than one is stale, do
   a single ticking commit before proceeding.
3. When invoking a cross-tool handoff (US2-style query — "what was
   just done, what remains, what is next"), verify tasks.md
   checkbox freshness against `git log` before believing the answer.

At the harness level, the CLAUDE.md pointer block (and equivalent
per-tool adapters) MUST include a line stating that any handoff
query's answer about "next step" derives primarily from tasks.md
checkbox state, and that stale checkboxes are a known failure mode.

Implementation lands in feature `002-harness-wording-hardening`
(the same feature as ADRs 0002 and 0003 — one wording feature covers
all three additions). Constitution: no version bump for this ADR
alone; the update is to CLAUDE.md's pointer language and to
tasks.md's own preamble, not to the constitution.

## Consequences

**Immediate**:
- Operator workflow for Phase 1+ features must maintain checkbox
  freshness. The bookkeeping commit pattern used mid-Phase-0
  (`Tick T021/T022/T023 (all done)`) becomes the norm, not an
  exception.
- The finding stops the "checkbox lag caused a handoff false negative"
  class of confusion from being blamed on the model or on the harness
  content when the actual cause is process.

**Downstream**:
- Feature `002-harness-wording-hardening` includes a preamble line
  in `tasks.md` templates (and any tools.md-shaped generated
  artifacts) making the checkbox-freshness expectation explicit.
- Phase 7 CI: a check that no `[x]` task appears in tasks.md whose
  matching commit does not exist in the git log (and vice versa: no
  work-unit commit whose matching task remains `[ ]` after a grace
  period). Defense-in-depth against operator forgetfulness.

**Alternatives considered**:
- **Automated ticking by agent CLIs at task completion** — rejected.
  Requires the agent to know its own task-list position, which is
  brittle and puts state into agent memory rather than the repo.
  Also makes Principle VI (no self-modifying instructions without
  review) uncomfortable — is a checkbox tick "self-modifying
  instructions"? Debatable, and the safer answer is manual.
- **Reduce reliance on tasks.md for handoff answers** — rejected.
  tasks.md is the natural artifact for "what work is left." Handoff
  Q&A that derived state purely from `git log` would be less
  intent-aware and harder to grade against a pass criterion.
  Improving how it is maintained is cheaper than reducing what
  reads it.
- **Only tick tasks at phase-end batches** — rejected. That is the
  pattern that failed in the first Test 2.2 attempt. This ADR
  exists specifically to rule it out.
