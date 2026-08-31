# Design: `graphify-first-authoring` — an opt-in atom/molecule

**Created**: 2026-08-31
**Status**: Draft — not yet a spec
**Depends on**: Spec 007's atom/manifest v2 machinery (`contributes.constitution`,
`haex constitution assemble`, root/atom `manifest.json`), and the D6 pointer-block
mechanism from [2026-08-28-spec-007-unified-manifest-design.md](2026-08-28-spec-007-unified-manifest-design.md).

## Overview

An agent authoring new code routinely rebuilds a helper, class, or component
that already exists — under a different name, in a different file, one
abstraction level away, or as an incomplete/unexported version of what's
needed now. This design packages a constitution-level rule against that
failure mode: **before authoring anything new and named, consult the
project's [graphify](https://github.com/) knowledge graph for an existing
candidate, and prefer extending it over duplicating it.**

This is explicitly **not** added to haex-hive's own core constitution
(`.specify/memory/constitution.md`). Per Principle V, external constraints are
opt-in per project — haex-hive's core stays minimal. Instead this ships as its
own atom that any consumer, including haex-hive itself, can adopt by adding it
to `.haex-hive.json`'s `atoms[]`.

## Naming: atom vs. molecule

**Atom** stays exactly what Spec 007 already defined — the schema-level
packaging unit (a directory with a `manifest.json` declaring what it
`contributes`). Nothing about this design changes that term or its schema.

**Molecule** is a new, prose-only word for how we *talk about* a bundle: a
named grouping of one or more atoms meant to be adopted together as one
cohesive feature. It introduces no schema (`molecule.json` does not exist),
adds no root-manifest field, and changes nothing structurally. It exists so
operator-facing docs can say "adopt the graphify-first-authoring molecule"
instead of the colder "adopt the graphify-first-authoring atom."

`graphify-first-authoring` is a molecule containing exactly one atom today. If
the install tooling is later split out as its own contribution type, the
molecule grows to two atoms without renaming anything — the pairing is
forward-compatible by construction (atoms bond into molecules; a molecule of
one is not a special case).

## Layout

```
.specify/atoms/graphify-first-authoring/
  manifest.json          # contributes.constitution: "constitution.md"
  constitution.md        # the principle text (below)
  hooks/
    post-commit          # thin entrypoint → _refresh.py
    post-checkout        # thin entrypoint → _snapshot.py
    _refresh.py          # freshness check + incremental graphify reindex
    _snapshot.py         # copies graphify-out/ from the parent worktree
  install.py             # see "Adoption" below
  README.md              # operator docs: adoption, config, escape hatch
```

Root `manifest.json` gains one flat new atom entry, no `blueprint.` or
`molecule.` segment in the id:

```json
"atoms": {
  "com.github.haexmas.haex-hive.constitution": { "path": ".specify/memory", "version": "1.3.0" },
  "com.github.haexmas.haex-hive.graphify-first-authoring": {
    "path": ".specify/atoms/graphify-first-authoring",
    "version": "0.1.0"
  }
}
```

Because haex-hive now has two atoms contributing `constitution`, adopting this
molecule on haex-hive itself exercises Spec 007 US3's multi-source LLM-merge
path in `haex constitution assemble` — not the single-source straight-copy
path.

## The constitution text

```markdown
### Consult the Knowledge Graph Before Authoring (NON-NEGOTIABLE)

Before an agent authors any new named function, class, component, store,
module, or CLI command in a project that has adopted this molecule, it MUST
consult the project's graphify knowledge graph (`graphify-out/`) for existing
artifacts that are identical, near-identical, or an incomplete version of what
it is about to build. If the graph reveals a candidate, the agent MUST prefer
extending or exposing the existing artifact over authoring a parallel one —
even when the existing artifact is unexported, minimally different, or
currently incomplete for the new use case.

The graph is authoritative only on the project's tracked branches (the
detected default branch, plus any declared in `.haex-hive.json`'s
`tracked_branches[]`). Feature branches and worktrees inherit the graph from
their fork point via a `graphify-out/` snapshot taken at branch creation; the
snapshot represents the pre-branch state and is the correct baseline for
"does this already exist?" questions during the branch's life. The snapshot
is discarded with the branch — `graphify-out/` is git-ignored everywhere.

**Bootstrap when absent or incomplete, refresh when stale.** If
`graphify-out/` or its required `graph.json` is missing, the agent MUST run
`graphify update <path>` to index the repo before authoring. If the freshness marker is
missing/invalid or HEAD has advanced past the graph's recorded revision on a
tracked branch, the agent MUST run `graphify update <path>` before authoring.
On a feature branch/worktree, a complete snapshot is used as-is and is never
refreshed against feature `HEAD`; an incomplete snapshot is warned about and
handled as a failed consultation. To consult the graph, the agent runs `graphify query "<question>"`, `graphify path A B`, or
`graphify explain X` as appropriate — these are plain CLI invocations, not
tied to any one agent harness.

**Refuse-then-propose.** When the graph reveals an existing candidate that
would need extension rather than duplication, the agent MUST (a) name the
candidate (file + symbol), (b) state the delta between what exists and what
is needed, and (c) propose the extension. If the match is borderline or the
extension could cause scope creep, the agent MUST stop and ask the operator
before deciding. Silently authoring a parallel implementation is not
permitted.

**Escape hatch.** The operator MAY suspend this principle for a single
session with an explicit "skip graphify check" instruction. The suspension
does not persist and MUST be re-issued per session.

**Rationale**: LLM agents routinely rebuild helpers that already exist under
a different name, in a different file, or one abstraction level away, because
their working window cannot see the whole codebase. A persistent semantic
index closes that gap. Without a hard consult step, the same duplication
returns every session.
```

