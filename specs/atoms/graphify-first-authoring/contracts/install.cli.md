# CLI Contract: `install.py`

**Spec**: [spec.md](../spec.md) §User Story 4, FR-011–FR-017
**Data model**: [data-model.md](../data-model.md) §InstallerState, §RootManifestEntry
**Design**: [design doc](../../../../docs/plans/2026-08-31-graphify-first-authoring-design.md) §"graphify as a dependency", §"Hooks: native, Python, cross-platform"

## Synopsis

```console
# Linux / WSL2
python3 .specify/atoms/graphify-first-authoring/install.py

# macOS (use python if that is the command provided by your installation)
python3 .specify/atoms/graphify-first-authoring/install.py

# Windows
python .specify/atoms/graphify-first-authoring/install.py
```

No flags in v0.1 — every decision point that could plausibly be a flag (skip confirmation, force-overwrite an existing hook) is deliberately absent; see "Non-goals" below.

## Description

Installs this atom's git hooks (`post-commit`, `post-checkout`) into the current repository's `.git/hooks/`, with a shebang resolved to whichever of `python3`/`python` is present on the invoking machine, and ensures `graphify-out/` is listed in `.gitignore`. Refuses cleanly, making no partial changes, if any precondition below is not met. Must be run once per machine per clone (git hooks are never committed).

## Preconditions (checked in this order)

1. **Current branch is tracked.** The repo's auto-detected default branch, or one named in `.haex-hive.json`'s `tracked_branches[]`. Otherwise: refuse, name the current branch and the expected tracked branch(es) (FR-013).
2. **`graphify` CLI is on PATH.** Otherwise: prompt `graphify CLI not found. Install now via 'pip install graphifyy'? [Y/n]`. Default `Y` runs `pip install graphifyy` and re-checks PATH; on `n` or if the pip install fails, refuse with actionable instructions, make no other changes (FR-011). The operator can then install `graphifyy` manually and re-run this installer.
3. **Neither target hook path is already occupied** by a hook from another tool. Otherwise: refuse, instruct the operator to integrate manually; do not overwrite (FR-014).

## Interactive step

If all preconditions pass, the installer inspects the working tree for a `graphify-out/` directory. If absent, it prompts before running `graphify install` as a one-time harness registration step (default `Y`; idempotent and safe to re-run even if already registered). If the operator declines, installation still succeeds after printing manual follow-up instructions. If a `graphify-out/` directory already exists, `graphify install` is skipped — the operator has already used graphify in this repo, so registration was either done manually or via a prior adoption (FR-012).

## Outputs

- **Success**: `.git/hooks/post-commit` and `.git/hooks/post-checkout` exist, executable, with a shebang naming a real interpreter on this machine. `.gitignore` contains a `graphify-out/` line (added if not already present). Exit 0.
- **Refuse (any precondition failed)**: diagnostic printed to stderr naming the specific failed precondition; no files written or modified. Non-zero exit.

## Non-goals (v0.1)

- No `--force` flag to overwrite an existing hook — that would undercut FR-014's collision-refusal safety boundary. (FR-011's pip-install prompt and FR-012's `graphify install` heuristic-based dispatch replace the earlier v0 confirmation prompts; no flag is needed to bypass them.)
- No `--platform` passthrough to `graphify install` — the operator can run `graphify install --platform P` manually if graphify's own auto-detection picks the wrong harness.
- No uninstall counterpart in this atom — removing the hooks is a manual `rm .git/hooks/post-commit .git/hooks/post-checkout`; `graphify uninstall` handles graphify's own side independently.
