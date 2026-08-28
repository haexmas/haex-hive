# Blueprints & Unified Manifest Model — Design

**Status**: Draft (design brainstorming from 2026-08-28 session)
**Author**: haex-hive constitution v1.2.0 process
**Supersedes**: [Spec 006 draft — Multi-Spec External-Ref](2026-08-28-spec-006-multi-spec-external-refs-design.md) (its use case falls out of this model as a special case)
**Related**: [haex-hive design](2026-08-26-haex-hive-design.md);
[Spec 004 — Cross-Repo References](../../specs/004-cross-repo-refs/spec.md);
[Spec 005 — `haex-init` CLI](../../specs/005-haex-init/spec.md);
[ADR 0005 — Unified `harness_sources`](../adr/0005-unify-harness-sources-and-drop-system-yaml.md);
[Constitution §Principle IV, V, VI](../../.specify/memory/constitution.md)

## Problem

haex-hive today ships only the **constitution** — the eight non-negotiable
invariants. It has no concrete blueprint layer: no shipped conventions
for graphify usage, no worktree-per-feature workflow, no file-size caps,
no test-layout rules. Every consuming repo re-invents (or copy-paste-drifts)
these each time. And third parties cannot publish their own conventions in
a way other repos can safely consume.

The gap: haex-hive needs a mechanism for **opt-in, SHA-pinned, extensible
convention packs** — authored by anyone, hosted in any git repo, installed
into any consuming repo the same way — that carries all four kinds of
artifact a real convention needs (agent-facing rules, invokable skills,
mechanical hooks, declarative config).

Complicating requirements from the brainstorming session:

- haex-hive itself ships **no** curated blueprints. Even the maintainer's
  own conventions are published as separate git repos and installed like
  any third party's. Cleaner separation, no ambiguity between "official"
  and "opt-in".
- Everything — constitution, spec, blueprint, profile — installs via the
  **same uniform mechanism**. One CLI verb, one manifest shape, one
  hydrate flow.
- pnpm-shaped ergonomics: `haex add <git-url>`, `haex install`,
  `haex update`. No central registry initially; a future registry adds
  named-lookup convenience without changing the underlying mechanism.
- Cross-OS clean: nothing may rely on symlinks (Windows). All in-repo
  artifacts are generated copies, deterministic from pinned SHAs.
- CLAUDE.md / AGENTS.md / GEMINI.md must stay minimal. Consumers accept
  one small pointer block per agent; everything else lives bundled
  under `.haex-hive/`. Hooks defined once, executed for every agent.

## Solution in one line

