# graphify-first-authoring atom

Opt-in atom that changes agent authoring behavior: **consult the graphify knowledge graph before authoring any new named code, and prefer extending an existing artifact over duplicating it.**

- **Atom id**: `com.github.haexmas.haex-hive.graphify-first-authoring`
- **Contributes**: `constitution.md` (merged into the adopting repo's `.haex-hive/constitution.md` via `haex constitution assemble`)
- **Also ships**: a `post-commit` hook (auto-refresh `graphify-out/` on tracked branches), a `post-checkout` hook (fork-point snapshot into new worktrees), and an installer for both

Nothing here is part of haex-hive's core constitution. Adopt it explicitly in your repo's `.haex-hive.json` if you want it.

## What the rule does

Before authoring **any new named function, class, component, store, module, or CLI command**, an agent bound by the assembled constitution:

1. On tracked branches, ensures a usable `graphify-out/graph.json` is present and fresh — bootstrapping or refreshing (`graphify update <repo-root>`) if the directory or graph file is absent, or the marker is missing/invalid or stale. Feature-branch/worktree snapshots stay frozen at their fork point and are not refreshed against feature `HEAD`; an incomplete snapshot is reported and handled as a failed consultation.
2. Queries the graph for candidates via plain `graphify` CLI (`graphify query "..."`, `graphify path`, `graphify explain`), evaluating unexported/incomplete artifacts too.
3. When a candidate matches: names the candidate location, proposes extending it, cites lines saved, rewrites **one** call-site as proof of concept — and waits for operator approval before touching anything else.
4. When similarity is borderline or scope-creep risk exists: **asks the operator** rather than deciding autonomously.
5. When the graph consult itself fails: warns, proceeds with authoring, and flags the skipped consult for a manual check later.

Full text lives in [`constitution.md`](constitution.md).

## Adoption (quick path)

For a repo that already runs haex-hive Spec 007 manifest v2 (`.haex-hive.json`, `haex constitution assemble`), see the [quickstart](../../../specs/atoms/graphify-first-authoring/quickstart.md) — the six steps are:

1. `pip install graphifyy` (or accept the installer's default-Y prompt when the CLI is absent)
2. Run the installer with the Python command available on your platform: `python3` on Linux/WSL2, or `python3`/`python` on macOS and `python` on Windows.
3. Add an `atoms[]` entry pinned to a full SHA of this repo
4. `haex constitution assemble`
5. `haex constitution show` — verifies both source atoms are named in the preface
6. `git commit --allow-empty -m "chore: test refresh"` — verifies the hook is live

## Files

| Path | Purpose |
|---|---|
| `manifest.json` | Atom manifest v2, `contributes.constitution = "constitution.md"` |
| `constitution.md` | The contributed principle text |
| `hooks/post-commit` | Refresh entrypoint (shebang set at install time) |
| `hooks/post-checkout` | Snapshot entrypoint (shebang set at install time) |
| `hooks/_refresh.py` | Refresh helper — `graphify update <root>`, warn-on-failure |
| `hooks/_snapshot.py` | Snapshot helper — copy parent's `graphify-out/` into new worktree |
| `hooks/_tracked_branches.py` | Tracked-branch set: detected default + `.haex-hive.json`'s `tracked_branches[]` |
| `install.py` | Installer — precondition-checked, refuses cleanly on any failure |

## What it does not do

- It does **not** rewrite existing duplicates already committed to the codebase (scope is new authoring).
- It does **not** replace human review — borderline calls escalate to the operator.
- It does **not** silently install anything into your Python environment (the installer prompts before `sys.executable -m pip install graphifyy`). It also prompts before `graphify install` when the local registration marker is absent, records successful registration in local git config, and skips that step only when the marker is present. `graphify-out/` presence alone is not a registration signal.
- If graph bootstrap or refresh fails, the agent warns and continues; the failed refresh is flagged for a later manual check.
- It does **not** cause git operations to fail — both hooks always exit 0 regardless of whether their work succeeded.

## Suspending for one session

Tell the agent: *"skip graphify check"* (or any equivalent). The suspension holds only for the current session and does not persist.

## Uninstall

`.git/hooks/*` is per-machine and never committed. To remove:

```bash
rm .git/hooks/post-commit .git/hooks/post-checkout
rm .git/hooks/_refresh.py .git/hooks/_snapshot.py .git/hooks/_tracked_branches.py
```

`graphify uninstall` handles the graphify side (harness registration) separately.
