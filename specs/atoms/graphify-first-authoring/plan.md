# Implementation Plan: graphify-first-authoring atom/molecule

**Branch**: `20260831-082047-graphify-first-authoring` | **Date**: 2026-08-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/atoms/graphify-first-authoring/spec.md`

## Summary

Package an opt-in atom — not part of haex-hive's core constitution — that any adopting repo (including haex-hive itself) can add to `.haex-hive.json` to require agents to consult the project's `graphify` knowledge graph before authoring new named code, preferring extension of existing artifacts over duplication. The atom contributes a constitution principle (merged via the existing `haex constitution assemble` mechanism), a pair of cross-platform Python git hooks that keep `graphify-out/` current on tracked branches and snapshot it into new worktrees, and an installer that handles the atom's one external dependency (the `graphify` CLI) without silently mutating the operator's environment. `graphify` owns and writes the freshness marker; the atom's refresh helper only invokes the CLI. All open design questions were resolved in a prior brainstorm ([design doc](../../../docs/plans/2026-08-31-graphify-first-authoring-design.md)) and a `/speckit.clarify` pass (two tool-failure-semantics questions, both resolved to warn-and-continue); nothing here needs further research to begin implementation.

## Technical Context

**Language/Version**: Python 3.10+ (matches `pyproject.toml`'s `requires-python` and Spec 007's D1 Python-only hook mandate — no shell/PowerShell hook variants)
**Primary Dependencies**: `graphify` CLI (external, package `graphifyy`, invoked as a subprocess — not a Python import dependency of this atom); haex-hive's existing atom/manifest v2 and `haex constitution assemble` machinery (consumed as-is, not modified)
**Storage**: N/A — `graphify-out/` is graphify's own artifact directory, not a store this feature manages
**Testing**: pytest (matches haex-hive's existing `dev` extras: `pytest>=7.4`, `pytest-subprocess>=1.5`)
**Target Platform**: Linux, macOS, WSL2, and native Windows (via the standard Git-for-Windows distribution) — hook shebangs are resolved per-machine at install time, not baked in
**Project Type**: atom package (contributed constitution content + a small installer + two git hooks), consumed through haex-hive's existing atom mechanism — not new application code added to the `haex_hive` CLI package
**Performance Goals**: not specified — incremental refresh (changed paths only, no full rebuild) is a functional requirement (FR-006), not a latency target; a hard number was explicitly deferred as low-impact during `/speckit.clarify`
**Constraints**: hooks MUST NOT block git operations on their own failure (FR-006, FR-004 — warn-and-continue/warn-and-proceed); `.git/hooks/*` are never committed to any repo; the installed hook shebang is resolved to whichever of `python3`/`python` is present at install time, not assumed
**Scale/Scope**: one atom, self-adopted by haex-hive as its own first consumer of it; cross-repo hydration for other consumers' non-constitution files is explicitly out of scope here (Spec 010 territory, per the spec's Assumptions)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Justification |
|---|---|---|
| I. No Secrets in Git | PASS | This atom introduces no secret material of any kind. |
| II. No Local Absolute Paths in Versioned Config | PASS | The one absolute path this feature produces — the resolved `python3`/`python` interpreter path baked into each installed hook's shebang — lives in `.git/hooks/`, which is never committed by git in any repo. Nothing this atom commits (`manifest.json`, `constitution.md`, `.gitignore` entry) contains a local path. |
| III. Project Identity Is Device-Independent | PASS | Not applicable — this atom does not address other projects or devices. |
| IV. Cross-Repo References Pin Immutable Revisions | PASS | This atom is referenced the same way any Spec 007 atom is — by `repository + full commit SHA + repo-relative path` in a consumer's `.haex-hive.json`. This feature does not need, and does not introduce, any new reference mechanism. |
| V. External Sources Are Opt-in Per Project | PASS — directly motivates this design | This entire feature exists *because of* Principle V: it is deliberately excluded from haex-hive's core constitution and shipped as a separate atom precisely so no project inherits it without an explicit `atoms[]` entry. |
| VI. Self-Modifying Instructions Are Always Review-Gated | PASS, with reasoning | Two distinct actions need checking against this principle. (a) The contributed *instruction* content (`constitution.md`) already flows through the existing, reviewed path: it only takes effect once `haex constitution assemble` writes the reviewable, committed `.haex-hive/constitution.md` — no different from any other Spec 007 atom. (b) The installer's local actions (`.git/hooks/*`, a `.gitignore` line, and an unversioned local git-config registration marker) are mechanical repo plumbing, not instruction/skill/permission content the principle's review-gate language is about; they enable enforcement of already-reviewed instructions rather than constituting new ones. A third action — optionally invoking `graphify install`, which touches the operator's *global*, non-repo-scoped agent config — sits outside any repo's history entirely, so the repo-scoped PR-review mechanism doesn't literally apply; FR-012's explicit local-registration marker is the analogous safeguard for that case. |
| VII. Relay Unavailability Never Blocks Local Work | PASS | This feature has no Nostr relay dependency of any kind; all graph consultation and refresh happens against local disk. |
| VIII. No Concealment Instructions in Agent Output | PASS | The "refuse-then-propose" behavior (FR-004) requires maximal transparency about any candidate found — the opposite of concealment. Nothing in this design asks an agent to withhold information from the operator. |

**Development Workflow — phasing discipline**: this feature builds on Spec 007's atom/manifest v2 machinery (top-level roadmap Phase 2, "harness registry + multi-tool compiler"). That prerequisite is confirmed already in daily use on this repo — `.haex-hive.json` here is already on `haex_hive_version: "2"` with a populated `atoms[]` array. This feature does not get ahead of its phase's prerequisites.

**Development Workflow — commits/PR**: all commits during implementation follow Conventional Commits v1.0.0; the branch lands on `main` via PR (rebase-merge or merge-commit, never squash), per the constitution's Development Workflow section.

No entries needed in Complexity Tracking — every principle passes on direct reasoning, not by claiming a justified exception.

**Post-Phase-1 re-check**: the data model, contracts, and quickstart produced in Phase 1 introduce no new committed artifact, path, or cross-device mechanism beyond what this table already covers — conclusions unchanged.

**Validation boundary**: T024 and T025 validate constitution assembly and source attribution only. They do not replace T008's pending agent-behavior check.

## Project Structure

### Documentation (this feature)

```text
specs/atoms/graphify-first-authoring/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md         # Phase 1 output (/speckit.plan command)
├── contracts/            # Phase 1 output (/speckit.plan command)
│   ├── install.cli.md
│   └── git-hooks.md
└── tasks.md              # Phase 2 output (/speckit.tasks command — NOT created by /speckit.plan)
```

### Source Code (repository root)

This feature does not fit the generic src/tests application template — its primary deliverable is a **content/config package** (a Spec 007 atom) consumed through haex-hive's existing atom mechanism, not new code added to the `haex_hive` CLI package itself.

```text
.specify/atoms/graphify-first-authoring/     # the atom package — this feature's primary deliverable
├── manifest.json                            # atom manifest: contributes.constitution: "constitution.md"
├── constitution.md                          # the contributed principle text
├── hooks/
│   ├── post-commit                          # thin entrypoint; shebang resolved by install.py
│   ├── post-checkout                        # thin entrypoint; shebang resolved by install.py
│   ├── _refresh.py                          # invokes graphify update; graphify writes the freshness marker
│   └── _snapshot.py                         # copies graphify-out/ from the parent worktree
├── install.py                               # dependency check, hook install, .gitignore entry
└── README.md                                # operator adoption docs

manifest.json                                # (repo root) gains one new atom entry — haex-hive as publisher
.haex-hive.json                              # (repo root) gains one new atoms[] entry — haex-hive as consumer
.gitignore                                   # gains a graphify-out/ line (also written by install.py for other adopters)

tests/
└── atoms/
    └── graphify_first_authoring/
        ├── test_refresh.py                  # refresh invocation + graphify-owned marker verification
        ├── test_snapshot.py                 # worktree-snapshot logic
        └── test_install.py                  # shebang resolution, hook-collision refusal, tracked-branch refusal, dependency check
```

**Structure Decision**: The atom lives under `.specify/atoms/graphify-first-authoring/`, matching the layout already established for haex-hive's own core constitution atom (`.specify/memory/`) and consistent with the design doc's file layout. Its logic (`_refresh.py`, `_snapshot.py`, `install.py`) is plain, importable Python so it can be unit-tested under the repo's existing `tests/` tree without needing to actually invoke git or graphify in most tests — only a thin end-to-end smoke test needs real subprocess calls.
