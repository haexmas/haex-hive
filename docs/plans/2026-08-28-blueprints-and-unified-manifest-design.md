# Blueprints & Unified Manifest Model — Design

**Status**: Draft (design brainstorming from 2026-08-28 session)
**Author**: haex-hive constitution v1.2.0 process
**Supersedes**: [Spec 006 draft — Multi-Spec External-Ref](2026-08-28-spec-006-multi-spec-external-refs-design.md)
(its use case falls out of this model as a special case)
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
- Everything — constitution, spec, blueprint, profile — uses the **same
  acquisition mechanism**: one CLI, one manifest envelope, pinned fetches
  and validation. Hydration remains explicitly type-specific so a resource
  cannot silently write another type's consumer-facing files.
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

### Per-type hydration contract

Acquisition is uniform; the following destinations and conflict rules are
not. Before hydration, `haex` creates both a managed-output inventory from the
previous `install.lock` and a planned-output map from every current flattened
entry. Each canonical destination has exactly one owner: a resource key plus
its contribution. Duplicate resource keys and multiple planned owners of any
destination fail before rendering, including two constitutions targeting
`.specify/memory/constitution.md`. A destination not owned by the prior
inventory is never overwritten; a prior managed destination may be replaced
only by its matching planned owner in the successful transaction below.

- `constitution`: `contributes.constitution` is one validated file path. It
  is copied to `.specify/memory/constitution.md`, the canonical agent-facing
  location. Spec-007 extends `spec-resolve resolve --role constitution` for a
  v2 directory entry: it first verifies that `<entry-path>/manifest.json` is
  a regular Git-tree file, then reads and validates `type: constitution` and
  `contributes.constitution`. Only regular-file modes `100644` and `100755`
  may then be emitted with `git show <sha>:<entry-path>/<contribution>`; a
  directory, symlink, or any other mode fails before extraction. A legacy file
  pin retains the existing direct `git show <sha>:<path>` behavior. In neither
  case does the resolver trust a generated copy; hydration is an offline,
  agent-readable projection, not a second authority.
- `spec`: all validated files in the manifest directory are copied to
  `.haex-hive/generated/specs/<resource-key>/`. That tree is read-only
  generated input for agents and tooling; it never overwrites a working
  `specs/<feature>/` directory. `spec-resolve` continues to resolve any
  `spec-ref.json` direct triple from its pinned source. Spec-007 defines the
  explicit materialisation command, if one is wanted, rather than making
  install mutate a feature directory implicitly.
- `blueprint`: only the rules, skills, hooks, config and declared native-tool
  outputs described in this document are rendered.
- `profile`: contributes no files itself; it expands to member resources
  before any compatibility check or hydration.

The manifest schema rejects type-inappropriate `contributes` fields. This
keeps the uniform entry envelope separate from per-type output semantics.

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
    "config": {"schema": "config.schema.json", "defaults": "config.defaults.json"},
    "nativeOutputs": [{
      "id": "graphify-config",
      "script": "hooks/on-install.sh",
      "staged": "native/graphify/config.toml",
      "target": "graphify.config"
    }]
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

### Identifier and path validation

Validation happens before `haex` constructs a cache, generated-output,
configuration, hook, or source-file path. Manifest `id` and hook `trigger`
are safe single components matching `^[a-z0-9][a-z0-9.-]{0,63}$`; they may
not contain a slash, backslash, whitespace, or `..`. Contribution paths and
entry `path` values are canonical POSIX repository-relative paths: they may
use `/` for nested files, but reject empty components, `.`, `..`, absolute
paths, backslashes, NUL, and drive-qualified paths. After checkout, `haex`
resolves each contribution with a symlink-aware realpath check and rejects it
unless it remains beneath the pinned resource root. Raw manifest ids, source
URLs, and paths are never interpolated into filesystem names.

## Consumer entry shape (`.haex-hive.json`)

`harness_sources` has two disjoint shapes. A concrete resource entry is:

