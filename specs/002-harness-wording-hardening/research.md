# Phase 0 Research: Harness Wording Hardening Prerequisites

**Feature**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Date**: 2026-08-27

Two candidate open questions considered. One requires a recorded decision;
one is deferred to Phase 2 as drafting work, not research.

## Decision 1: SHA of secana-specs to reference in the Test 3.2b prompt

**Decision**: use the same SHA the Phase 0 Test 3.2b failure produced,
`ab39fe57cca76153ed57051ceff229bb9972b141`, in the rerun's Test 3.2b
prompt.

**Rationale**: continuity. If the rerun's prompt differs from the original
prompt in any way (SHA, path, phrasing), a subsequent PASS could be
attributed to prompt drift rather than to the constitution's strengthened
wording. Same prompt, same expected refusal shape, same SHA gives a
directly comparable before/after result. The SHA is already recorded
verbatim in `.validation-runs/2026-08-26.md`.

**Alternatives considered**:
- **Use the current tip SHA of secana-specs** (if secana-specs has moved
  since the Phase 0 run) — rejected. Even if the pointed-at file content
  is identical, the SHA change would introduce a variable this experiment
  cannot afford.
- **Use a synthetic SHA that resolves to nothing** — rejected. The point
  of the test is to catch a real "external harness that exists and is
  reachable" case. A synthetic SHA might get Codex to refuse for reasons
  unrelated to the harness (e.g., unresolvable git object) rather than
  for the intended Principle V reason.

## Not-a-decision: exact wording for strengthened V and new VIII

The ADRs 0002 and 0003 already specify the required properties of the
wording:
- V must disambiguate "apply constraints" from "modify allowlist to
  permit constraints"
- V must require a refuse-then-propose response shape when the source is
  not in the allowlist
- V must forbid writes to `.specify/system.yaml` triggered by "apply"-
  shaped prompts
- VIII must ban emitting hide-instructions in any format
- VIII must apply to output emitted by any agent operating under the
  haex-hive harness

The concrete drafting of the paragraph text is a **task, not a research
question**. Deferred to Phase 2 (tasks.md), where the "draft the amended
V paragraph" and "draft the new VIII" become explicit implementation
tasks with acceptance criteria drawn from the ADRs above.

## Platform/environment notes

- Codex version on the validation machine remains 0.147.0. If a Codex
  update lands before the rerun happens, the new version MUST be recorded
  in the run's notes. A version change is a legitimate reason for a PASS
  or FAIL to shift, so it must be traceable.
- Claude Code version on the validation machine is whatever the operator
  has installed. Not recorded because Claude Code updates independently of
  this feature's timeline; the pre-change baseline is "Tests 3.2a passed"
  on the version used in Phase 0. The rerun uses the current version at
  rerun time; a change is expected to leave 3.2a passing.
- The sibling `secana-specs` clone remains at the same path per operator
  local configuration. Not committed here; see spec 001 T026.