Introduce a **unified `manifest.json` shape** carried by every
consumable haex-hive resource. Extend `.haex-hive.json`'s
`harness_sources` array so every entry is `source + revision + track +
path + as + config`, where `path` addresses a directory containing
`manifest.json`. A pnpm-style CLI (`haex add`, `install`, `update`,
`remove`, `list`) fetches pinned entries into a gitignored cache and
hydrates well-known locations under `.haex-hive/`. haex-hive itself
ships only the constitution + the CLI + the manifest schema. Everything
else — blueprints, profiles, additional specs — lives in third-party
git repos (including the maintainer's own).

## Fits existing principles

- **IV (SHA-pinned)** — every entry carries `repository + full commit
  SHA + repo-relative path`. `track` is an optional convenience for
  `haex update`; `revision` remains the authoritative pin.
- **V (opt-in per project)** — every atom listed explicitly; nothing
  implicit; no discovery-based inheritance.
- **II (no absolute paths)** — cache lives at `.haex-hive/cache/`,
  always repo-relative; hydration produces the same on-disk layout on
  Linux, macOS, and Windows.
- **VI (review-gated)** — adding/upgrading a pinned entry is a diff to
  `.haex-hive.json`, committed by a human. `haex add` writes the diff
  but the human commits.

## Unified manifest.json

Every haex-hive-consumable resource is a directory containing a
`manifest.json`. The manifest declares its own `type`. The consuming
repo doesn't need per-type branching in its entry — the manifest is
authoritative; the consumer entry's `as` field is only an assertion.

### Types

- `constitution` — non-negotiable invariants (Principle IV/V-shaped
  content). One per project (typical case).
- `spec` — a feature specification bundle: `spec.md`, `plan.md`,
  `tasks.md`, `contracts/`, `checklists/`, etc.
- `blueprint` — a convention pack contributing rules, skills, hooks,
  and config to the consumer.
- `profile` — a curated bundle: `manifest.json` with an `includes: [...]`
  list of other pinned entries. Flattened at install time.

Future `type` values (e.g. `preset`, `template`) can be added without
breaking existing consumers, as long as `haex install` refuses unknown
types loudly.

### Example manifests

Constitution:

```jsonc
{
  "id": "haex-hive-constitution",
  "version": "1.2.0",
  "type": "constitution",
  "description": "Core invariants for haex-hive-managed repos.",
  "contributes": {
    "constitution": "constitution.md"
  }
}
```

Spec:

```jsonc
{
  "id": "spec-006",
  "version": "0.1.0",
  "type": "spec",
  "description": "Multi-spec external-ref (superseded by unified manifest).",
  "contributes": {
    "spec":  "spec.md",
    "plan":  "plan.md",
    "tasks": "tasks.md"
  }
}
```

Blueprint:

```jsonc
{
  "id": "graphify-integration",
  "version": "0.3.1",
  "type": "blueprint",
  "description": "Query graphify before writing new code; keep graph fresh.",
  "contributes": {
    "rules":  ["rules/before-writing-code.md", "rules/graphify-query-conventions.md"],
    "skills": ["skills/check-duplicates.md",   "skills/graphify-refresh.md"],
    "hooks":  [{"trigger": "feature.start",   "script": "hooks/on-feature-start.sh"}],
    "config": {"schema": "config.schema.json", "defaults": "config.defaults.json"}
  },
  "requires":  ["graphify >= 0.4"],
  "conflicts": []
}
```

Profile:

```jsonc
{
  "id": "haex-personal",
  "version": "1.0.0",
  "type": "profile",
  "description": "Curated blueprint set for personal projects.",
  "includes": [
    { "repository": "https://github.com/haexmas/haex-blueprints.git",
      "revision":   "<sha>",
      "path":       "atoms/graphify-integration" },
    { "repository": "https://github.com/haexmas/haex-blueprints.git",
      "revision":   "<sha>",
      "path":       "atoms/worktree-per-feature" }
  ]
}
```

## Consumer entry shape (`.haex-hive.json`)

Every entry in `harness_sources` follows one shape, regardless of type:

```jsonc
{
  "source":   "https://github.com/haexmas/haex-hive.git",  // git URL or "self"
  "revision": "b2f884158dc90fbd4ab956f00ee100a82b6ec3eb",  // immutable SHA (Principle IV)
  "track":    "main",                                       // optional; ref used at add time, drives `haex update`
  "path":     ".specify/memory/constitution",               // repo-relative path to a dir containing manifest.json
  "as":       "constitution",                               // assertion vs. manifest.type
  "config":   { }                                            // optional; typically only for type=blueprint
}
```

- `source: "self"` — the consuming repo is also the producer of this
  entry. Existing semantic.
- `track` — remembered so `haex update` knows what ref to re-resolve
  against. Without `track`, an entry is frozen.
- `as` — refuse to install if `manifest.type` differs. Prevents the
  "I thought this was a blueprint but got a spec" class of accident.
- `config` — consumer overrides, merged into atom defaults at install
  time. Validated against `config.schema.json`. Unknown keys fail loudly.

## CLI surface (pnpm-shaped)

```
haex add <git-url>[#<ref>] [--path <subpath>] [--as <expected-type>]
    - Fetches the given URL at <ref> (default: repo default branch).
    - Reads manifest.json at <subpath> (default: repo root).
    - Pins the resolved SHA into revision; stores <ref> as track.
    - Asserts manifest.type == <expected-type> if --as given.
    - Appends an entry to .haex-hive.json.
    - Runs `haex install` at the end (unless --no-install).

haex install
    - Reads .haex-hive.json (the lockfile-equivalent).
    - Hydrates every pinned entry (fetch to cache, dispatch on
      manifest.type, render into a staging tree, atomic swap).
    - Idempotent; deterministic; produces .haex-hive/install.lock.

haex install --check
    - Verifies live tree matches install.lock. Nonzero exit if drift.
    - Intended for CI.

haex update [<id> ...]
    - For each entry with a `track` field: re-fetch <track>, bump
      `revision` to the new HEAD SHA, re-run install.
    - Without <id>: updates all trackable entries.

haex remove <id>
    - Deletes the entry from .haex-hive.json; re-runs install so
      hydration drops the removed content.

haex list
    - Shows installed entries: id, type, version, SHA, track.
```

**Registry, later.** When one lands, `haex add graphify-integration`
becomes a shortcut that resolves a name to a URL. The pin still carries
the URL + SHA, so the registry can vanish and everything still resolves.

## Install / hydrate flow

### Trigger points

- `haex init` — first-time setup; writes `.haex-hive.json`, wires each
  installed agent's settings file once, writes `.gitignore` entries.
- `haex install` — after every edit to `.haex-hive.json`; also on
  manual invocation.
- `haex install --check` — CI: verify no drift between live tree and
  lockfile.

### Steps, in order

1. **Validate `.haex-hive.json`.** Schema check. Every entry must
   carry `source + revision + path`. Reject branch or `HEAD` refs in
   `revision` (Principle IV).
2. **Fetch to cache.** For each entry, ensure
   `.haex-hive/cache/<atom-id>@<sha>/` exists. If missing: `git fetch`
   + checkout the SHA, verify the checked-out SHA matches. Never
   network again for an already-cached SHA.
3. **Flatten profiles.** Any entry whose manifest carries
   `includes: [...]` gets expanded recursively into its member entries.
   Cycle detection; max-depth cap. Order preserved. Direct pins for
   the same `(source, path)` shadow profile-provided pins and log the
   shadow.
4. **Validate compatibility.** Walk the flattened set; check each
   atom's `requires` and `conflicts` fields. Fail loudly with a list;
   never partial-install.
5. **Merge config.** For each blueprint: `defaults` (from
   `config.defaults.json`) ⊕ consumer override (from the entry's
   `config` block). Validate the merged object against
   `config.schema.json`. Write to
   `.haex-hive/config/<atom-id>.json`.
6. **Render into a staging dir.** All writes go into
   `.haex-hive/.staging/` first — never into the live tree:
   - Template-substitute rule files with effective config →
     concatenate deterministically (atom-id alphabetical) into
     `.haex-hive/.staging/generated/rules.md`.
   - Copy skill files into
     `.haex-hive/.staging/generated/skills/` and into each active
     agent's `<agent-skills-dir>/haex-hive/`.
   - Copy hook scripts into
     `.haex-hive/.staging/hooks/<trigger>/NN-<atom>.sh` (NN =
     declared order or manifest index).
7. **Compute lockfile.** Hash the staging tree deterministically →
   produce `.haex-hive/.staging/install.lock` (records: atom ids,
   SHAs, effective-config hashes, output-file hashes).
8. **Atomic swap.** If validation passed, rename staging into place.
   If anything failed, discard staging — live tree untouched.
9. **Diff `.haex-hive.json`** (if `haex add` or `haex update` was the
   caller): the tool leaves the diff staged but the human commits.
   Principle VI applies.

### On-disk layout inside a consuming repo

```
.haex-hive/
  cache/                     # pinned checkouts (gitignored)
    <atom-id>@<sha>/
  config/                    # per-atom effective config (generated, gitignored)
    <atom-id>.json
  hooks/                     # dispatcher-managed hook scripts (generated, gitignored)
    <trigger>/NN-<atom>.sh
  generated/                 # (generated, gitignored)
    rules.md                 # single agent-facing rules bundle
    skills/                  # canonical skill sources; agents get copies
  install.lock               # generated, gitignored
.haex-hive.json              # the committed lockfile of pinned entries
```

Committed to git: `.haex-hive.json` (and the small pointer blocks
`haex init` writes into CLAUDE.md / AGENTS.md / GEMINI.md, and one
delegating hook entry per agent settings file). Everything else is
generated and gitignored.

## Bundling under `.haex-hive/` — three key decisions

### 1. Per-atom config files, not a shared file

Each blueprint has its own `.haex-hive/config/<atom-id>.json`. Hooks and
skills read only their own atom's file. No cross-atom contention, easy
to eyeball, easy to diff. Rationale: with 5–10 atoms active a shared
flat config file becomes hard to scan; namespaced files keep each atom
independent.

### 2. Agent instruction files stay minimal

`haex init` writes a single small "haex-hive is active" pointer block
once into CLAUDE.md / AGENTS.md / GEMINI.md. Blueprints **never touch
those files again**. Rule contributions get concatenated into a single
`.haex-hive/generated/rules.md`; the pointer block references that
bundle (via `@` import syntax for agents that support it, or a plain
"see this file" line otherwise). Consumers see one small block per
agent; upgrading an atom changes only the bundle.

### 3. One hook dispatcher, all agents route through it

Blueprints drop hook scripts into `.haex-hive/hooks/<trigger>/*.sh`. A
single dispatcher — `haex hook run <trigger>` — runs everything in
that dir in numeric order. `haex init` wires each installed agent's
own settings file once, so the entry is always the same delegation:

```jsonc
// Claude Code — .claude/settings.json (written once by haex init)
"hooks": { "PreToolUse": "haex hook run pre-tool-use" }
```

Analogous single delegation for Codex, Gemini CLI, etc. Blueprints never
touch `.claude/settings.json` again. Adding a hook = adding a file
under `.haex-hive/hooks/<trigger>/`. All agents that share a trigger
see it automatically. Agent-specific triggers still land in the
agent's own settings file at `haex init` time, but the delegation
target is always `haex hook run`.

### 4. Skills: copies, no symlinks

Symlinks are unreliable on Windows (require admin or Developer Mode;
partial support in Git for Windows) and would violate Principle II's
cross-OS-identical resolution. Instead:

- Canonical source at `.haex-hive/generated/skills/` (generated from
  the pinned cache).
- Each active agent's skills dir gets a namespaced subfolder populated
  by copy: `.claude/skills/haex-hive/`, and equivalents for other
  agents.
- All copies are gitignored. The only committed record of what's
  installed is `.haex-hive.json`.
- Idempotent: same SHAs → same on-disk layout on every OS.
- Drift: if a user hand-edits a copied file, the next `haex install`
  overwrites it and logs a warning.

For agents whose skill loaders don't recurse into subfolders, the
install step emits a flat index file (`.claude/skills/haex-hive/
index.md`) that the rule bundle references.

## Config-value portability — how a value actually lands where it matters

External tools (graphify, ESLint, vitest) don't know about the
haex-hive config schema. The **atom author** owns the wiring; the
consumer only declares intent (`max_query_depth: 3`). Three ways an
atom applies its config to the target tool:

1. **Hooks read at run time.** `on-feature-start.sh` does:
   ```sh
   MAX_DEPTH=$(jq -r '.max_query_depth' .haex-hive/config/graphify-integration.json)
   graphify query --depth "$MAX_DEPTH" ...
   ```
   The atom's script is responsible for translating haex-hive-shaped
   config to the external tool's CLI flags.

2. **Templated into agent rules at hydrate time.** `rules/before-
   writing-code.md` uses `{{max_query_depth}}` placeholders. The
   resolver substitutes them from the effective config when
   concatenating into `.haex-hive/generated/rules.md`. So the agent
   reads: *"Query graphify with `--depth=3` before writing new code."*

3. **Native tool config file rendered at install time.** If the tool
   only reads its own on-disk config (e.g. `~/.config/graphify/
   config.toml`), the atom ships `hooks/on-install.sh` that renders
   that file from `.haex-hive/config/<atom-id>.json`. Escape hatch
   only; preferred paths are (1) and (2).

**Line of responsibility.** Consumer declares intent; atom author is
responsible for making that intent land wherever the tool actually
looks. If an atom can't wire a config key to anything real, it
shouldn't declare it in `config.schema.json`.

## Blueprint repo authoring — layout conventions

Publishers create any git repo they own. The only hard rule is: **a
`manifest.json` at the path a consumer will `haex add --path`**.

### Single-atom repo

```
graphify-integration/                    # repo root
  manifest.json                          # type: "blueprint"
  README.md
  rules/before-writing-code.md
  skills/check-duplicates.md
  hooks/on-feature-start.sh
  config.schema.json
  config.defaults.json
```

Consumer: `haex add https://github.com/<author>/graphify-integration.git`
(URL points at repo root; no `--path` needed).

### Multi-atom repo (collections)

```
haex-blueprints-haexmas/                 # repo root
  README.md                              # what this collection is
  atoms/
    graphify-integration/manifest.json
    worktree-per-feature/manifest.json
    dedup-check-before-new-code/manifest.json
    file-size-cap/manifest.json
    tdd-conventions/manifest.json
  profiles/
    haex-personal/manifest.json          # type: "profile", includes: [...]
```

Consumer picks any single atom:

```
haex add https://github.com/haexmas/haex-blueprints-haexmas.git \
         --path atoms/graphify-integration
```

Or installs the profile in one shot:

```
haex add https://github.com/haexmas/haex-blueprints-haexmas.git \
         --path profiles/haex-personal
```

## What haex-hive itself contains

**Consumer-facing:** the constitution and the `haex` CLI. Nothing else.

- `.specify/memory/constitution/` — with its own `manifest.json`.
  Installable as `type: constitution`, same mechanism as any third-
  party blueprint.
- `haex` CLI — `init`, `add`, `install`, `install --check`, `update`,
  `remove`, `list`, `hook run`.
- Docs — manifest schema, per-type contribution contract, blueprint
  authoring guide.
- `tests/fixtures/` — example atom/profile repos used only by the test
  suite. Not published, not linked from onboarding as "start here".

The maintainer's own convention pack (`haex-blueprints-haexmas`, or
similar) lives in a **separate** git repo and is installed via the same
`haex add` mechanism any third party would use. No implicit
"official" set.