```jsonc
{
  // git URL or "self"
  "source": "https://github.com/haexmas/haex-hive.git",
  // immutable SHA (Principle IV)
  "revision": "b2f884158dc90fbd4ab956f00ee100a82b6ec3eb",
  // optional ref used at add time; drives `haex update`
  "track": "main",
  // repo-relative directory containing manifest.json
  "path": ".specify/memory/constitution",
  // assertion vs. manifest.type
  "as": "constitution",
  // optional; typically only for type=blueprint
  "config": {}
}
```

A permission-only trust-scope entry is `{ "source": "<credential-free git
URL>", "paths": ["optional/repo/relative/prefix"] }`: it has neither
`revision`, `path`, `as`, nor `config`, and is never installed or prefetched.
It preserves the current allowlist use case. An empty `harness_sources` array
still grants no permissions at all. The schema rejects an entry that mixes the
two shapes. The Spec-007 migration renames `repository` to `source` on every
existing permission-only entry without adding a revision or path, preserving
its scope verbatim; it never turns an empty array into a permission grant.

Every explicit `paths` item is a non-empty canonical POSIX-relative prefix
validated by the same rules as an entry `path` before authorization; it rejects
absolute paths, backslashes, NUL, drive-qualified paths, empty components,
`.`, and `..` (so `../` is invalid). It authorizes a candidate only when it is
identical to the prefix or starts with `prefix + "/"`; `src/app` therefore
does not authorize `src/apple`. Omitting `paths` deliberately grants the
source's full repository scope.

- `source: "self"` — the consuming repo is also the producer of this entry.
  It is resolved locally from the pinned tree after validating both objects;
  a v2 resource reads its manifest then its declared contribution with
  `git show`, while a legacy pin reads its file directly. It has no cache
  entry and never goes through `haex add` or remote fetch. This retains the
  existing `spec-resolve` self-reference contract.
- `track` — remembered so `haex update` knows what ref to re-resolve
  against. Without `track`, an entry is frozen.
- `as` — refuse to install if `manifest.type` differs. Prevents the
  "I thought this was a blueprint but got a spec" class of accident.
- `config` — consumer overrides, merged into atom defaults at install
  time. Validated against `config.schema.json`. Unknown keys fail loudly.

All persisted `source` values are canonical, credential-free Git URLs (or the
literal `self`). `haex add`, migration, and every other source-entry writer
reject URLs with userinfo such as `user:token@host`; they do not attempt to
redact and continue. Authentication remains Git credential-helper or SSH-key
based, so no key material reaches `.haex-hive.json`.

## CLI surface (pnpm-shaped)

```text
haex add <git-url>[#<ref>] [--path <subpath>] [--as <expected-type>]
    - Canonicalises and validates the URL before cache lookup or any network
      access; rejects userinfo credentials.
    - Fetches the validated URL at <ref> (default: repo default branch).
    - Reads manifest.json at <subpath> (default: repo root).
    - Pins the resolved SHA into revision; stores <ref> as track.
    - Asserts manifest.type == <expected-type> if --as given.
    - Rejects an URL containing userinfo; canonicalises and appends only a
      credential-free URL to .haex-hive.json. Git credential helpers and SSH
      remain the authentication mechanisms.
    - Appends a concrete resource entry to .haex-hive.json.
    - Runs `haex install` at the end (unless --no-install).

haex install
    - Reads .haex-hive.json (the lockfile-equivalent).
    - Hydrates every pinned entry (fetch to cache, dispatch on
      manifest.type, render into a staging tree, atomic swap).
    - Idempotent; deterministic; produces .haex-hive/install.lock.

haex install --check
    - Renders the expected managed workspace outputs into a temporary sibling
      root from committed inputs and pinned sources, without changing either
      the workspace or agent settings.
    - Compares that result with any live managed output and lockfile. Missing
      gitignored outputs in a clean checkout are expected; differing or
      orphaned managed outputs are drift and return nonzero. This makes the
      command a clean-CI validation as well as a local drift check.

haex update [<resource-key> ...]
    - For each entry with a `track` field: re-fetch <track>, bump
      `revision` to the new HEAD SHA, re-run install.
    - Targets only top-level persisted resource keys. Without a key, updates
      all trackable top-level entries.

haex remove <resource-key>
    - Accepts only a top-level persisted resource key, deletes that entry from
      .haex-hive.json, and re-runs install so
      hydration drops the removed content.

haex list
    - Shows installed entries: display id, resource key, type, version, SHA,
      track, and owner. A profile member shows its owning top-level profile
      key and can be updated or removed only through that profile.
```

