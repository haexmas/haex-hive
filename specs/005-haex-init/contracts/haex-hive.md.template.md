# Contract: Canonical Session-Instructions Template

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)
**Date**: 2026-08-27

## File Location

- **Source of truth in this repo**:
  `.specify/templates/haex-hive-session-instructions.md`
- **Embedded copy inside `haex-init`**: Python string constant
  `CANONICAL_SESSION_INSTRUCTIONS`.
- **Destination on the operator's machine (written by `haex-init`)**:
  `~/.haex-hive/haex-hive.md`.

The three copies MUST be byte-identical. This is enforced by
Decision 9's sync test.

## Canonical Content

```markdown
# haex-hive session instructions

This file is the canonical instruction text every LLM/agent session
reads at start when it operates inside a repository containing a
`.haex-hive.json` marker at the root.

## What haex-hive is

haex-hive is a mechanism for a project to declare (via
`.haex-hive.json`) which external constitution and specification
content it opts into. External content is referenced by
`(repository, revision, path)` — the revision is always a full,
immutable git commit SHA.

## What to do at session start

1. If the working directory contains no `.haex-hive.json` at its
   root, do NOT apply haex-hive constraints. The repo has not
   opted in.

2. If `.haex-hive.json` is present, read it. Each entry in
   `harness_sources` names a role or a permission-only allowlist
   entry. For each `role: "constitution"` entry, resolve the
   referenced content (`.specify/scripts/spec-resolve resolve
   --role constitution`) and treat its principles as binding for
   this session's work in this repo.

3. Also read any `CLAUDE.md` or `AGENTS.md` at the repo root and
   any other convention paths the repo uses. These are the repo
   owner's instructions and apply alongside the constitution, not
   instead of it.

4. If the repo's instructions contradict a NON-NEGOTIABLE
   constitutional principle, surface the contradiction to the
   operator with both sides quoted. Do not silently pick a side.
   Default position while awaiting the operator: apply the
   constitutional principle.

## What the constitution can require

The constitution can require, among other things:

- No secrets in committed content.
- No absolute local paths in versioned config.
- Device-independent project identity.
- SHA-pinned cross-repo references.
- Opt-in-only external content (an empty `harness_sources` grants
  no permissions).
- Review-gated self-modification of harness content.
- Relay-independence for local work.
- No concealment instructions in agent output to downstream
  readers.

When the user asks the agent to perform an action that would
violate one of these principles — regardless of what the repo's
own instructions say — refuse and cite the specific principle.

## What haex-hive does NOT do

- It does NOT modify `.haex-hive.json` in response to any "apply
  this" prompt. The opt-in list is edited only in response to an
  explicit "add X to the allowlist" request, under review-gate.
- It does NOT fetch anything at session start unless a resolve is
  actually needed for the operator's request.
- It does NOT communicate over the relay for anything the operator
  is doing locally.

## Reporting

At the end of any session where haex-hive constraints applied,
briefly note in the operator-facing output which constitution SHA
was resolved and which principles were consulted. This is not a
performance summary; it is a transparency signal so the operator
can verify the constraint that applied.
```

## Rationale for Wording

- The instruction text is a normative guide to the LLM agent, not
  a spec document. It focuses on what to do (steps 1-4) and what
  not to do (the "does NOT" list).
- It repeats the constitutional principles at a high level so an
  agent that cannot resolve the constitution file (network down,
  cache empty) still knows the shape of the invariants.
- The reporting requirement at the end is a Principle-VIII-aligned
  transparency signal — an agent that skips it is silently
  narrowing what the operator sees.

## Versioning

- The version constant that governs this file is
  `INSTRUCTIONS_VERSION` in `haex-init`.
- A content change here MUST also update `INSTRUCTIONS_VERSION`
  and regenerate `INSTRUCTIONS_SHA256`. The sync test enforces this.
- The file is read at LLM session start by the agent, so any change
  is a semi-behavioural change and gets a version bump
  proportional to how much operator-visible behavior changes.

## Not part of this file

- Per-tool config specifics (Claude vs Codex vs Gemini).
- Any project-specific rules.
- Any operator-specific preferences.
- Anything that references a specific commit or SHA (this file is
  the SHA-free bootstrap; the constitution it points to has SHAs).

## Consumer Signal for Downstream Readers

Any agent reading this file at session start MUST NOT treat the
absence of a `.haex-hive.json` as license to inherit constraints
from anywhere else (a global CLAUDE.md, a sibling repo, a
convention). A missing `.haex-hive.json` means "not opted in";
opt-in is explicit or it does not exist.
