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
