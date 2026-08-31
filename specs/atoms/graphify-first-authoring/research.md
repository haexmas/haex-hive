# Phase 0 Research: graphify-first-authoring atom/molecule

No `[NEEDS CLARIFICATION]` markers remain in the Technical Context — the preceding brainstorm, the design doc, and the `/speckit.clarify` pass already resolved every open question this feature raised. This document consolidates those decisions into the Decision/Rationale/Alternatives format for the planning record, rather than re-opening them.

## D1. Interpreter resolution for git hooks

**Decision**: `install.py` resolves `shutil.which("python3") or shutil.which("python")` once, at install time, and writes the literal resolved path into each hook's shebang line.

**Rationale**: `.git/hooks/` is never committed — it is always a per-machine, locally-installed artifact — so resolving the interpreter per machine at install time, rather than guessing a single portable shebang name, is free: the install step already has to run once per clone regardless. Windows' python.org installer provides only `python.exe`; many modern Linux distributions provide only `python3`. No single literal name satisfies both.

**Alternatives considered**: A fixed `#!/usr/bin/env python3` shebang (fails on vanilla Windows installs with no `python3.exe`); a `#!/bin/sh` polyglot dispatcher trying `python3` then falling back to `python` (adds a shell dependency the repo's Python-only hook policy, Spec 007 D1, exists specifically to avoid).

## D2. Cross-platform hook execution

**Decision**: Native git hooks (`post-commit`, `post-checkout`), plain Python, no shell wrapper.

**Rationale**: Git for Windows' own hook-execution path reads a hook file's shebang line and dispatches to the named interpreter directly — it does not rely on the Windows OS understanding `#!`. Combined with D1's per-machine interpreter resolution, this makes a Python-shebang hook genuinely cross-platform (Linux, macOS, WSL2, native Windows).

**Alternatives considered**: An agent-managed-only approach (freshness check purely inside the agent's own behavior, no git hooks at all) was drafted and then reverted during the brainstorm — it would have covered only agent-initiated work, missing direct human commits and other tooling entirely.

## D3. Worktree/feature-branch graph handling: snapshot, not symlink

**Decision**: `post-checkout` copies `graphify-out/` from the explicitly
selected parent worktree into a newly created worktree. The supported creation
command passes that path through `GRAPHIFY_PARENT_WORKTREE`; Git does not expose
the source worktree to the hook, so the hook must not infer it from list order.

**Rationale**: A symlink was considered and rejected — not because of a genuine Windows blocker (symlinks work fine within this constitution's declared OS scope: Linux/macOS/WSL2), but because a snapshot is *semantically correct*: the feature branch is meant to see the pre-branch fork-point state, not a live view of the tracked branch's ongoing changes. A snapshot also degrades gracefully — it is simply discarded with the branch, no cleanup logic needed, and it works even if the constitution's OS scope is ever widened to native Windows without WSL.

**Alternatives considered**: Symlink (rejected for the semantic reason above, not portability); an environment-variable indirection (`HAEX_GRAPHIFY_OUT`) (rejected — would require every consuming tool to honor a non-standard env var, whereas a plain directory copy needs no cooperation from anything).

## D4. Tracked-branch detection

**Decision**: Auto-detect the repository's default branch via `git symbolic-ref refs/remotes/origin/HEAD`; `.haex-hive.json`'s optional `tracked_branches[]` names any additional long-lived branches.

**Rationale**: Branch-naming conventions vary too much across teams (`main`/`master`/`trunk`, `develop`/`dev`/`development`, optional `staging`) to hardcode. Auto-detection covers the common single-branch case with zero configuration; the optional array covers multi-branch teams without forcing configuration on everyone else.

**Alternatives considered**: Config-only (every consumer must declare tracked branches explicitly) — rejected as unnecessary friction for the common case.

## D5. Tool-failure semantics (from `/speckit.clarify`)

**Decision**: Both the `post-commit` hook's refresh and the agent's own graph consultation warn and continue/proceed on failure, rather than blocking.

**Rationale**: Recorded in spec.md's Clarifications section. A broken `graphify` (crash, timeout, corrupted graph) is an auxiliary-tool failure, not a defect in the code being committed or authored — blocking all commits or all authoring on that basis is a disproportionate operational risk. The agent-side freshness backstop (bootstrap-when-absent, refresh-when-stale) already exists as the safety net that catches a stale graph left behind by a failed hook refresh.

**Alternatives considered**: Hard-block (rejected — one bad graphify release could brick every commit on the tracked branch); configurable per-repo warn-vs-block (rejected as unnecessary complexity for a first version; nothing in the brainstorm or clarify pass surfaced a concrete need for it).

## D6. Dependency handling: no schema growth, ad-hoc installer check

**Decision**: `install.py` checks `shutil.which("graphify")` directly; no `requires` field is added to the atom manifest schema.

**Rationale**: Confirmed by grep across Spec 007's contracts that no dependency-declaration field exists anywhere in `atom-manifest.v2.schema.json`. Growing the schema for one atom's need is scope creep; solving it ad-hoc in the one place that needs it now, while naming the gap explicitly for a future spec, matches how Spec 007's own design doc already treats similarly-shaped deferred items (multi-agent adapters, blueprint hydration).

**Alternatives considered**: A formal `requires: { tools: [...], atoms: [...] }` manifest field (deferred — real candidate for a future spec once more than one atom needs it, not solved here).

## D7. Multi-agent-harness delivery: no new work

**Decision**: The contributed `constitution.md` text rides Spec 007's existing D6 pointer-block mechanism (`CLAUDE.md`/`AGENTS.md`/`GEMINI.md` → `.haex-hive/generated/rules.md`) — no per-LLM-harness adapter work is needed from this atom.

**Rationale**: `graphify` itself already ships a built-in multi-platform installer (`graphify install [--platform P]`, confirmed on disk covering ~18 harnesses) for the *tool-invocation* side. The *policy* side (the "you MUST consult graphify" rule) is just text, and Spec 007 already solved cross-harness text delivery generically. Constitution text in this atom therefore references plain `graphify` CLI invocations (`graphify query "..."`, not `/graphify`), so it reads correctly regardless of which harness loads it.

**Alternatives considered**: A bespoke per-harness adapter for this atom's rule text specifically (rejected — would duplicate Spec 007 D6 for no benefit).
