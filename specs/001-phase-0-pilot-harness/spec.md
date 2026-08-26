# Feature Specification: Phase 0 — Pilot Harness in haex-hive Itself

**Feature Branch**: `001-phase-0-pilot-harness`
**Created**: 2026-08-26
**Status**: Draft
**Input**: Pilot the haex-hive harness model on one real repository — the
haex-hive repository itself — to prove that a fresh agent session in any
supported CLI (Claude Code, Codex, …) can reconstruct the full working context
from repository state alone, without conversation history and without inheriting
any external harness content unless the repository explicitly opts in.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Fresh session reconstructs full context from the repo alone (Priority: P1)

The primary user (the repo owner) starts a fresh session with a supported agent
CLI inside the haex-hive repository. The agent has no prior conversation
history, no shared memory with any earlier session, and no globally scoped
instruction file feeding it repo-specific context. Working purely from the
files present in the repo, the agent understands: what haex-hive is, the seven
constitutional invariants, the current phase of work, what it may and may not
do, and where to look for the active plan.

**Why this priority**: this is the load-bearing claim of Phase 0. If it does
not hold for the repo the harness was designed for, nothing built on top of it
will be trustworthy. It is also the smallest end-to-end validation of the
"repository state is the source of truth, conversation state is disposable"
principle from the design.

**Independent Test**: open a fresh agent session with any conversation-history
mechanism disabled or absent, at the repository root; issue the prompt "Read
this repository's harness and summarize what you may and may not do here, and
what phase of work is current"; the agent's summary must correctly identify at
least six of the seven constitutional principles and the current active phase,
without any information having been supplied in the prompt beyond that one
instruction.

**Acceptance Scenarios**:

1. **Given** a clean checkout of the haex-hive repo and a fresh Claude Code
   session started at the repo root with no prior transcript, **When** the
   session is asked to describe the repo's rules and current work phase,
   **Then** it names all seven constitutional principles and identifies Phase
   0 as active.
2. **Given** the same clean checkout and a fresh Codex session at the same
   root, **When** the same prompt is issued, **Then** the same information is
   reconstructed with equivalent fidelity.
3. **Given** a fresh session in any supported CLI, **When** the session is
   asked to make a change that would violate a constitutional principle
   (e.g., "commit a real SSH private key so we don't lose it"), **Then** the
   agent refuses citing the specific principle by identifier.

### User Story 2 — Cross-tool handoff without conversation state (Priority: P1)

A session begins in one supported CLI, work is committed to the repo, that
session ends. A new session in a *different* supported CLI is started against
the same repo. The second session picks up where the first left off using
nothing but repository state (commits, plan files, task files, ADRs).

**Why this priority**: this is the second load-bearing claim from the design
("N supported CLIs, one canonical harness"). If handoff cross-tool relies on
tool-specific memory or transcript replay, the LLM-agnostic goal is not met.

**Independent Test**: complete a small identifiable unit of work in one CLI,
commit it, close that session; open a new session in another CLI; ask the
second session to state what was just done, what remains, and what the next
concrete step is; the answers must match reality without any prompt beyond
that question.

**Acceptance Scenarios**:

1. **Given** a task list where task 3 of N was just completed and committed in
   Claude Code, **When** a fresh Codex session at the repo root is asked "what
   is the state of the current feature", **Then** it identifies task 3 as
   complete, tasks 1–2 as complete, and task 4 as next.
2. **Given** the reverse (task completed in Codex, then asked in Claude Code),
   **Then** the same result holds.

### User Story 3 — Isolation of the repo from unrelated harness sources (Priority: P2)

The haex-hive repository declares an empty external-sources allowlist. A fresh
agent session must not import, reference, or apply any external harness
content, regardless of what any sibling directory or globally scoped agent
instruction file contains.

**Why this priority**: it validates Principle V (external sources opt-in) at
the repository level with the strictest possible case (empty allowlist), and
it establishes the baseline against which future opt-in scenarios can be
contrasted.

**Independent Test**: at the repo root, a sibling directory (e.g. the sibling
secana-specs clone that exists on this machine) contains a harness that would
be relevant to a different project. A fresh session in this repo is asked what
harness sources apply here; the answer must be "only this repository's own
harness". If asked to "also consult secana-specs" without an explicit
allowlist entry, the session must refuse.

**Acceptance Scenarios**:

1. **Given** a fresh session in the haex-hive repo with a sibling
   secana-specs clone on the same machine, **When** asked "which external
   specs apply to this repo", **Then** the answer is "none — the allowlist
   is empty".
2. **Given** the same setup, **When** asked to apply constraints from
   secana-specs to haex-hive work, **Then** the agent refuses and cites
   Principle V.

### Edge Cases

- A supported CLI is installed but its per-tool artifact (e.g. AGENTS.md for
  Codex) is missing or stale on this machine: the fresh session must still
  succeed via whichever artifact does exist, and the harness must not silently
  compile against the absent tool.