The invocation examples deliberately use the plain `graphify` CLI, not the
Claude-Code-specific `/graphify` slash command — this text is delivered to
every agent harness uniformly (see "Multi-LLM delivery" below), so it must
read correctly regardless of which harness executes it.

## Graph lifecycle

- **Branch scope**: auto-detect the repo's default branch (`git
  symbolic-ref refs/remotes/origin/HEAD`). `.haex-hive.json` MAY add an
  optional `tracked_branches[]` array to name additional long-lived branches
  (`develop`, `staging`, …). For haex-hive's own repo, this is just `main` —
  no override needed.
- **Every commit on a tracked branch** fires `post-commit`, which refreshes
  `graphify-out/` incrementally (only changed paths; full rebuild only when
  the graph is missing).
- **Worktree/feature-branch creation** fires `post-checkout`, which copies
  (not symlinks — Windows-portable, and semantically correct as a fork-point
  view) the parent worktree's `graphify-out/` in. Feature branches and their
  snapshots are discarded together; nothing survives the branch.
- **Merging a feature branch back into a tracked branch** needs no special
  graph-merge logic — the merge commit lands *on* the tracked branch and
  fires the same `post-commit` hook as any other commit.
- **Freshness marker**: `graphify` itself owns
  `graphify-out/.meta.json` and writes `indexed_at_sha` whenever it indexes or
  incrementally refreshes the graph. The agent compares this to current HEAD
  on tracked branches to decide bootstrap vs. refresh vs. proceed. Feature
  branch/worktree snapshots are frozen at their fork point and are not
  freshness-compared or refreshed against feature `HEAD`.
- **Bootstrap/refresh failure**: if either operation errors or times out, the
  agent warns, continues with graph consultation and authoring, and flags the
  incomplete refresh for a later manual check. The failure does not block
  authoring.

## Hooks: native, Python, cross-platform

Hooks are plain Python (no shell), matching the repo's Python-only stance and
Spec 007's own D1 decision (Python-only hook dispatcher). Contrary to an
earlier assumption in this design's drafting: Git for Windows' hook-execution
path reads a hook file's shebang line itself and dispatches to the named
interpreter directly — it does not rely on the Windows OS understanding
`#!`. So a Python-shebang hook is genuinely cross-platform (Linux, macOS,
WSL2, and native Windows via the standard Git-for-Windows distribution).

The remaining real gap is interpreter **naming**, not shebang support:
Windows' python.org installer provides only `python.exe` (no `python3.exe`),
while many modern Linux distros provide only `python3` (no bare `python`).
Since `.git/hooks/` is never committed — it's always a per-machine,
locally-installed artifact — `install.py` resolves this once, per machine, at
install time:

```python
interpreter = shutil.which("python3") or shutil.which("python")
if interpreter is None:
    raise SystemExit("graphify-first-authoring: no python or python3 found on PATH")
# write the hook file with a literal, resolved shebang, not a guess
```

**Hook collision**: if `.git/hooks/post-commit` (or `post-checkout`) already
exists from another tool (`pre-commit` framework, husky-style setups, etc.),
`install.py` refuses and instructs the operator to wire this molecule's hook
logic into their existing hook manager instead of overwriting it. This is a
working default for v0.1, to be specified more precisely later if it becomes
a real friction point.

## Agent-side freshness backstop

