# Behavior Contract: installed git hooks

**Spec**: [spec.md](../spec.md) §User Story 2, §User Story 3, FR-006, FR-008
**Data model**: [data-model.md](../data-model.md) §GraphifyOutDirectory, §FreshnessMarker
**Design**: [design doc](../../../../docs/plans/2026-08-31-graphify-first-authoring-design.md) §"Graph lifecycle", §"Agent-side freshness backstop"

Both hooks are thin entrypoints installed by `install.py` (see [install.cli.md](install.cli.md)); their behavior is implemented in importable modules (`_refresh.py`, `_snapshot.py`) so it can be unit-tested without invoking git.

## `post-commit`

**Invocation**: no arguments (git's standard `post-commit` contract).

**Behavior**:
1. Determine the current branch. If it is not in the tracked-branch set (auto-detected default + `.haex-hive.json`'s `tracked_branches[]`), exit 0 immediately — no-op.
2. Otherwise, invoke `graphify <repo-root> --update` to refresh `graphify-out/` incrementally.
3. **On success**: exit 0. `graphify-out/.meta.json`'s `indexed_at_sha` now matches `HEAD`.
4. **On failure** (graphify crashes, times out, corrupted graph): print a warning to stderr naming the failure. **Exit 0 regardless** — the commit that already happened MUST NOT be affected by this hook's outcome (FR-006, resolved in `/speckit.clarify`). The freshness marker is left stale; the agent-side backstop catches this on the next authoring attempt.

**Never**: this hook never causes a `git commit` to fail, roll back, or print an error that a caller would interpret as commit failure.

## `post-checkout`

**Invocation**: `<prev-head-sha> <new-head-sha> <branch-checkout-flag>` (git's standard `post-checkout` contract; the third argument is `1` for a branch checkout, `0` for a file checkout).

**Behavior**:
1. If the third argument is not `1`, exit 0 immediately — this hook only cares about branch/worktree checkouts.
2. If a complete `graphify-out/` containing `graph.json` already exists in the current working directory, exit 0 immediately — never overwrite. An incomplete destination directory is treated as absent and may be replaced after a complete parent graph is found (FR-008 acceptance scenario 2).
3. Otherwise, locate the parent worktree (the first entry of `git worktree list --porcelain`). If it has no complete `graphify-out/` with `graph.json` (fresh repo, failed/incomplete index), exit 0 — nothing to copy; the agent's own bootstrap-when-absent/incomplete behavior applies on first use (User Story 3, scenario 3).
4. Otherwise, copy the parent's `graphify-out/` into the current working directory's `graphify-out/`, recursively, preserving the freshness marker as-is (it correctly reflects the fork-point commit, not the new branch's HEAD).

**On failure** (copy fails partway, e.g. disk full): print a warning to stderr; exit 0 regardless — a checkout MUST NOT fail because this hook could not copy a cache directory. A partially-copied or absent/incomplete `graphify-out/` is caught by the agent-side bootstrap-when-absent/incomplete behavior on first use.

## Shared failure principle

Neither hook is permitted to make a git operation (`commit`, `checkout`, `worktree add`) fail on its own account. This mirrors the constitution text's own bootstrap/refresh backstop (FR-010): the hooks are the eager, native convenience; the agent-side check is what actually guarantees the rule holds, independent of whether the hooks ran, ran successfully, or were bypassed entirely (`--no-verify`).
