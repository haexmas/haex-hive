# Feature Specification: graphify-first-authoring atom/molecule

**Feature Branch**: `20260831-082047-graphify-first-authoring`
**Created**: 2026-08-31
**Status**: Draft
**Input**: User description: "graphify-first-authoring atom/molecule: opt-in constitution rule requiring agents to consult the project's graphify knowledge graph before authoring new named code"

**Design source of truth**: [docs/plans/2026-08-31-graphify-first-authoring-design.md](../../../docs/plans/2026-08-31-graphify-first-authoring-design.md). This spec inherits all decisions from that design doc (atom/molecule naming, file layout, hook mechanics, dependency handling) and does not restate them.

**Scope note**: This is deliberately **not** part of haex-hive's core constitution. It is one opt-in atom, packaged and adopted the same way any external consumer would adopt any atom, that haex-hive also chooses to adopt on itself. It lives outside the sequential `specs/NNN-*` numbering used for core-engine specs (001–010 are already spoken for, including the not-yet-created 006/008/009/010) — opt-in atoms live under `specs/atoms/<atom-name>/` instead, on their own track.

## Clarifications

### Session 2026-08-31

- Q: If the `post-commit` hook's `graphify-out/` refresh invocation fails (graphify crashes, times out, corrupted graph), does that block the commit? → A: No — warn-and-continue. The commit succeeds regardless; a warning is printed, and the stale freshness marker is caught by the agent-side backstop (bootstrap/refresh-when-stale) the next time an agent needs the graph.
- Q: If the agent's own graphify consultation fails at authoring time (the query invocation errors or times out), does the agent block until it succeeds? → A: No — warn-and-proceed. The agent notes the consult failed, authors the code anyway, and flags it for a manual check later, consistent with the hook's own failure semantics above.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Operator adopts the rule and agents stop silently duplicating code (Priority: P1)

An operator working in a haex-hive-managed repo wants agents to stop rebuilding helpers, classes, or components that already exist under a different name or in a different file. They run the atom's installer, then `haex constitution assemble` picks up the contributed principle text. From that point forward, any agent bound by the assembled constitution consults the project's graphify knowledge graph before authoring new named code, and — when the graph reveals an existing candidate, even an unexported or incomplete one — proposes extending it instead of silently building a parallel implementation.

**Why this priority**: This is the entire reason the atom exists. Every other capability (auto-refresh hooks, worktree snapshots, dependency handling) exists to make this rule practical to live with — none of them matter if the rule itself doesn't change agent behavior. This is the MVP: even with the graph refreshed by hand, the rule already delivers its value.

**Independent Test**: In a test repo with the atom's `constitution.md` merged into `.haex-hive/constitution.md`, and a knowledge graph containing one relevant existing artifact, ask an agent to author a new function that duplicates it. Verify the agent names the existing candidate, states the delta, and proposes extending it rather than authoring a parallel implementation.

**Acceptance Scenarios**:

1. **Given** an adopting repo has assembled a constitution containing this atom's contributed text, **When** an agent is asked to author a new named function/class/component/store/module, **Then** the agent consults the graph before writing any code.
2. **Given** the graph contains an existing artifact that is identical, near-identical, or an incomplete version of what is being requested, **When** the agent finds it, **Then** it names the candidate (file + symbol), states the delta between what exists and what is needed, and proposes extending it instead of authoring a duplicate.
3. **Given** the operator has explicitly instructed "skip graphify check" for the current session, **When** the agent authors new code in that same session, **Then** it does not perform the graph consultation, and the suspension does not carry over to the next session.
4. **Given** `graphify-out/` does not yet exist in the repo, **When** an agent is about to author new named code, **Then** it runs `graphify <path>` to build the graph before proceeding, rather than skipping the check.

---

### User Story 2 — Graph stays current automatically on tracked branches (Priority: P2)

Once adopted, the knowledge graph the rule depends on must not go stale as work lands on the repo's long-lived branches. Every commit landing on a tracked branch (the repo's detected default branch, plus any declared in `.haex-hive.json`'s `tracked_branches[]`) triggers an incremental refresh of `graphify-out/`, without the operator or any agent having to remember to run it by hand.