`resource-key` is the validated, stable qualified identity
`sha256(canonical-source + NUL + canonical-path)`. It avoids collisions
between identical manifest ids in different repositories and remains stable
when `haex update` changes a revision. Cache keys instead use
`sha256(canonical-source + NUL + revision)`, which is available before reading
`manifest.json`. The full source, revision, path, display id, resource key,
and output paths are recorded in `install.lock`; generated config and hook
paths use a safe display id plus resource-key suffix, never a bare id.

**Registry, later.** When one lands, `haex add graphify-integration`
becomes a shortcut that resolves a name to a URL. The pin still carries
the URL + SHA, so the registry can vanish and everything still resolves.

## Install / hydrate flow

### Trigger points

- `haex init` — first-time setup; writes `.haex-hive.json`, wires each
  installed agent's settings file once, writes `.gitignore` entries.
- `haex install` — after every edit to `.haex-hive.json`; also on
  manual invocation.
- `haex install --check` — CI: render committed inputs into a temporary
  sibling root and verify any live generated output against it. A clean
  checkout has no generated output and is therefore valid without a
  committed generated lockfile.

### Steps, in order

1. **Validate `.haex-hive.json`.** Schema check. A concrete entry must
   carry `source + revision + path`; a permission-only entry grants scope but
   is not an install target. Reject branch or `HEAD` refs in `revision`
   (Principle IV), embedded credentials, unsafe paths, and legacy/v2 field
   mixing. Canonicalise and validate every external source before deriving a
   cache key, opening a cache, or using the network.
2. **Fetch direct entries to cache.** For each external concrete entry, ensure
   `.haex-hive/cache/<source-revision-key>/` is a valid checkout. On every
   cache hit, verify the repository object and checked-out SHA against the
   pinned revision before use. Quarantine an interrupted, stale, or locally
   mutated cache entry, then fetch, check out, and verify a replacement; an
   invalid entry when offline fails rather than being used. `self` is resolved
   only from the local pinned tree and has no cache. No network is used for a
   valid cached SHA.
3. **Flatten profiles and fetch members.** Normalize every profile
   `includes[].repository` to the canonical `source` field before identity,
   cache, or network work. Reject embedded credentials and validate each
   member's pin and paths before cache lookup; only the validated canonical
   source is fetched or stored. Resolve each member from its pinned cache,
   fetching and SHA-verifying it first on a cache miss (or use the local
   pinned tree for `self`), then recurse if it is a profile.
   Cycle detection and a configured max depth apply to the full recursion;
   order is preserved. Direct pins for the same canonical `(source, path)`
   shadow profile-provided pins and log the shadow.
   Before the first compatibility check or hydration, validate every fetched
   manifest id, trigger, and contribution path with the rules above; profile
   source fields are subject to the same credential-free URL validation.
4. **Validate ownership and compatibility.** Build the planned-output map and
   reject duplicate resource keys, destination owners, type-inappropriate
   contributions, `requires`, or `conflicts`. Derive a stale-output set as
   prior managed inventory minus current planned destinations. Only an
   inventory-owned destination may enter this set; it is a journalled deletion
   rather than an overwrite. Fail loudly with a list; never partial-install.
5. **Merge config.** For each blueprint: `defaults` (from
   `config.defaults.json`) ⊕ consumer override (from the entry's
   `config` block). Validate the merged object against
   `config.schema.json`. Write to
   `.haex-hive/config/<safe-display-id>--<resource-key>.json`.
