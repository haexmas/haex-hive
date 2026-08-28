# Quickstart: `haex-init`

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Date**: 2026-08-27

Two end-to-end walkthroughs that together prove the two Priority-1
user stories, plus the follow-up pin. Each walkthrough is
copy-pasteable — the same commands the test suite exercises.

## Walkthrough 1 — Self-ref mode (SC-001a + SC-001b)

**Precondition**: a fresh Linux machine with `python3` ≥ 3.10 and
`git` ≥ 2.30 on `$PATH`. `claude` on `$PATH` and `~/.claude/`
present. `code` on `$PATH` and `~/.config/Code/` present. No prior
haex-hive state anywhere.

### Step 1 — Get `haex-init`

```
curl -sSLO https://<haex-hive-repo-url>/.specify/scripts/haex-init
chmod +x haex-init
```

(For Phase 1, the URL does not yet resolve to a public host —
operators clone the haex-hive repo and copy the file. Public-URL
resolution is Spec 006's `--fetch-latest` scope.)

### Step 2 — Create a project directory

```
mkdir my-project && cd my-project
```

### Step 3 — Run `haex-init`

```
../haex-init
```

Expected interaction:

```
Detected tools:
  [1] claude-code   (LLM)
  [2] vscode        (IDE)

Which should haex-hive wire into? (comma-separated, "all", "none"): all

Constitution mode:
  [1] self-ref
  [2] external-ref
Choose [1/2]: 1

Apply this change? [Y/n]:   ← ~/.haex-hive/haex-hive.md
Apply this change? [Y/n]:   ← ~/.haex-hive/VERSION
Apply this change? [Y/n]:   ← marker block into ~/.claude/CLAUDE.md
Apply this change? [Y/n]:   ← .haex-hive.json (harness_sources: [])
Apply this change? [Y/n]:   ← .specify/schemas/haex-hive.schema.json
Apply this change? [Y/n]:   ← .vscode/settings.json
Apply this change? [Y/n]:   ← append __pycache__/ to .gitignore
Initialize git repo? [Y/n]:
Commit scaffolding now? [Y/n]:

haex-init action report
=======================
Operator-level:
  [x] created ~/.haex-hive/haex-hive.md
  [x] created ~/.haex-hive/VERSION (v=1.0)
  [x] appended marker block v=1.0 to ~/.claude/CLAUDE.md

Project-level:
  [x] created .haex-hive.json (self-ref, harness_sources: [])
  [x] created .specify/schemas/haex-hive.schema.json
  [x] merged json.schemas entry into .vscode/settings.json
  [x] appended __pycache__/ to .gitignore

Git:
  [x] scaffolding commit ac5d1e (2 files)

Next steps:
  1. Run  /speckit-constitution  in your agent session.
  2. After committing the constitution, run:
       haex-init --pin-constitution

haex-init: 8 actions applied, 0 skipped
```

### Step 4 — Verify

```
spec-resolve status
```

Expected: `0 refs, 0 cached, last update-check: never`, exit 0.
(This is SC-001a: the scaffolding step lands with a green
`spec-resolve status`.)

### Step 5 — Author the constitution

In your agent session:

```
/speckit-constitution
```

Follow prompts, commit the resulting `.specify/memory/constitution.md`.

### Step 6 — Pin it

```
../haex-init --pin-constitution
```

Expected interaction:

```
haex-init --pin-constitution

Detected HEAD at ab12cd3.
Detected .specify/memory/constitution.md tracked at HEAD.

Proposed change to .haex-hive.json:

--- .haex-hive.json (current)
+++ .haex-hive.json (proposed)
@@
 {
   "haex_hive_version": "1.0",
   "identity": {...},
-  "harness_sources": []
+  "harness_sources": [
+    {
+      "role": "constitution",
+      "repository": "self",
+      "revision": "ab12cd3<full 40 hex chars>",
+      "path": ".specify/memory/constitution.md"
+    }
+  ]
 }

Apply this change? [Y/n]:
Commit pinned constitution reference now? [Y/n]:

haex-init action report
=======================
Project-level:
  [x] added role: constitution entry to harness_sources

Git:
  [x] pin commit de4f5a6

haex-init: 2 actions applied, 0 skipped
```

### Step 7 — Verify

```
spec-resolve status
```

Expected: `1 ref, 1 cached, last update-check: never`, exit 0.
(This is SC-001b: the pin step reaches a green `spec-resolve status`
with the constitution reference in place.)

## Walkthrough 2 — External-ref mode (SC-001c + US2)

**Precondition**: fresh empty project directory, same tool state as
Walkthrough 1. Have on hand a resolvable external repo URL, a SHA,
and a path within that repo that carries the constitution content
(the "family spec repo" scenario).

### Step 1 — Run `haex-init`

```
../haex-init
```

Expected interaction:

```
Detected tools: … (same as before)

Constitution mode:
  [1] self-ref
  [2] external-ref
Choose [1/2]: 2

External repository URL: https://example.gitlab.com/team/specs.git
Fetch latest HEAD SHA from remote? [y/N]: y
  ls-remote HEAD → 4c8e9a2f1b3d6e0a … (offering)
SHA (40 lowercase hex) [4c8e9a2f1b3d6e0a2f7c9b4d8e0a1f3c5d7b9e2a]: 4c8e9a2f1b3d6e0a2f7c9b4d8e0a1f3c5d7b9e2a
Path within repository [default: .specify/memory/constitution.md]:

Verifying reference…
  ✓ SHA is reachable at remote
  ✓ path .specify/memory/constitution.md exists at that SHA
  ✓ content is non-empty (2483 bytes)

Apply this change? [Y/n]:   ← .haex-hive.json (external-ref)
Apply this change? [Y/n]:   ← .specify/schemas/haex-hive.schema.json
Apply this change? [Y/n]:   ← .vscode/settings.json
Apply this change? [Y/n]:   ← .gitignore
Initialize git repo? [Y/n]:
Commit scaffolding + external constitution reference now? [Y/n]:

haex-init action report
=======================
Project-level:
  [x] created .haex-hive.json (external-ref, 1 harness_source)
  [x] created .specify/schemas/haex-hive.schema.json
  [x] merged json.schemas entry into .vscode/settings.json
  [x] appended __pycache__/ to .gitignore
Git:
  [x] scaffolding commit b8f01c2

haex-init: 5 actions applied, 0 skipped
```

### Step 2 — Verify

```
spec-resolve resolve --role constitution
```

Expected: exit 0, stdout contains the exact bytes stored at
`.specify/memory/constitution.md` at `4c8e9a2f…` in the remote repo.
(SC-001c: external-ref mode leaves `spec-resolve` fully functional.)

## Walkthrough 3 — Idempotent re-run (SC-003)

```
../haex-init
```

Expected output (no prompts):

```
Everything in order. No actions needed.
haex-init: 0 actions applied, 0 skipped
```

Exit 0.

## Walkthrough 4 — Version-aware upgrade (US3 acceptance 4)

**Precondition**: Walkthrough 1 completed. Then simulate a newer
`haex-init` by editing a scratch copy of the tool to bump
`INSTRUCTIONS_VERSION` from `1.0` to `1.1` and update
`CANONICAL_SESSION_INSTRUCTIONS` accordingly.

```
../haex-init-newer
```

Expected interaction:

```
Detected version drift:
  ~/.claude/CLAUDE.md has marker block v=1.0
  haex-init carries v=1.1

Proposed change to ~/.claude/CLAUDE.md:

--- ~/.claude/CLAUDE.md (current)
+++ ~/.claude/CLAUDE.md (proposed)
@@ -12,5 +12,5 @@
-<!-- haex-hive-block:begin v=1.0 -->
+<!-- haex-hive-block:begin v=1.1 -->
 ## haex-hive
 …
 <!-- haex-hive-block:end -->

Apply this change? [Y/n]:
```

## Walkthrough 5 — Dry-run diagnostic (SC-005)

```
../haex-init --dry-run
```

Expected on a fully up-to-date project: `Everything in order. No
actions needed.`, exit 0, filesystem SHA before ≡ after.

Expected on a project missing `.vscode/settings.json`:

```
Would apply:
  [?] create .vscode/settings.json

haex-init: 1 action pending (dry-run)
```

Exit 1, filesystem SHA before ≡ after.

## Walkthrough 6 — Non-TTY safety (Decision 7)

```
../haex-init < /dev/null
```

Expected: prints `haex-init: refusing to run non-interactively
without --yes` to stderr, exit 2.

```
../haex-init --yes < /dev/null
```

Expected: proceeds in fully auto-confirming mode, produces the same
outcome as the interactive run.

## What is not covered here

- Test-suite invocations (see `tests/haex-init/run-all.sh`).
- Manual smoke test against a real external remote
  (`.validation-runs/haex-init-real-remote.md` in the implementation
  phase).
- Multi-spec external-ref (Spec 006).