**Why this priority**: Without automatic refresh, User Story 1's guarantee decays the moment anyone commits — a human editing directly, a different tool, or an agent session that never revisits the repo. This removes the single biggest way the rule quietly stops being true.

**Independent Test**: In a repo with the atom installed, commit a change on the tracked branch through plain `git commit` (no agent involved). Verify `graphify-out/` reflects the new commit afterward, with no full rebuild (only the changed paths re-extracted).

**Acceptance Scenarios**:

1. **Given** the atom's hooks are installed and the repo is on a tracked branch, **When** a commit lands on that branch, **Then** `graphify-out/` is refreshed incrementally to include the new commit's changes.
2. **Given** a merge commit lands a feature branch onto a tracked branch, **When** the merge commit is created, **Then** the same refresh occurs as for any other commit — no separate graph-merge step is needed.
3. **Given** the repo is on a branch that is neither the detected default branch nor listed in `tracked_branches[]`, **When** a commit lands there, **Then** no automatic refresh occurs.

---

### User Story 3 — Feature branches and worktrees see a correct fork-point view (Priority: P2)

When an operator creates a new worktree or feature branch off a tracked branch, they need "does this already exist?" questions answered against a real graph immediately — not an empty one, and not one requiring a manual rebuild. The atom snapshots the parent branch's `graphify-out/` into the new worktree at creation time, representing the state at the fork point. The snapshot is discarded along with the branch/worktree.

**Why this priority**: Feature work is exactly where duplication risk is highest (an agent working in isolation, unaware of what just landed on the tracked branch). Without this, User Story 1 has no graph to consult at all on a fresh branch until an expensive full rebuild happens.

**Independent Test**: On a repo with an existing tracked-branch graph, create a new worktree off that branch. Verify the new worktree's `graphify-out/` is present immediately and matches the parent's graph at the fork point, without triggering a fresh index build.

**Acceptance Scenarios**:

1. **Given** a tracked branch has an existing `graphify-out/`, **When** a new worktree is created from it, **Then** the new worktree's `graphify-out/` is populated as a copy of the parent's graph.
2. **Given** the new worktree already has a `graphify-out/` (e.g. from a prior manual run), **When** the worktree-creation hook fires, **Then** it does not overwrite the existing directory.
3. **Given** the parent branch has no `graphify-out/` at all (fresh repo, never indexed), **When** a new worktree is created from it, **Then** nothing is copied, and the agent's own bootstrap-when-absent behavior (User Story 1) applies on first use.
4. **Given** work on the feature branch is later merged back into a tracked branch, **When** the worktree/branch is deleted, **Then** its snapshot is discarded with it and never reaches version control.

---

### User Story 4 — Adoption is a single command, not a scavenger hunt (Priority: P3)

An operator adopting this atom should not have to separately discover and install graphify themselves, work out which git-hook shebang their platform needs, or risk clobbering an existing hook setup. Running the atom's installer once handles all of it: it verifies the `graphify` CLI is present, offers to register it with the operator's current agent harness, installs the git hooks with a platform-correct interpreter, and adds `graphify-out/` to `.gitignore`.

**Why this priority**: Convenience and safety, not core value — User Stories 1–3 already work once these prerequisites are met by any means. This just makes meeting them a single reviewable step instead of several manual ones prone to platform-specific mistakes.

**Independent Test**: Run the installer in a fresh clone that has the `graphify` CLI on PATH but no hooks installed. Verify: hooks appear under `.git/hooks/` with a shebang matching an interpreter actually present on the machine, `graphify-out/` is added to `.gitignore`, and the operator is prompted (not auto-committed without asking) about registering graphify with their harness.

**Acceptance Scenarios**:

1. **Given** the `graphify` CLI is not present on PATH, **When** the operator runs the installer, **Then** it prompts with a default-Yes offer to install `graphifyy`; if the operator declines or that installation fails, it refuses with actionable manual-install instructions and makes no other changes.
2. **Given** the `graphify` CLI is present but the local registration marker is absent, **When** the operator runs the installer, **Then** it asks for confirmation before running `graphify install` on their behalf; a successful run records the marker, while declining prints manual follow-up instructions without failing the installation.
3. **Given** a git hook already exists at the target hook path from another tool, **When** the operator runs the installer, **Then** it refuses to overwrite it and instructs the operator to integrate manually.
4. **Given** the operator runs the installer while checked out on a branch that is neither the detected default branch nor a declared tracked branch, **When** installation is attempted, **Then** it refuses, naming the current branch and the expected tracked branch(es).
5. **Given** installation succeeds, **When** the operator inspects the repo afterward, **Then** `graphify-out/` is listed in `.gitignore` and was not present before installation ran.
6. **Given** `graphify-out/` already exists but the local registration marker is absent, **When** the operator runs the installer, **Then** it still prompts for registration because the graph cache is not registration state.
7. **Given** the local registration marker is set to `installed`, **When** the operator runs the installer, **Then** it skips `graphify install` without prompting for that registration step.

### Edge Cases

- What happens when an agent needs to author code on a feature branch whose snapshot predates a large amount of work already merged into the tracked branch? The snapshot intentionally reflects the fork point, not current tracked-branch state — this is by design (User Story 3), not a bug to fix here.
- What happens when HEAD on a tracked branch advances through a rebase or hard reset rather than a normal commit? The staleness check compares the graph's recorded revision against current HEAD regardless of how HEAD moved, so the agent-side backstop (User Story 1) still triggers a refresh.
- What happens when a human commits directly (no agent session open) on a tracked branch? The post-commit hook still fires, since it is git plumbing independent of any agent being present — the graph stays current either way.
- What happens when the `post-commit` hook's refresh invocation itself fails (graphify crashes, times out, corrupted graph)? The commit still succeeds — the hook warns rather than blocks, and the resulting stale freshness marker is caught by the agent-side backstop the next time an agent needs the graph (see Clarifications).
- What happens when the agent's own graph consultation fails mid-session (the `graphify query`/`path`/`explain` invocation errors or times out)? The agent warns and proceeds with authoring rather than blocking, flagging the skipped consultation for a manual check later (see Clarifications).
- What happens if the operator suspends the rule for a session and then starts a new session without re-suspending? The rule applies again immediately — suspension never persists past the session that requested it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The atom MUST contribute a constitution principle file that becomes part of an adopting project's assembled constitution via the existing `haex constitution assemble` mechanism.
- **FR-002**: The contributed principle MUST require agents to consult the project's graphify knowledge graph before authoring any new named function, class, component, store, module, or CLI command.
- **FR-003**: The contributed principle MUST require agents to prefer extending an existing identical, near-identical, or incomplete artifact discovered in the graph over authoring a duplicate — regardless of whether that artifact is currently exported.
- **FR-004**: The contributed principle MUST require the agent to name the candidate, state the delta versus what is needed, and propose the extension, rather than silently authoring a parallel implementation. When similarity is borderline (not clearly identical/near-identical, not clearly independent) or extending the existing artifact would risk scope creep, the agent MUST ask the operator rather than deciding autonomously. If the graph consultation itself fails (the invocation errors or times out), the agent MUST warn and proceed with authoring rather than blocking, flagging the skipped consultation for a manual check later.
- **FR-005**: The contributed principle MUST allow the operator to suspend it for a single session via an explicit instruction, and the suspension MUST NOT persist beyond that session.
- **FR-006**: The atom MUST provide a git `post-commit` hook that incrementally refreshes `graphify-out/` after every commit on a tracked branch. If the refresh invocation itself fails, the hook MUST warn rather than block — the commit MUST succeed regardless, leaving the freshness marker stale for the agent-side backstop (FR-010) to catch on next use.
- **FR-007**: Tracked branches MUST be determined as the repository's auto-detected default branch, plus any additional branches declared in `.haex-hive.json`'s `tracked_branches[]`.
- **FR-008**: The atom MUST provide a git `post-checkout` hook that copies `graphify-out/` from the parent worktree into a newly created worktree, if not already present there.
- **FR-009**: `graphify-out/` MUST never be committed to version control in an adopting repo.
- **FR-010**: The contributed principle's freshness requirement (bootstrap when absent, refresh when stale) MUST hold for the agent even when the git hooks are not installed or have been bypassed.
- **FR-011**: The atom's installer MUST verify the `graphify` CLI is present on PATH. If absent, it MUST prompt the operator to install it via `sys.executable -m pip install graphifyy` using the invoking Python interpreter (default Yes); on decline, pip failure, or failed PATH re-check, the installer MUST refuse with actionable instructions, making no other changes.
- **FR-012**: The atom's installer MUST use an explicit, unversioned local registration state (the git-config key `graphify-first-authoring.registration=installed`) to decide whether the current clone has completed graphify harness registration. If that marker is absent, it MUST prompt before invoking `graphify install`; on successful invocation it MUST write the marker, and on decline it MUST continue with manual follow-up instructions while leaving the marker unset. The presence of `graphify-out/` MUST NOT be used as registration state because bootstrap, refresh, and snapshots may create it independently. Installation of the `graphify` package itself (`graphifyy`) is governed by FR-011's prompt; the installer MUST NOT silently install it into the operator's Python environment outside that prompt.
- **FR-013**: The atom's installer MUST refuse to run outside a tracked branch, naming the current branch and the expected tracked branch(es).
- **FR-014**: The atom's installer MUST refuse to overwrite a pre-existing git hook at either target hook path rather than silently replacing it.
- **FR-015**: Git hooks installed by the atom MUST use a shebang resolved at install time to whichever of `python3`/`python` is actually present on the installing machine's PATH.
- **FR-016**: The contributed principle text MUST reference plain `graphify` CLI invocations rather than any single agent harness's specific invocation syntax.
- **FR-017**: The atom's installer MUST add `graphify-out/` to the adopting repo's `.gitignore` if not already present.