6. **Render into a staging dir.** All writes go into
   `.haex-hive.next-<uuid>/`, a sibling of `.haex-hive/`, first — never into
   the live tree. Cache remains in `.haex-hive/cache/` and is not part of a
   swap:
   - Template-substitute rule files with effective config →
     concatenate deterministically (resource-key alphabetical) into
     `.haex-hive.next-<uuid>/generated/rules.md`.
   - Copy skill files into
     `.haex-hive.next-<uuid>/generated/skills/`; prepare each active agent's
     namespaced skill directory in an adjacent staging directory as well.
   - Copy hook scripts into
     `.haex-hive.next-<uuid>/hooks/<trigger>/NN-<resource-key>.sh` (NN =
     declared order or manifest index).
   - Stage every target in `.haex-hive.next-<uuid>/outputs/<resource-key>/`
     rather than writing it live. The constitution contribution is staged at
     `outputs/<resource-key>/constitution` and maps to
     `.specify/memory/constitution.md`; spec projections, agent copies, and
     declared native outputs use the same target-map form. Record staged hash,
     owner, target, and any stale deletion in the transaction plan.
7. **Compute lockfile.** Hash the staging tree deterministically →
   produce `.haex-hive.next-<uuid>/install.lock` (records: resource keys,
   display ids, canonical source/path, SHAs, effective-config hashes, and
   staged-output target maps and hashes). The lockfile omits completed stale
   outputs, while the journal retains their recovery backup until commit.
8. **Prepare and commit one transaction.** Before any new work, `haex` reads
   a durable, fsynced journal under `.haex-hive/transactions/`. If a prior
   commit was interrupted, recovery inspects its recorded targets and backups:
   a fully swapped set is completed by finalising it; any partial set is
   restored from backups. Ambiguous state fails closed for operator recovery.
   `on-install` is not allowed to mutate a live target directly. It produces
   declared native-tool files in a staging root; `haex` records a backup for
   every managed workspace, agent skill, and external configuration target,
   and records and fsyncs every swap or stale deletion in the journal before
   and after it. It removes backups and the journal only after every operation
   succeeds. On a normal returned failure, it restores all backups and removes
   every new target and staging root. A hook may not make undeclared side
   effects; such a hook is rejected. Thus the cache survives while generated
   state, agent copies, native targets, and removed outputs recover to one
   complete transaction state.
9. **Diff `.haex-hive.json`** (if `haex add`, migration, or `haex update` was the
   caller): the tool leaves the diff staged but the human commits.
   Principle VI applies.

### On-disk layout inside a consuming repo

```text
.haex-hive/
  cache/                     # pinned checkouts (gitignored)
    <source-revision-key>/
    quarantine/              # invalid cache entries, never hydrated
  config/                    # per-atom effective config (generated, gitignored)
    <safe-display-id>--<resource-key>.json
  hooks/                     # dispatcher-managed hook scripts (generated, gitignored)
    <trigger>/NN-<resource-key>.sh
  generated/                 # (generated, gitignored)
    rules.md                 # single agent-facing rules bundle
    skills/                  # canonical skill sources; agents get copies
    specs/<resource-key>/    # generated, read-only spec bundles
  install.lock               # generated, gitignored
  transactions/              # durable recovery journals (gitignored)
.haex-hive.next-<uuid>/      # sibling transaction staging root (gitignored)
  outputs/<resource-key>/    # staged target files; never written live first
.haex-hive.json              # the committed lockfile of pinned entries
```

Committed to git: `.haex-hive.json` (and the small pointer blocks
`haex init` writes into CLAUDE.md / AGENTS.md / GEMINI.md, and one
delegating hook entry per agent settings file). Everything else is
generated and gitignored.

## Bundling under `.haex-hive/` — four key decisions

### 1. Per-atom config files, not a shared file