## Onboarding a new consuming repo, end to end

```
mkdir my-project && cd my-project
git init
haex init                                            # writes .haex-hive.json, wires agent settings, .gitignore
haex add https://github.com/haexmas/haex-hive.git \
         --path .specify/memory/constitution \
         --as constitution                           # pin the constitution
haex add https://github.com/<author>/<repo>.git \
         --path <subpath>                            # pin a blueprint or profile; repeat as needed
haex install                                         # (auto-run by haex add; here explicit for verification)
```

The haex-hive repo URL is one URL among many. It happens to host the
constitution the user pins; it does not host or endorse blueprints.

## Impact on existing work

### Spec-006 (multi-spec external-ref)

The "multi-spec external-ref" use case becomes a natural consequence
of the unified manifest model — an external repo with several
`manifest.json` directories (one per spec) is just N entries under
`harness_sources`, each pointing at a different `path`. The narrow
feature no longer needs its own spec.

**Disposition**: close the current spec-006 draft as *superseded by
the unified manifest model*. The design draft in
`docs/plans/2026-08-28-spec-006-multi-spec-external-refs-design.md`
stays as historical record.

### Spec-005 (`haex init`)

Its `--pin-constitution` flag becomes syntactic sugar for
`haex add <self>#<sha> --path .specify/memory/constitution --as
constitution`. A patch-scope change; no rewrite.