Hooks are the eager, native convenience — but the actual behavioral
guarantee lives in the constitution text itself ("bootstrap when absent,
refresh when stale"), independent of whether hooks are installed, bypassed
(`--no-verify`), or the repo was freshly cloned before `install.py` ran. Both
mechanisms call the same underlying `_refresh.py`/`_snapshot.py` logic; hooks
just trigger it automatically, the agent triggers it defensively.

## graphify as a dependency

graphify is a separate tool (`pip install graphifyy`, CLI binary `graphify`
on PATH) with its own built-in multi-platform installer:
`graphify install [--platform P]` places its skill/config content into any of
~18 supported agent harnesses. haex-hive does not need to reimplement that.

What haex-hive's atom manifest schema does **not** have today is any way to
declare "this atom requires tool X on PATH" or "this atom requires atom Y
also installed" — confirmed by grep across the Spec 007 contracts; no
`requires`/`dependencies` field exists anywhere in `atom-manifest.v2.schema.json`.
Rather than growing the schema for one atom's need, this is solved ad-hoc in
`install.py`:

```python
if shutil.which("graphify") is None:
    answer = input(
        "graphify CLI not found. Install now via 'pip install graphifyy'? [Y/n] "
    )
    if answer.strip().lower() == "n":
        raise SystemExit(
            "graphify CLI is required — install it with 'pip install graphifyy' "
            "and re-run this installer."
        )
    subprocess.run([sys.executable, "-m", "pip", "install", "graphifyy"], check=True)

registration = subprocess.run(
    ["git", "-C", str(repo_root), "config", "--local", "--get",
     "graphify-first-authoring.registration"],
    capture_output=True, text=True, check=False,
)
if registration.returncode != 0 or registration.stdout.strip() != "installed":
    answer = input(
        "graphify-first-authoring needs graphify registered for your agent "
        "harness. Run `graphify install` now? [Y/n] "
    )
    if answer.strip().lower() != "n":
        subprocess.run(["graphify", "install"], check=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "config", "--local",
             "graphify-first-authoring.registration", "installed"],
            check=True,
        )
    else:
        print("Skipped 'graphify install'; run it manually when ready.")
# A graphify-out/ directory alone does not prove harness registration.
```

Two deliberate boundaries: `install.py` never silently `pip install`s
graphify itself (that mutates the operator's Python environment — venvs,
pins — without asking), but it does offer to run `graphify install` when the
CLI is already present, since that's graphify's own designed, reversible
(`graphify uninstall` exists), idempotent entrypoint. After a successful run,
the installer records `graphify-first-authoring.registration=installed` in the
clone's unversioned local git config. The marker, rather than
`graphify-out/`, is the registration state; graph bootstrap, refresh, and
worktree snapshots can create the cache independently.

This gap — no formal dependency declaration between atoms, or from an atom to
an external tool — is named here the same way Spec 007's design doc already
named multi-agent adapters and blueprint hydration as real-but-deferred: a
natural candidate for a future spec's manifest schema (`requires: { tools:
[...], atoms: [...] }`), once more than one atom needs it. Not solved now.

## Multi-LLM delivery (no new work needed)

This was the open question that shaped most of this design: does adopting
this molecule require installing per-LLM-harness skill content ourselves?
No — Spec 007's own D6 decision already solves rule-content delivery across
harnesses. Every agent config file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, …)
gets a minimal pointer-block pointing at one canonical
`.haex-hive/generated/rules.md`. Our contributed `constitution.md` text flows
into that same canonical file via `haex constitution assemble`, so it reaches
every harness uniformly, for free. (The pre-existing caveat that harnesses
which don't parse markdown at all, e.g. Codex's TOML config, need a
native-format adapter is unrelated to this molecule and already tracked as
Spec 010 territory.)

## Adoption today

Manual, no new CLI surface:

```console
# Linux / WSL2
python3 .specify/atoms/graphify-first-authoring/install.py

# macOS (use python if that is the command provided by your installation)
python3 .specify/atoms/graphify-first-authoring/install.py

# Windows
python .specify/atoms/graphify-first-authoring/install.py
```

Must be run on a tracked branch — `install.py` refuses otherwise, naming the
current branch and the tracked branch(es) it expected.

For a *different* repo referencing this atom cross-repo (via
`repository + SHA + path`, not locally present) rather than self-hosting it:
`haex constitution assemble` today only materializes the `contributes.constitution`
file, not the rest of an atom's directory (hooks, `install.py`, `README.md`).
Full blueprint hydration for cross-repo consumers is Spec 007's already-named
deferral to Spec 010's `haex install`. Not solved now — out of scope for this
design.

## Deferred / open questions

- Formal `requires` field on atom manifests (tools + atoms) — candidate for
  a future spec.
- Hook-collision policy beyond "refuse and instruct" — revisit if it becomes
  a real friction point.
- `graphify-out/.meta.json` freshness marker — `graphify` owns the marker and
  must write `indexed_at_sha` at index and incremental-refresh time. T009
  invokes that real refresh path; the atom does not synthesize the marker.
- `haex blueprint install <atom-id>` or equivalent CLI surface for
  cross-repo hydration — deferred to Spec 010, same as the base constitution
  atom's own cross-repo consumption story.