Each blueprint has its own
`.haex-hive/config/<safe-display-id>--<resource-key>.json`. Hooks and skills
receive that path from the dispatcher and read only their own resource's file.
No cross-atom contention, easy
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

**Hook runtime contract.** Hook scripts are POSIX `sh` plus `jq`; `haex hook
run` invokes an explicit shell rather than relying on a file association. On
Linux and macOS that is a POSIX `sh` on `PATH`; on Windows it is Git for
Windows' `sh.exe` (found on `PATH` or in its standard installation), with
`jq.exe` on `PATH`. `haex init`/`haex doctor` validates both executables before
enabling a hook and fails with installation instructions if either is absent;
the hook's shebang is not used for dispatch. Spec-009 must include a
`windows-latest` acceptance fixture which calls `haex hook run` from
PowerShell, asserts ordered `.sh` execution and JSON read via `jq`, and
verifies the actionable missing-runtime error.

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
   MAX_DEPTH=$(jq -r '.max_query_depth' "$HAEX_CONFIG_PATH")
   graphify query --depth "$MAX_DEPTH" ...
   ```

   The atom's script is responsible for translating haex-hive-shaped
   config to the external tool's CLI flags.

2. **Templated into agent rules at hydrate time.** `rules/before-
   writing-code.md` uses `{{config.max_query_depth}}` placeholders. The
   resolver accepts only the `{{config.<dotted-key>}}` grammar, substitutes
   from the effective config when
   concatenating into `.haex-hive/generated/rules.md`. So the agent
   reads: *"Query graphify with `--depth=3` before writing new code."* An
   unknown key, malformed placeholder, or placeholder left after rendering is
   a validation error; no generated rule can retain an unresolved token.

3. **Native tool config file rendered at install time.** If the tool
   only reads its own on-disk config, the atom ships `hooks/on-install.sh`
   which renders a declared, staged native config from `$HAEX_CONFIG_PATH`.
   `haex` applies that staged file through the transaction protocol; the
   target mapping is device-local and unversioned. Escape hatch only;
   preferred paths are (1) and (2).

### Native-tool output contract

The `contributes.nativeOutputs` manifest array is the complete declaration for
an install-time native output. Each object has a safe component `id`, a
validated contribution `script`, a canonical relative `staged` file path, and
a safe logical `target` binding. The binding is resolved only in a per-device,
unversioned `haex` target map; no committed manifest contains an absolute path
or a home-directory expansion. The local mapping must resolve beneath an
operator-approved local root. An existing target must be a regular file, not a
symlink or directory; an absent target is createable on first install if every
existing parent is a non-symlink directory under that root. Parent creation is
a journalled transaction operation, so rollback removes only directories it
created and that remain empty.

For each declaration, `haex` runs the script in an isolated staging directory
with the pinned resource and effective config mounted read-only. The runner
enforces a deny-by-default filesystem sandbox: only `$HAEX_STAGE_ROOT` is
writable; live workspace, agent, cache, external-target, and all other
user/system paths are denied. The CLI provides this boundary with its bundled
platform sandbox adapter; on a platform where it cannot enforce the adapter,
native-output installation fails rather than falling back to an unsandboxed
shell. It exposes `HAEX_STAGE_ROOT`, `HAEX_CONFIG_PATH`, and a read-only JSON
file listing only that resource's declared output ids, staged paths, and
logical targets. The script may write only `$HAEX_STAGE_ROOT/<staged>` for a
listed declaration.

Before commit, `haex` validates every staged path with an `lstat` walk: staged
outputs must be declared regular files beneath the stage root, and any symlink,
directory in place of a file, or undeclared file fails. It enumerates every
target, backup, parent-directory creation, and stale deletion from the target
map before applying them through the journalled transaction. Spec-009 includes
acceptance tests for denied writes outside the stage root, staged-symlink
rejection, an absent first-install target, and rollback of its created parents.

**Line of responsibility.** Consumer declares intent; atom author is
responsible for making that intent land wherever the tool actually
looks. If an atom can't wire a config key to anything real, it
shouldn't declare it in `config.schema.json`.

## Blueprint repo authoring — layout conventions

Publishers create any git repo they own. The only hard rule is: **a
`manifest.json` at the path a consumer will `haex add --path`**.

### Single-atom repo

```text
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