### Constitution — location & shape

Reshape from `.specify/memory/constitution.md` (a file) to
`.specify/memory/constitution/` (a directory) containing
`manifest.json` + `constitution.md`. One breaking migration, one ADR,
one SHA bump. External consumers pinning the *old* SHA still resolve
the old-shape content — nothing breaks for them until they
`haex update`. `role: constitution` in existing `.haex-hive.json`
entries maps to `as: constitution` in the new shape (either the CLI
accepts both spellings for one transition release, or the migration
guide says "rewrite the field").

**Constitution amendment**: **minor version bump (→ 1.3.0)**.
Principles I–VIII unchanged. Principle IV's `path` semantics expand
from "file or directory" to "always a directory containing
`manifest.json`". Documented in a new ADR alongside the amendment.

## Proposed spec sequence

- **Spec-007 — Unified manifest & `harness_sources` v2.**
  Normalize entry shape; introduce `manifest.json` schema with a
  required `type`; reshape the constitution; migration path for old
  pins; constitution amendment. Foundation for everything else.
- **Spec-008 — The `haex` CLI.**
  `add`, `install`, `install --check`, `update`, `remove`, `list`.
  Install/hydrate machinery. `.haex-hive/` layout. Staging + atomic
  swap. Ref-tracking via `track`. Uniform dispatch on `manifest.type`.
- **Spec-009 — Blueprint contract & hydration.**
  Rule concatenation into `.haex-hive/generated/rules.md`; skill copy
  into agent-side `haex-hive/` subfolders; `haex hook run <trigger>`
  dispatcher; per-agent settings wiring at `haex init` time.
  `requires` / `conflicts` resolution. Templating rules for
  `{{config.*}}` substitution.
- **Spec-010 — Profile type.**
  `includes: [...]` resolution; cycle detection; precedence rules
  (direct pin shadows profile-provided pin).
- **Later, if warranted — Spec-011: registry.**
  Named lookups. Deferred until at least one non-haex-hive publisher
  exists and manual URL management shows friction.

## Suggested order of work

1. Land the current haex-hive-design.md and constitution ADRs as-is
   (already done through v1.2.0). Nothing to change today.
2. Close/superseded-mark the spec-006 branch; do not merge it as a
   feature.
3. Open **Spec-007** first — the foundation; nothing else can proceed
   without it.
4. **Spec-008** and **Spec-009** can run in parallel after Spec-007
   lands. Spec-009 needs Spec-008's `haex install` skeleton but not
   its full command set.
5. **Spec-010** after Spec-009 lands; the smallest and cheapest to
   bolt on last.
