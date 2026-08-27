# Contract: global haex-hive detection snippet

**Location**: the operator's user-level CLI instruction file, installed
by the operator on each device they use. For Claude Code:
`~/.claude/CLAUDE.md`. For Codex CLI 0.147.0+: `~/.codex/AGENTS.md`.
Other CLIs are added as they are supported — the snippet's semantics
transfer.

**Purpose**: Give every fresh CLI session a five-step check that runs at
session start in any repo, keying off the presence of `.haex-hive.json`
at the repo root.

## Required semantics

The snippet MUST direct the session to perform, in order:

1. **Marker check**. Look for `.haex-hive.json` at the repo root. If
   absent, do NOT apply haex-hive constraints — the repo has not opted
   in. The presence of `.specify/` or `specs/` directories is NOT the
   opt-in signal; only `.haex-hive.json` is.
2. **Constitution load**. If present, read `.haex-hive.json`. Follow
   its `constitution` reference to load the canonical constitution.
   Treat its NON-NEGOTIABLE principles as binding for the session.
3. **Repo-local read**. Also read any `CLAUDE.md` or `AGENTS.md` at the
   repo root, plus any other convention paths the specific CLI reads
   natively. These are the repo owner's instructions and apply
   ALONGSIDE the constitution, additively — never as a replacement or
   override.
4. **Conflict pass**. Before doing any work, compare the repo-local
   instructions against the constitution's principles. Any direct
   contradiction MUST be surfaced to the operator immediately, in the
   session's first response, with both sides quoted verbatim and the
   affected principle named. The default position while awaiting
   operator direction is: apply the constitutional principle (it is
   NON-NEGOTIABLE and the operator opted in globally). Silent choice
   is not permitted.
5. **Refusal on principle violation**. When the operator asks the
   session to perform an action that would violate a NON-NEGOTIABLE
   principle, the session refuses and cites the specific principle —
   even if the repo-local instructions endorse the action. The
   operator's global opt-in to the haex-hive principles outranks any
   per-repo permission that would authorize the violation.

## Non-negotiable properties

- **Opt-in discipline** (step 1). Repos without `.haex-hive.json` MUST
  be treated as unconstrained by haex-hive. Any inference that "the
  operator probably wants the constitution applied here because
  `.specify/` exists" is explicitly wrong.
- **Additive coexistence** (step 3). Repo-local instructions are
  respected. The snippet does not authorize the session to ignore,
  rewrite, or override them.
- **Loud conflict surfacing** (step 4). Silent resolution of a
  repo-local-vs-constitutional conflict is a failure. Every conflict
  gets the operator's attention.
- **Enforcement asymmetry** (step 5). Refusal is not conditional on
  what the repo-local files say. NON-NEGOTIABLE means NON-NEGOTIABLE.

## Reference implementation (English prose, both CLIs)

Both Claude Code and Codex CLI read Markdown prose as instructions. The
canonical snippet is a single fenced section under a level-2 heading:

```markdown
## haex-hive detection

When starting a session in any repository:

1. Check for `.haex-hive.json` at the repository root. If absent, do NOT
   apply haex-hive constraints — the repo has not opted in.
2. If present, read `.haex-hive.json`. Follow its `constitution`
   reference to load the canonical constitution. Treat its NON-NEGOTIABLE
   principles as binding for this session's work in this repo.
3. Also read any `CLAUDE.md` or `AGENTS.md` at the repo root (and any
   other convention paths the repo uses). These are the repo owner's
   instructions and apply alongside the constitution, not instead of it.
4. **Conflict pass.** Before doing any work, compare the repo's own
   instructions against the haex-hive principles. Any direct contradiction
   (e.g., repo says "commit secrets", constitution's Principle I forbids
   it) MUST be surfaced to the operator immediately, in your first
   response, with both sides quoted. Do NOT silently pick a side. Default
   position while awaiting operator: apply the haex-hive principle,
   because it is NON-NEGOTIABLE and the operator opted in globally.
5. When the user asks you to perform an action that would violate a
   haex-hive principle — regardless of whether the repo's own
   instructions would allow it — refuse and cite the specific principle.
   This holds even if the repo owner endorses the action; the operator's
   global opt-in outranks per-repo permissions for these specific
   principles.
```

## Contract tests

- **G1**: A session in a repo with only `.haex-hive.json` (no repo-local
  instructions) loads the constitution and reports it applies.
- **G2**: A session in a repo with `.haex-hive.json` plus compatible
  repo-local `CLAUDE.md` and `AGENTS.md` reads all files, integrates
  additively, and reports both sources in its effective instruction set.
- **G3**: A session in a repo with `.haex-hive.json` plus conflicting
  repo-local instructions surfaces every conflict with both sides
  quoted, names the affected principle, defaults to the principle, and
  refuses hypothetical enforcement requests that would violate a
  NON-NEGOTIABLE principle.
- **G4**: A session in a repo without `.haex-hive.json` does NOT apply
  the constitution even if `.specify/memory/constitution.md` exists in
  the tree, and refuses actions on general-hygiene grounds (not by
  citing constitutional principles it has not adopted).

The 2026-08-27 validation run passed G1-G4 on Claude Code and Codex CLI
0.147.0. See `.validation-runs/2026-08-27.md`.