```text
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

```text
haex add https://github.com/haexmas/haex-blueprints-haexmas.git \
         --path atoms/graphify-integration
```

Or installs the profile in one shot:

```text
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

```text
mkdir my-project && cd my-project
git init
haex init                                  # initializes config and agent wiring
haex add https://github.com/haexmas/haex-hive.git \
         --path .specify/memory/constitution \
         --as constitution                 # pin the constitution
haex add https://github.com/<author>/<repo>.git \
         --path <subpath>                  # pin a blueprint or profile
haex install                               # normally auto-run by haex add
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

Its `--pin-constitution` flag writes a validated `source: "self"` concrete
entry directly; it does not call `haex add`. The v2 resolver follows the
manifest-to-contribution read described above; a legacy file pin retains direct
`git show <sha>:<path>`, including SHA and path validation. A patch-scope
change; no rewrite.

### Constitution — location & shape

Reshape from `.specify/memory/constitution.md` (a file) to
`.specify/memory/constitution/` (a directory) containing
`manifest.json` + `constitution.md`. The Spec-007 transition release accepts
both, but as distinct schema variants: the legacy
`role: constitution + repository + revision + path` file pin remains
readable only through the existing resolver, while new entries must use the
v2 `source + revision + path + as: constitution` directory shape. Mixed
variants fail schema validation.

Migration is explicit and reviewable: `haex migrate constitution
--revision <new-full-sha>` validates that the requested source at that SHA has
the directory manifest and `type: constitution`, then proposes the single
`.haex-hive.json` diff replacing `repository`/`role` with
`source`/`as`, and the old file path with the manifest directory path. The
human reviews and commits that pin change before installation. If the legacy
`.specify/memory/constitution.md` is not in `install.lock`, migration may
adopt it only in that immediate transaction: it must be a regular file whose
bytes exactly match `git show <old-sha>:<old-path>`. A mismatch, symlink, or
missing old pin fails and requires the operator to back up or remove the file;
no ordinary install adopts unmanaged content. The verified adoption is recorded
in the transaction journal and replaced by normal lock ownership only after a
successful commit. Existing consumers retain their old SHA until they perform
this migration; no command silently upgrades a pin. The release after the
documented transition window removes the legacy schema branch and
`spec-resolve` support, making legacy entries a validation error before
hydration.

**Constitution amendment**: **minor version bump (→ 1.3.0)**.
Principles I–VIII unchanged. Principle IV's `path` semantics expand
from "file or directory" to "always a directory containing
`manifest.json`". Documented in a new ADR alongside the amendment.

## Proposed spec sequence

- **Spec-007 — Unified manifest & `harness_sources` v2.**
  Normalize entry shape; introduce `manifest.json` schema with a
  required `type`; reshape the constitution; preserve permission-only
  scopes; support then explicitly retire legacy constitution pins; constitution
  amendment. Foundation for everything else.
- **Spec-008 — The `haex` CLI.**
  `add`, `install`, `install --check`, `update`, `remove`, `list`.
  Install/hydrate machinery. `.haex-hive/` layout. Sibling staging +
  rollback transaction. Ref-tracking via `track`. Uniform acquisition and
  type-specific dispatch on `manifest.type`.
- **Spec-009 — Blueprint contract & hydration.**
  Rule concatenation into `.haex-hive/generated/rules.md`; skill copy
  into agent-side `haex-hive/` subfolders; `haex hook run <trigger>`
  dispatcher; per-agent settings wiring at `haex init` time.
  `requires` / `conflicts` resolution. Templating rules for
  `{{config.*}}` substitution. Windows hook-runtime acceptance test.
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
