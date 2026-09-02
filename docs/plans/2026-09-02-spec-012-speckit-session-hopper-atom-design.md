# Spec 012: Speckit Session Hopper Atom (Design Preview)

**Status**: Design preview. Not yet a spec. Captured 2026-09-02 as the requirements source for a subsequent `/speckit-specify` invocation that creates `specs/012-speckit-session-hopper-atom/`.

**Purpose**: define a first concrete `speckit-workflow` atom (Spec 011 atom-kind) that prompts the operator, before every `command:` step of a speckit workflow, to run that step in a new agent session (fresh context) rather than inline in the current session. The prompt is advisory: the operator picks new-session or inline for each step. The atom is fully declarative and portable across every LLM host, because the mechanism is Constitution rule plus a text-printing hook, with no client-specific subagent API.

**Related**:
- [Spec 011: Speckit Workflow Atom](2026-09-02-spec-011-speckit-workflow-atom-design.md): defines the `speckit-workflow` atom kind (`contributes.speckit_workflow`, `contributes.speckit_hooks`, `contributes.constitution`, hook publication under `.specify/extensions/workflow-atoms/<atom-id>/`, `workflow-registry.json.active_workflow` selection). This atom is an instance of that kind.
- [Spec 007: Unified Manifest v2](2026-08-28-spec-007-unified-manifest-design.md): atom-manifest baseline; publisher-manifest shape.
- [Spec 008: Install Transaction](../../specs/008-install-transaction/): multi-source constitution merge; delete-orphans on removal.
- Constitution v1.4.0, "Declared speckit workflow adherence": the bullet this atom becomes binding under when selected via `active_workflow`.
- [speckit-community workflows catalog](https://speckit-community.github.io/extensions/search?q=workflows): other workflow families (V-Model, bugfix-first, strict-TDD, ...). Motivation for keeping this atom workflow-agnostic in its hook script.

---

## What this covers

A single atom, published from a new sibling repo `haexmas/atoms`, that:

1. Ships a `workflow.yml` mirroring the bundled `speckit` "Full SDD Cycle" steps (`specify`, `clarify`, `plan`, `tasks`, `analyze`, `implement`) with the same review gates between them.
2. Wires every `command:` step's `hooks.before` to one shared shell script that prints an English prompt block on stdout, telling the operator how to run the next step in a new session (which worktree to cd into, which branch is expected, which `/speckit-<step>` slash-command to invoke).
3. Ships a small `constitution.md` fragment that turns the printed prompt into a binding pre-step protocol: agents whose `active_workflow` names this atom MUST display the block verbatim, wait for the operator's answer, and only continue the step inline if the operator replies `inline`.

Adoption is via `.haex-hive.json`, same as any other atom. Making this workflow binding is a two-step operator action: adopt the atom, then set `workflow-registry.json.active_workflow` to the atom's id.

## What this does NOT cover (deliberately)

- **Client-specific subagent APIs**: no adapter that spawns a Claude Code Task, a Codex agent, or a Cursor background agent. The mechanism is prompt-and-wait; the operator opens the new session by hand. A later spec MAY add native-subagent auto-start when available; not needed for the MVP the operator asked for.
- **Runtime enforcement**: no CI check, no pre-commit hook, no mechanical refusal when a step is run inline instead of in a new session. The rule is stated in the Constitution fragment and enforced by agent compliance, same as every other Constitution rule.
- **Hard-coded per-step context lists**: the hook does NOT enumerate `spec.md`, `plan.md`, `tasks.md`, or any other file names, because different community workflows (V-Model, bugfix-first, ...) produce different artefacts. The new session discovers relevant context itself through the normal speckit slash-command entry path plus the user-global CLAUDE.md, which loads `.haex-hive.json` and the constitution on session start.
- **Extension dependencies**: this atom declares no `required_extensions` and no `optional_extensions`. Isolation behaviour needs no speckit-community extension.
- **Deviation from the bundled step list**: the workflow.yml is a session-hopping mirror of the bundled `speckit` cycle, not a new step design. Different step topologies are out of scope; a downstream atom can fork this one for a bugfix-first or V-Model variant.

## Terminology

- **Isolated step**: a `command:` step the operator runs in a fresh agent session (a new conversation with cleared context) that lives in the same git worktree and on the same branch as the main session.
- **Main session**: the operator's ongoing conversation, where reviews, gates, clarifications, and coordination happen.
- **Prompt block**: the multi-line English text the `before` hook prints on stdout; the agent MUST show it to the operator verbatim and MUST NOT run the step until the operator answers.
- **`inline` reply**: the sentinel word the operator types to override the recommendation and let the current agent run the step in the main session anyway.

## Architecture

### Atom identity

- Publisher repo: `haexmas/atoms` (a new sibling to `haexmas/haex-hive`), holding multiple atoms over time. First atom is this one.
- Publisher-manifest id: `com.github.haexmas.atoms`.
- Atom id: `com.github.haexmas.atoms.speckit-session-hopper`.
- Workflow id inside `workflow.yml`: `speckit-session-hopper` (this is what `workflow-registry.json.active_workflow` names; Spec 011 FR-002 publishes the atom's workflow at `.specify/workflows/<atom-id>/`, and the id inside the workflow may be the short form).

### Repo layout

```
haexmas/atoms/                                # git repo root
├── manifest.json                             # publisher-manifest
├── README.md                                 # adoption instructions per atom
└── speckit-session-hopper/
    ├── manifest.json                         # atom-manifest
    ├── workflow.yml
    ├── constitution.md                       # fragment
    └── hooks/
        └── before-step.sh
```

### Publisher-manifest

`haexmas/atoms/manifest.json`:

```json
{
  "haex_hive_version": "2",
  "publisher": "com.github.haexmas.atoms",
  "atoms": {
    "com.github.haexmas.atoms.speckit-session-hopper": {
      "path": "speckit-session-hopper",
      "version": "0.1.0"
    }
  }
}
```

### Atom-manifest

`haexmas/atoms/speckit-session-hopper/manifest.json`:

```json
{
  "haex_hive_version": "2",
  "id": "com.github.haexmas.atoms.speckit-session-hopper",
  "version": "0.1.0",
  "priority": 30,
  "contributes": {
    "speckit_workflow": "workflow.yml",
    "constitution": "constitution.md",
    "speckit_hooks": "hooks"
  }
}
```

### workflow.yml

Mirrors the bundled `speckit` cycle. Every `command:` step gains one `hooks.before` entry pointing at the shared script. The script destination path uses the reserved atom-owned namespace from Spec 011 FR-003.

```yaml
schema_version: "1.0"
workflow:
  id: "speckit-session-hopper"
  name: "SDD cycle with per-step session isolation"
  version: "0.1.0"
  author: "haexmas"
  description: "Same steps as bundled speckit, but prompts the operator to run each command step in a fresh agent session."

requires:
  speckit_version: ">=0.7.2"

inputs:
  spec:
    type: string
    required: true

steps:
  - id: specify
    command: speckit.specify
    hooks:
      before:
        - script: .specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh
          args: ["specify"]
    input:
      args: "{{ inputs.spec }}"

  - id: review-spec
    type: gate
    message: "Review the generated spec before planning."
    options: [approve, reject]
    on_reject: abort

  - id: clarify
    command: speckit.clarify
    hooks:
      before:
        - script: .specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh
          args: ["clarify"]

  - id: plan
    command: speckit.plan
    hooks:
      before:
        - script: .specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh
          args: ["plan"]

  - id: review-plan
    type: gate
    message: "Review the plan before generating tasks."
    options: [approve, reject]
    on_reject: abort

  - id: tasks
    command: speckit.tasks
    hooks:
      before:
        - script: .specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh
          args: ["tasks"]

  - id: analyze
    command: speckit.analyze
    hooks:
      before:
        - script: .specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh
          args: ["analyze"]

  - id: implement
    command: speckit.implement
    hooks:
      before:
        - script: .specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh
          args: ["implement"]
```

Whether the review gates additionally recommend a new session for the review itself is an open question (see below). Baseline: gates stay in the main session, because their reason for existing is the operator's decision.

### hooks/before-step.sh

One script for every step. It reads the step name from `$1`, discovers the worktree root and branch from `git`, and prints the English prompt block on stdout. No file lookup, no network, no jq.

```sh
#!/usr/bin/env sh
set -eu

STEP="${1:-<step>}"
BRANCH="$(git branch --show-current 2>/dev/null || echo '<unknown>')"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

cat <<EOF
======================================================
Next step: /speckit-${STEP}
Recommendation: run this in a NEW session (isolated context).

Open a new session in the same worktree:
    cd ${ROOT}
Expected branch: ${BRANCH}
Then run:
    /speckit-${STEP}

Or reply "inline" to keep this agent running the step here.
======================================================
EOF
```

Notes:

- The script uses POSIX `sh` (not bash) for portability across the operator's environment.
- It does NOT reference the constitution or any spec artefacts. The new session finds those itself: the user-global CLAUDE.md loads `.haex-hive.json` and the constitution automatically on session start (haex-hive detection); the `/speckit-<step>` slash-command reads whatever `specs/<slug>/` files are relevant for that step; `active_workflow` is read by any agent that cares.
- It falls back gracefully outside a git worktree (`<unknown>` branch, current directory as root). The atom is not intended for non-git use; that fallback exists only to avoid a shell error if someone accidentally invokes the script by hand.
- Executable bit: Spec 011 FR-003 states hook payloads are copied byte-identically. If `haex install` does not currently preserve the mode bit for atom-shipped scripts, that is a Spec 011 follow-up ticket, not a change to this design. In the interim the operator or the hook runner MUST `chmod +x` the published script.

### constitution.md (fragment)

Kept short. English. States one MUST rule.

```markdown
## Per-step session isolation

Sessions whose `active_workflow` resolves to
`com.github.haexmas.atoms.speckit-session-hopper` MUST, before every
`command:` step of that workflow:

1. Execute the step's `hooks.before` script and capture its stdout.
2. Display the captured block to the operator verbatim.
3. Wait for the operator's answer.
4. Continue the step in the current session only if the operator's
   answer is exactly `inline`. On any other answer, stop and defer
   the step to the new session the operator opens; the current
   session resumes at the next review gate once the new session's
   output is on disk.
```

The multi-source merge (Spec 011 FR-004) appends this fragment under
`## Workflow-Contributed Rules` with the atom-id byline; the header
above becomes an `### Per-step session isolation` subsection under the
byline heading, so no header conflict occurs.

## Adoption flow

Documented in `haexmas/atoms/README.md` and mirrored in this design for the plan.

1. Pin the atom in `.haex-hive.json`:

   ```json
   {
     "includes": ["com.github.haexmas.atoms.speckit-session-hopper"],
     "revision": "<full-40-char-sha>",
     "source": "https://github.com/haexmas/atoms"
   }
   ```
2. Run `haex install --llm=file`. Review the constitution candidate. Rerun `haex install --accept-merged <candidate>`.
3. Edit `.specify/workflows/workflow-registry.json` and set `active_workflow` to `com.github.haexmas.atoms.speckit-session-hopper`. (Spec 011 does not require a helper for this yet; a plain text edit suffices.)

Post-adoption state:

- `.specify/workflows/com.github.haexmas.atoms.speckit-session-hopper/workflow.yml` published.
- `.specify/extensions/workflow-atoms/com.github.haexmas.atoms.speckit-session-hopper/before-step.sh` published.
- `.haex-hive/constitution.md` contains the "Per-step session isolation" subsection under `## Workflow-Contributed Rules`.
- Every subsequent agent session opened in this repo, reading its user-global CLAUDE.md, loads the constitution, sees the MUST rule, and consequently prompts before every command step.

## Removal (downgrade)

Removing the atom entry from `.haex-hive.json` and rerunning `haex install`
triggers Spec 011 US3 (delete-orphans): the workflow directory, the hook
directory, and the constitution fragment are all removed atomically; if
`active_workflow` still named this atom, it is reset to `null` and stderr
emits `workflow-atom-reset-to-default`. No atom-specific removal logic
is needed.

## Assumptions

- **Same-worktree new sessions**: the operator opens the new session in the same git worktree and on the same branch as the main session. The atom does NOT recommend or automate worktree-per-step. Rationale: worktree-per-step multiplies filesystem state without buying isolation the operator asked for, and speckit artefacts live inside `specs/<slug>/` on the current worktree either way.
- **Advisory-only enforcement**: compliance rests on the Constitution rule, which agents are already required to obey under Principle II family (haex-hive constitution NON-NEGOTIABLEs). No mechanical guard.
- **Bundled `speckit` remains available**: adopting this atom does not remove the bundled workflow. The operator can switch back by setting `active_workflow` to `speckit` (or `null`, which resolves to `speckit`), per Spec 011 FR-006/FR-008.
- **English text**: all operator-facing text shipped by the atom is English. The atom is meant to be publisher-neutral and locale-agnostic.

## Open questions

1. **Review gates and isolation**: should the workflow additionally recommend a new session for review-gate steps? Default: no, because gates are the operator's decision moment and belong in the main session. If a future variant wants to isolate long "analyze" or "review-plan" reads, a fork of this atom can add `hooks.before` to gate steps too.
2. **Executable bit on published hook script**: Spec 011 FR-003 says byte-identical copy. Does that include the mode bit, or does the installer need an explicit rule for `speckit_hooks/**` payloads? Filed as a Spec 011 clarification, not blocking for this design (README can instruct `chmod +x` as a workaround).
3. **`inline` as the sentinel word**: any risk of collision with an operator who genuinely wants to say "inline" as text? Extremely unlikely inside a "new-session-or-inline" prompt, but the constitution rule could be tightened to "exactly the single token `inline`, case-insensitive" if collisions ever surface.
4. **Second `haexmas/atoms` occupant**: this design leaves publisher-manifest room for future atoms in the same repo. Adding a second atom is a follow-up PR against `haexmas/atoms` that appends to `manifest.json.atoms`. No design change here.

## Deferred to later specs

- **Native-subagent auto-start** on hosts that support it (Claude Code Task, Codex, ...). Would need a per-host adapter and a workflow.yml field like `hooks.before.mode: subagent`. Reasonable for a Spec-012-successor once at least two host adapters exist.
- **Verify-only mode reporting isolation status** (relies on Spec 008 US2 `--verify-only`, still deferred).
- **Different step topologies**: bugfix-first, V-Model, strict-TDD. Each becomes its own atom in `haexmas/atoms/` or a separate publisher repo; they can share the same `before-step.sh` pattern.
