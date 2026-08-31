# Quickstart: adopting graphify-first-authoring

This walks through adopting the atom on a repo that already uses haex-hive's Spec 007 manifest v2 (`.haex-hive.json`, `haex constitution assemble`) — exactly the case haex-hive itself is in.

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
$ python3 .specify/atoms/graphify-first-authoring/install.py

# macOS (use python if that is the command provided by your installation)
$ python3 .specify/atoms/graphify-first-authoring/install.py

# Windows
$ python .specify/atoms/graphify-first-authoring/install.py
graphify-first-authoring needs graphify registered for your agent harness. Run `graphify install` now? [Y/n]
```

When `graphify-out/` is absent, accept the default (or answer `n` and run
`graphify install` yourself later). If `graphify-out/` already exists, this
registration prompt is skipped. On success:

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

## 4. Assemble the constitution

```console
$ haex constitution assemble
```

If this is the only constitution-contributing atom, the result is a byte-for-byte copy. If haex-hive's own core constitution atom is also adopted (the usual case for haex-hive's own repo), this triggers the existing LLM-merge path — review the merged output before committing.

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

## Suspending the rule for one session

Tell the agent explicitly: "skip graphify check" — this holds only for the current session and must be re-issued next time.