### Key Entities

- **graphify-out/**: The knowledge-graph artifact directory the rule depends on. Authoritative on tracked branches; a discarded fork-point snapshot on feature branches/worktrees.
- **graphify-out/.meta.json**: Freshness marker recording the graph's `indexed_at_sha`, compared against current HEAD to decide bootstrap vs. refresh vs. proceed.
- **Contributed constitution text**: The atom's `constitution.md`, merged into `.haex-hive/constitution.md` by `haex constitution assemble` alongside any other adopted constitution-contributing atoms.
- **Tracked branch set**: The detected default branch plus `.haex-hive.json`'s optional `tracked_branches[]` — the set of branches on which the graph is considered authoritative and auto-refreshed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can go from "atom not installed" to "rule enforced and graph auto-refreshing" by running exactly one installer command, with no separate manual steps to install or wire up the underlying graph tool.
- **SC-002**: Across a working session, an agent bound by the adopted rule never authors a new function/class/component that is identical or near-identical to one already present and discoverable in the graph, without first surfacing it to the operator.
- **SC-003**: A newly created feature-branch worktree has a usable, non-empty knowledge graph available immediately, with no full rebuild required before the first authoring decision.
- **SC-004**: Under normal operation (no tool failure), the graph on a tracked branch never falls further behind than the most recent commit on that branch, regardless of whether the commit came from an agent session or a direct human commit. When a refresh does fail, the next agent-initiated consultation still reflects the current commit, since the agent-side backstop refreshes on demand.

## Assumptions

- The `graphify` CLI (package `graphifyy`) may be present already (installed via `pip install graphifyy`) or offered by the atom's installer via the opt-in prompt in FR-011; this atom does not silently mutate the operator's Python environment.
- The operator's repo has already adopted haex-hive's Spec 007 manifest v2 machinery (`.haex-hive.json`, atom resolution, `haex constitution assemble`) — this atom is consumed the same way any other atom is.
- Multi-agent-harness delivery of the contributed constitution text rides the existing Spec 007 D6 pointer-block mechanism (`CLAUDE.md`/`AGENTS.md`/`GEMINI.md` pointing at `.haex-hive/generated/rules.md`); no new per-harness delivery work is in scope here.
- Cross-repo hydration of this atom's non-constitution files (hooks, installer) for consumers other than haex-hive itself is out of scope, deferred to the existing Spec 010 `haex install` territory.
- A formal `requires` field on atom manifests (for declaring a dependency on an external tool or another atom) does not exist yet and is out of scope here; this atom's installer checks its one dependency (the `graphify` CLI) ad-hoc.