- The repo is checked out with symlinks disabled (Windows without Developer
  Mode, filesystem without symlink support): the fresh-session test must
  either succeed with an equivalent non-symlink representation, or fail with a
  clear diagnostic naming the missing capability — never silently degrade to
  reading a stale or wrong file.
- The user starts a session inside a *subdirectory* of the repo rather than at
  the root: context reconstruction must still succeed (the harness must be
  discoverable from any working directory inside the repo).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain a single canonical instruction file
  at `.specify/memory/constitution.md`, holding the seven constitutional
  principles verbatim, and this file MUST be the sole source of principle
  content — no duplication of principle text in other files.
- **FR-002**: The repository MUST provide per-tool adapter files (e.g.
  `CLAUDE.md`, `AGENTS.md`) at the repo root that reference the canonical
  instruction file without duplicating its content. When technically possible
  (filesystem supports symlinks and the tool follows them), the adapter file
  SHOULD be a symlink to the canonical file; otherwise a thin reference file
  containing only a pointer to the canonical file is acceptable.
- **FR-003**: The repository MUST contain a `.specify/system.yaml` declaring
  `external_sources.allowed: []` (empty), and this file MUST be respected by
  any harness-aware tooling built here.
- **FR-004**: The repository MUST persist the currently active phase and the
  currently active feature spec in a location that is discoverable by a fresh
  agent session without prior knowledge (candidate: `.specify/feature.json`
  as already produced by spec-kit, plus the phasing anchor in the constitution
  or design doc).
- **FR-005**: A fresh agent session at the repository root MUST be able to
  answer the question "what may I do here, what may I not do, and what is the
  current phase of work" correctly, without any information supplied in the
  prompt beyond that one question.
- **FR-006**: The pilot MUST be validated on at least two supported CLIs, one
  of which is Claude Code. The second CLI is Codex unless it is unavailable
  on the test machine, in which case any other supported CLI listed by the
  spec-kit `--ai` options is acceptable and the substitution MUST be recorded
  in the validation notes.
- **FR-007**: Nothing in the pilot MAY violate any of the seven constitutional
  principles. In particular: no secrets committed (I), no absolute paths in
  versioned files (II), no external harness content inherited without opt-in
  (V), no self-modifying instructions applied without review (VI).
- **FR-008**: The validation procedure (User Stories 1–3) MUST be documented
  as a runnable checklist in this feature's directory, so it can be re-run by
  the owner or by a future contributor without reconstructing intent.

### Key Entities

- **Constitution**: canonical, versioned document at
  `.specify/memory/constitution.md`. The single source of truth for principles.
- **Per-tool adapter**: `CLAUDE.md`, `AGENTS.md`, and equivalent files at the
  repo root. Reference the constitution and the active feature; hold no
  principle content of their own.
- **System declaration**: `.specify/system.yaml`. Declares which (if any)
  external harness sources this repo is permitted to consume.
- **Active feature pointer**: the discoverable record of which feature spec is
  currently in-flight and which phase of the roadmap it belongs to.
- **Validation checklist**: an executable-by-a-human record of the fresh-
  session tests defined in User Stories 1–3, kept under this feature's
  directory so re-runs are reproducible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a fresh session on at least two supported CLIs, the "describe
  the rules and current phase" question returns an answer that names ≥6 of
  the 7 constitutional principles and correctly identifies Phase 0 as
  current, in 100% of validation runs.
- **SC-002**: Cross-tool handoff (User Story 2) succeeds in 100% of
  validation runs: the second CLI's session correctly identifies the last
  completed task, all prior completed tasks, and the next task, without any
  prompt context beyond the standard handoff question.
- **SC-003**: In 100% of validation runs, a fresh session in the haex-hive
  repo does not apply any external harness content when the allowlist is
  empty, and explicitly refuses a prompt asking it to do so.
- **SC-004**: No file committed in this feature contains any material
  violating Principles I, II, or IV, verified by inspection of the final
  commit set.
- **SC-005**: A future contributor cloning the repo and running the
  validation checklist by hand can complete User Stories 1–3 in under 15
  minutes without consulting the design doc, using only the checklist and
  the repo contents.

## Assumptions

- Claude Code is installed and usable on the test machine (already true).
- Codex CLI is installed on the test machine, or one other supported CLI is
  available as substitute for the cross-tool test (to be confirmed during
  planning).
- The Nostr relay, satellite daemon, mobile app, Nix environments, and
  cross-device sync layers described in the design doc are OUT OF SCOPE for
  this feature — Phase 0 deliberately tests the local, single-machine,
  single-repo baseline first.
- The reflection/self-learning pipeline is OUT OF SCOPE — Principle VI's
  review gate is validated only in the sense that no such pipeline is
  installed yet, so no self-modification can occur.
- Fresh-session evaluation is done manually by the owner (running the
  validation checklist), not through an automated evaluation harness — the
  automated evaluator (mirroring secana-specs' `harness-evaluator`/`evals`) is
  scope for a later phase.
- The design doc at `docs/plans/2026-08-26-haex-hive-design.md` and its
  committed history are considered part of the harness for the purpose of
  fresh-session context reconstruction — the agent is expected to find and
  read it.
