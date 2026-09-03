# Quickstart: adopting graphify-first-authoring

This walks through adopting the atom on a repo that already uses haex-hive's Spec 007 manifest v2 (`.haex-hive.json`, `haex install`) — exactly the case haex-hive itself is in.

## 1. Prerequisite: the `graphify` CLI

```console
$ pip install graphifyy
$ graphify --help
```

If this is already installed, skip to step 2. Otherwise, the installer in the
next step offers this package installation with a default-Yes prompt. Declining
the prompt leaves the repository unchanged and prints the manual follow-up.

## 2. Run the installer

From the repo root, on a tracked branch (the default branch, or one declared in `tracked_branches[]`):

```console
# Linux / WSL2
$ python3 .specify/molecules/graphify-first-authoring/install.py

# macOS (use python if that is the command provided by your installation)
$ python3 .specify/molecules/graphify-first-authoring/install.py

# Windows
$ python .specify/molecules/graphify-first-authoring/install.py
graphify-first-authoring needs graphify registered for your agent harness. Run `graphify install` now? [Y/n]
```

When the local registration marker is absent, accept the default (or answer
`n` and run `graphify install` yourself later). A successful registration is
recorded as `graphify-first-authoring.registration=installed` in local git
config. The presence of `graphify-out/` does not suppress the prompt because
the directory may have been created by bootstrap, refresh, or a snapshot. On success:

- `.git/hooks/post-commit` and `.git/hooks/post-checkout` are installed.
- `.gitignore` gains a `graphify-out/` line, if not already present.

## 3. Adopt the atom in `.haex-hive.json`

Add an entry to `atoms[]` (alongside any existing constitution atom):

```json
{
  "includes": ["com.github.haexmas.haex-hive.graphify-first-authoring"],
  "revision": "<pinned commit SHA>",
  "source": "https://github.com/haexmas/haex-hive"
}
```

## 4. Install

```console
$ haex install
```

If this is the only constitution-contributing atom, the result is a byte-for-byte copy. If haex-hive's own core constitution atom is also adopted (the usual case for haex-hive's own repo), this triggers the LLM-merge path via `haex install --llm=…` — review the merged output before committing.

## 5. Verify

```console
$ haex constitution show
```

The printed "Assembled from" preface should name the adopted constitution
source(s): one source when this atom is the only constitution-contributing
atom, or both source atoms in haex-hive's self-adoption case. From this point,
any agent bound by this constitution consults `graphify-out/` before authoring
new named code.

## 6. Confirm the hooks are live

```console
$ git commit --allow-empty -m "chore: test graphify-out refresh"
$ ls graphify-out/.meta.json   # should reflect the new HEAD
```

When creating a feature worktree, pass the source worktree explicitly so the
hook can snapshot the correct fork-point graph (Git does not provide this path
to `post-checkout`):

```console
# Linux / macOS / WSL2
$ GRAPHIFY_PARENT_WORKTREE="$PWD" git worktree add -b feature/x ../hive-feature

# PowerShell
PS> $env:GRAPHIFY_PARENT_WORKTREE = (Get-Location).Path
PS> git worktree add -b feature/x ..\hive-feature
```

Without this signal, the hook leaves the destination untouched rather than
guessing which linked worktree was the parent; the agent-side rule handles the
missing snapshot according to the branch type.

## Suspending the rule for one session

Tell the agent explicitly: "skip graphify check" — this holds only for the current session and must be re-issued next time.
