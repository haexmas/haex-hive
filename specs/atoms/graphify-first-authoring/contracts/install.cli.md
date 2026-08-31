# CLI Contract: `install.py`

**Spec**: [spec.md](../spec.md) §User Story 4, FR-011–FR-017
**Data model**: [data-model.md](../data-model.md) §InstallerState, §RootManifestEntry
**Design**: [design doc](../../../../docs/plans/2026-08-31-graphify-first-authoring-design.md) §"graphify as a dependency", §"Hooks: native, Python, cross-platform"

## Synopsis

```console
python .specify/atoms/graphify-first-authoring/install.py
```

No flags in v0.1 — every decision point that could plausibly be a flag (skip confirmation, force-overwrite an existing hook) is deliberately absent; see "Non-goals" below.

## Description

Installs this atom's git hooks (`post-commit`, `post-checkout`) into the current repository's `.git/hooks/`, with a shebang resolved to whichever of `python3`/`python` is present on the invoking machine, and ensures `graphify-out/` is listed in `.gitignore`. Refuses cleanly, making no partial changes, if any precondition below is not met. Must be run once per machine per clone (git hooks are never committed).

## Preconditions (checked in this order)

1. **Current branch is tracked.** The repo's auto-detected default branch, or one named in `.haex-hive.json`'s `tracked_branches[]`. Otherwise: refuse, name the current branch and the expected tracked branch(es) (FR-013).
2. **`graphify` CLI is on PATH.** Otherwise: refuse with `pip install graphifyy` instructions; make no other changes (FR-011).
3. **Neither target hook path is already occupied** by a hook from another tool. Otherwise: refuse, instruct the operator to integrate manually; do not overwrite (FR-014).

## Interactive step

If all preconditions pass, and `graphify` does not yet appear registered for the operator's current agent harness, prompt:

```
graphify-first-authoring needs graphify registered for your agent harness. Run `graphify install` now? [Y/n]
```

Default (bare Enter, or `y`/`Y`) runs `graphify install`. Any other input skips it — the operator is told to run it manually before relying on this atom's rule.

## Outputs

- **Success**: `.git/hooks/post-commit` and `.git/hooks/post-checkout` exist, executable, with a shebang naming a real interpreter on this machine. `.gitignore` contains a `graphify-out/` line (added if not already present). Exit 0.
- **Refuse (any precondition failed)**: diagnostic printed to stderr naming the specific failed precondition; no files written or modified. Non-zero exit.

## Non-goals (v0.1)

- No `--yes`/`--force` flag to skip the interactive confirmation or overwrite an existing hook — both would undercut the deliberate safety boundaries in FR-012/FR-014.
- No `--platform` passthrough to `graphify install` — the operator can run `graphify install --platform P` manually if graphify's own auto-detection picks the wrong harness.
- No uninstall counterpart in this atom — removing the hooks is a manual `rm .git/hooks/post-commit .git/hooks/post-checkout`; `graphify uninstall` handles graphify's own side independently.
