# ADR 0009: Declared Speckit Workflow Adherence

**Status**: Accepted
**Date**: 2026-09-02
**Related**: `.specify/memory/constitution.md` §Development Workflow;
constitution version bump 1.3.0 → 1.4.0

## Context

The constitution's §Development Workflow already names `/speckit-specify`,
`/speckit-plan`, and `/speckit-analyze` as MUST. It leaves the task-execution
loop (`/speckit-tasks`, `/speckit-implement`) implicit. During a session on
2026-09-02 that implicit gap produced two operator corrections of the same
form: a task was ticked in `specs/*/tasks.md` after freehand edits against
source files, without invoking `/speckit-implement` and its checklist gate.
The corrections were addressed at conversation level, but nothing in the
in-repo harness stops the pattern from repeating on the next session.

A related concern: haex-hive itself declares its speckit workflow at
`.specify/workflows/speckit/workflow.yml` (bundled workflow "Full SDD Cycle"
covering specify → review-spec → plan → review-plan → tasks → implement).
The declaration exists, but nothing binds the operator to follow it. The
same file shape is intended to be selectable per project (see the planned
Spec 011: `speckit-workflow` atom that replaces or extends the local
`workflow.yml` through the normal atom-adoption flow), so the constitution
clause MUST reference the declaration by path rather than hard-coding
specific slash-commands.

Under haex-hive's self-adoption pattern, the constitution atom
(`com.github.haexmas.haex-hive.constitution`) is the mechanism that ships
this rule to every downstream repo: any project pinning the new revision
inherits the clause via its own assembled `.haex-hive/constitution.md`.
This is the default enforcement path; per-project override arrives with
Spec 011.

## Decision

Add a new bullet to the constitution's §Development Workflow section:

> **Declared speckit workflow adherence**: The project's active speckit
> workflow is declared at `.specify/workflows/speckit/workflow.yml`. Every
> primary task landing MUST follow the steps and review gates declared
> there, invoking the named commands (`speckit.<step>` → `/speckit-<step>`)
> at their corresponding stages. Freehand edits against source files are
> allowed only for (a) review-fix responses on an already-open PR, or (b)
> follow-up doc-alignment surfaced during a walkthrough test; never for the
> primary task landing itself. If `.specify/workflows/speckit/workflow.yml`
> is absent, the built-in speckit skills serve as the implicit default and
> MUST still be followed for their corresponding stages. Spec 011 (planned)
> will formalise per-project workflow selection so an adopted
> `speckit-workflow` atom can replace or extend the local `workflow.yml`
> without touching this constitution.

Version bump: 1.3.0 → 1.4.0 (MINOR: material expansion of the development
workflow contract).

## Consequences

- **Positive**: enforcement of the full speckit loop is anchored in versioned
  content instead of session-scoped memory. Every downstream repo that adopts
  the new constitution revision inherits the rule automatically through
  `haex install`.
- **Positive**: the clause is written generically against `workflow.yml`, so
  a project that swaps its declared workflow (e.g. adopts a community
  extension from https://speckit-community.github.io/extensions/ or the
  Spec 011 `speckit-workflow` atom) picks up the new steps without needing
  a constitution amendment.
- **Neutral**: existing sessions and downstream consumers on the old
  revision are unaffected until they bump their pin. There is no runtime
  enforcement; the constitution is advisory-to-the-agent, and violation
  detection is a `/speckit-analyze` responsibility. Adding runtime
  enforcement (e.g. a pre-commit hook that refuses non-workflow task
  landings) is out of scope for this ADR.
- **Neutral**: the `.haex-hive/constitution.md` copy shipped in this
  repo's own tree is not regenerated in this commit (chicken-egg: the new
  atom SHA does not exist until after the commit lands). A follow-up
  commit bumps `.haex-hive.json`'s revision pin and re-runs `haex install`
  to publish the amended constitution locally.

## Alternatives Considered

- **Hard-coded `/speckit-implement` MUST clause**: rejected. Ties the
  constitution to one specific command name, breaks under alternate
  workflow packages (V-Model Extension Pack, Bugfix Workflow, and other
  entries in the community extensions list). The workflow.yml-relative
  wording is future-proof against per-project workflow selection.
- **Memory-only enforcement (per-agent auto memory)**: rejected. Memory
  is per-agent and per-session; it does not propagate to teammates or new
  clones. The operator explicitly requested a repo-level anchor.
- **Runtime-enforced pre-commit hook**: deferred. Enforcement is
  currently advisory. A future ADR may add a mechanical gate under Phase
  7 (see the constitution's §Governance closing paragraph).

## Follow-up

- After this commit lands: bump `.haex-hive.json` `atoms[0].revision` to
  the new SHA and re-run `haex install` locally to regenerate
  `.haex-hive/constitution.md`. Commit that as a small follow-up.
- Spec 011 will formalise the workflow-selection mechanism, at which point
  this ADR's clause continues to hold; the wording is already generic
  against `workflow.yml`.
