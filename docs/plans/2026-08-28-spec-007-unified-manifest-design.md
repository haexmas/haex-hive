# Spec 007 — Unified Manifest & harness_sources v2 — Design

**Status**: Draft (design brainstorming from 2026-08-28 session, iteration after PR #8 review)
**Author**: haex-hive constitution v1.2.0 process
**Extends**: [Blueprints & Unified Manifest Model — PR #8](https://github.com/haexmas/haex-hive/pull/8)
(not yet merged into `main` at the time this design was drafted; local file
appears on the PR #8 branch only)
**Related**: [haex-hive design](2026-08-26-haex-hive-design.md);
[Spec 004 — Cross-Repo References](../../specs/004-cross-repo-refs/spec.md);
[Spec 005 — `haex-init` CLI](../../specs/005-haex-init/spec.md);
[Constitution §Principle IV, V, VI, VII](../../.specify/memory/constitution.md)

## Problem

PR #8 introduced the unified `manifest.json` model and the pnpm-shaped CLI
sketch. It leaves a number of load-bearing choices open:

- Are producer content directories and manifest files typed by an explicit
  `type` tag, or by the shape of what they declare?
- Should the consumer-side entry reference atoms by path or by ID?
- How does `.haex-hive/` divide committed vs generated content across
  multiple devices resolving the same lockfile?
- What is the deterministic contract between `.haex-hive.json`, the shared
  content store, and the hydrated `.haex-hive/generated/` tree?
- How is a multi-constitution consumer supposed to reconcile conflicting
  principles across sources — and how does the reconciled output travel to
  other devices without violating Principle VII (relay availability)?
- What is the CLI verb set, and how does `haex-init` fit into it?
- What is the migration path from `.haex-hive.json` v1 (Spec 004/005) to
  v2 (this spec)?

This design closes those questions with **seventeen numbered decisions**,
each carrying rationale and non-obvious consequences. It then proposes a
phased delivery across Specs 007/008/009/010 so no single spec grows past
useful review size.

## Non-Goals

Bounded up front — these are deliberately out of scope of Spec 007 and
its successors as currently planned:

- **Central atom registry / discovery service**. Publishers publish git
  repos with a root `manifest.json`; discovery is via `haex atoms list
  --source <url>` against a known publisher. No name-server.
- **Runtime skill sandboxing beyond process boundaries**. Publisher-hooks
  run as Python subprocesses under the consumer's user account. No
  seccomp/apparmor/gVisor wiring.
- **Live-catalog / on-the-fly-spec authoring**. All atoms are content
  already committed to a publisher repo at a pinned SHA.
- **Cross-device sync of consumer-side runtime state**. Device-local state
  in `$HAEX_HIVE_STATE/` is per-device. Consumer repo content
  (`.haex-hive/`) is the sole cross-device sync channel.
- **Registry-based atom-ID uniqueness enforcement**. Reverse-DNS by
  convention. No central lookup catches collisions.
- **Windows-native GUI installer**. Distribution is pip-installable for
  v1. Native single-file binaries are Post-MVP (Option C for v2).

## Relationship to PR #8

This design **extends and refines** PR #8's unified manifest model. Key
divergences and clarifications:

| Area | PR #8 said | This design says | Reason |
|---|---|---|---|
| Consumer entry shape | `source + rev + path + as + config` | `source + rev + includes[] + config` | Uniform shape whether user picks 1 or N atoms; no dual entry/profile syntax |
| Type discriminator | Explicit `type: "constitution" \| "spec" \| ...` in manifest | Derived from shape (`contributes.constitution`, `contributes.rules`, `includes`) | Removes redundancy; can't diverge from actual content |
| Atom-ID grammar | Free-form kebab-case slug | Reverse-DNS (`^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$`) | Collision-safe across publishers by construction |
| `.haex-hive/cache/` | Gitignored in-repo cache | Removed; shared content store at `$HAEX_HIVE_STATE/store/<content-sha>/` | Cross-project deduplication; keeps repo lean |
| `.haex-hive/` gitignore | Multiple subdirs gitignored | Everything committed | Byte-identity across devices via git, no reliance on deterministic install |
| Constitution merge | Concatenate multiple sources with labels | LLM-based semantic merge, single output at `.haex-hive/constitution.md` | Real semantic conflicts (not just structural collisions) need human+LLM to resolve |
| Constitution sync | (not spec'd) | Committed to repo; optional Nostr notify | Respects Principle VII; no relay dependency for local work |
| Hook dispatcher | Bash-shaped (`.sh` examples) | Python-only (Jinja2 for templating) | Cross-OS uniformity, no shell-vs-ps1 dispatch |
| Rules concat order | Alphabetical by atom-id | Priority-based (`manifest.priority` int, alphabetical tiebreak) | Semantic ordering matters (dedup-check before graphify-refresh) |
| Agent-config wiring | Per-agent adapter for full content | Minimal pointer-block per agent-md, points to `.haex-hive/generated/rules.md` | Minimally invasive; one pattern across CLAUDE.md/GEMINI.md/AGENTS.md |
| Consumer→atom resolution | Direct-path in entry | Atom-ID lookup via publisher root manifest | Rename-safe; publisher owns repo layout |
| CLI binary name | `haex` | `haex` (was `haex-init` before Spec 007) | Single binary, subcommand-based (pnpm/git/docker pattern) |

## The seventeen decisions

### D1. Hook dispatcher: Python-only

All hook scripts are Python 3.10+. No shell/PowerShell fallback. The
dispatcher (`haex hook run <trigger>`) invokes hooks as Python subprocesses
with a JSON context passed via stdin.

**Rationale**: cross-platform (Linux/macOS/Windows without WSL) demands a
uniform runtime. Python is already the CLI runtime; adding a second
scripting surface (bash + ps1 detection) doubles the failure modes and
kills native Windows use.

**Consequence**: Python 3.10+ becomes a hard prereq for using haex-hive.
Publishers write `.py` files; consumers execute them under their own
Python interpreter (which they also use for `haex` itself).

### D2. Constitution merge: LLM-based, committed sync

When more than one atom contributes to `contributes.constitution`, they
are combined by `haex constitution assemble`, which runs the operator's
attached LLM interactively over the source texts, produces a merged
`.haex-hive/constitution.md`, and records its content-hash in
`install.lock`.

Sync across devices is by **committing the merged file into the repo**.
Other devices `git pull` and verify the content-hash matches
`install.lock`. Optional Nostr-relay notify (`haex constitution publish`)
tells other devices "new merged version available — pull".

**Rationale**: real semantic conflicts across constitutions live in prose
and cannot be resolved by structured-diff. LLM-in-the-loop reflects how
the operator already reads and interprets constitutions. Committed sync
respects Principle VII — relay unavailability never blocks local work
(the file is in git). Nostr notify is convenience, not correctness.

**Consequence**: `haex install` on a device WITHOUT LLM access can only
succeed if `.haex-hive/constitution.md` is already committed and matches
the lockfile hash. Otherwise it refuses with a clear message and points
at `haex constitution assemble` on a device with LLM access.

### D3. Atom-ID grammar: reverse-DNS

Every atom-ID matches `^[a-z0-9][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+$`. At
least two segments joined by dots. Convention: derive from publisher URL,
e.g. `https://github.com/haexmas/blueprints` for atom `graphify-integration`
becomes `com.github.haexmas.blueprints.graphify-integration`.

**Rationale**: unqualified atom-IDs create a global namespace collision
problem as soon as two publishers exist. Reverse-DNS is collision-safe
by construction. Dots are filesystem-safe on all three target OSes; no
URL-encoding needed for cache directory keys.

**Uniqueness and collision rule**: an atom-ID is a global resolution key,
not a source-local nickname. After expanding every direct `atoms[]` entry
and every transitive profile, `haex install` MUST select exactly one
`(source, full revision, atom-id)` provider for each atom-ID. A publisher's
root-manifest key and the referenced atom manifest's `id` MUST match. The
resolver rejects a collision when the same ID is supplied by different
source/revision pairs, including two direct entries, and reports both entry
indices and pins. Identical repeated occurrences from the same
source/revision are de-duplicated only when their normalized consumer config
payloads are identical: omitted `values` is normalized to `{}` and omitted
`priority` remains absent. If either normalized `values` or `priority` differs,
resolution fails as a configuration conflict and names both entry indices.
This comparison, de-duplication, and failure rule is shared by `haex install`
and `haex verify`; no entry-order precedence is applied.

D14 is the sole exception: a direct entry for atom X deliberately shadows a
transitive profile occurrence of X. The direct provider is the one selected
for configuration ownership, lockfile entry, storage, and generated output;
the shadowed provider is not hydrated or recorded as X. Any other ambiguous
profile/direct combination is rejected rather than silently choosing a
source.

**Consequence**: existing example IDs from PR #8 (`haex-hive-constitution`,
`graphify-integration`, `haex-personal`) must be renamed before Spec 007
lands. Publisher registries encode the new IDs in their root `manifest.json`.

### D4. Templating engine: Jinja2

Publisher rule/hook content may contain Jinja2 template markers
(`{{ config.max_query_depth }}`, `{% if consumer.identity == "..." %}`).
The hydration step renders templates with atom-level effective config as
the render context. `autoescape=False` (rules are Markdown, not HTML).

**Rationale**: Python-first ecosystem, mature, pure-Python (no compile
step), well-known escape semantics. Consistent with D1.

**Consequence**: Jinja2 becomes a runtime dependency of `haex`
(pip-installable, no compile step). Template render order must be
deterministic (D9).

### D5. Rules order: priority-based

`manifest.priority: <int>` (default 100). Assembled `rules.md` is sorted
ascending by priority, alphabetical by atom-ID as tiebreak. Documented
convention (not schema-enforced):

```text
0    – 99   Foundational / constitutional
100  – 299  Cross-cutting conventions
300  – 599  Tool-specific / domain
600  – 899  Project-specific customizations
900  – 999  Late-binding overrides
```

Consumer override is the reserved, atom-ID-keyed field
`config.<atom-id>.priority: <int>`; it overrides that atom manifest's
default priority. It is deliberately outside the publisher-defined settings
object, so a publisher cannot accidentally redefine ordering semantics. The
v2 consumer-entry schema defines each `config.<atom-id>` value as an object
with only `priority` (optional integer) and `values` (optional object,
default `{}`). `values` alone is validated against the atom's
`config_schema`; `priority` is validated by the consumer schema. Atom
`config_schema` files MUST NOT define a top-level `priority` property.

**Rationale**: alphabetical-only ordering breaks semantic dependencies
(`dedup-check` should come before `graphify-refresh` regardless of alphabet).
Priority makes the ordering explicit. Documented ranges without schema
enforcement gives publishers a shared language without freezing edge cases.

### D6. Agent-md pointer block: marker-based idempotent upsert

`haex init` writes a small marker-bounded block to each agent-md file
(`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`), default position **top**. Format:

```markdown
<!-- HAEX-HIVE START -->
This project is haex-hive-managed. Load and follow: .haex-hive/generated/rules.md
<!-- HAEX-HIVE END -->
```

Subsequent runs find the markers (wherever the user may have moved them)
and replace content in-place. Never overwrites user content outside the
markers.

**Rationale**: minimal-invasive to the operator's own agent instructions;
respects the operator's post-init file layout choices; keeps per-agent
adapter surface tiny.

**Consequence**: agents that don't parse markdown (Codex `.codex/config.toml`,
etc.) need a per-agent adapter emitting a semantically-equivalent pointer
in the native format. Adapter framework is Spec 008/010 territory.

### D7. Config merge: deep-merge objects, replace arrays, strict-schema

Publisher's atom manifest declares `defaults` (arbitrary non-secret JSON)
and `config.schema.json` (JSON Schema Draft 2020-12). The schema describes the
**effective** settings object, not a partial override. At every object boundary
where consumer input is accepted, it MUST set `additionalProperties: false`
and declare its permitted `properties` and/or `patternProperties`.

For each selected atom, the meta-validator first validates and rewrites any
`x-haex-secret` field as defined below. Validation then proceeds in this order:
(1) validate `defaults` against the rewritten `config_schema`; (2) recursively
reject any key supplied in
`config.<atom-id>.values` that is not permitted by that object's properties or
pattern properties; (3) deep-merge the override onto defaults, replacing
arrays; then (4) validate the effective settings object against
the rewritten `config_schema`. Thus a required property supplied by defaults
does not make an empty or partial override invalid, while an unknown override
key still fails before the effective config is written.
`config.<atom-id>.priority` is processed separately as specified in D5 and is
not part of that effective settings object.

Config is committed, so it MUST NOT contain plaintext secrets. A
secret-dependent publisher field MUST be an otherwise unconstrained property
schema with exactly `"x-haex-secret": true`; it MUST NOT combine the marker
with `type`, `const`, `enum`, `format`, `pattern`, `$ref`, or a composition
keyword. The haex schema meta-validator rejects any other marked-field shape,
then replaces the marked field's schema before standard Draft 2020-12
validation with this exact schema:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["$haex_secret"],
  "properties": {
    "$haex_secret": {
      "type": "string",
      "pattern": "^keychain:[A-Za-z0-9._-]+$"
    }
  }
}
```

Consequently a marked field accepts only
`{ "$haex_secret": "keychain:<alias>" }`, never a string or another
literal. The alias is a device-local keychain reference, never secret
material. The meta-validator leaves every unmarked field unchanged for normal
publisher `config_schema` validation. Before writing
`.haex-hive/config/<atom-id>.json`, `haex install` runs this transformation
and the complete D7 validation sequence; the Spec 008 conformance suite MUST
cover a valid reference that is committed verbatim, a rejected plaintext
value, and unchanged validation of an unmarked field. Install, rendering,
locking, and verification never dereference a valid reference; runtime
consumers resolve it locally if their own contract requires it.

Config in the consumer entry is a map keyed by atom-ID (even for
length-1 `includes`, to keep the shape uniform):

```json
{
  "includes": ["com.github.haexmas.blueprints.skill-x"],
  "config": {
    "com.github.haexmas.blueprints.skill-x": {
      "priority": 250,
      "values": { "max_query_depth": 5 }
    }
  }
}
```

**Rationale**: standard config-merge pattern from JS/Python ecosystems
(Lodash `merge`, Jest, ESLint). Arrays-replace avoids ambiguity around
concat order and deduplication. Strict schema catches typos early with
good diagnostics.

### D8. Python distribution: pip-installable v1, native bundles v2

`pip install haex-hive` or `pipx install haex-hive` for v1. Python 3.10+
is a hard prerequisite documented in the README. `haex_hive_min_version`
field in `.haex-hive.json` triggers a clear error if a repo's config
requires a newer CLI than the local install.

Native single-file bundles (PyInstaller/Nuitka) are deferred to v2 if
corporate/no-Python-access adoption becomes important.

**Rationale**: 90% of the initial audience (devs already using AI-agent
tooling) have Python. Pip is the smallest possible distribution surface.
Native bundles require code-signing infrastructure and update servers —
significant work, not blocking for MVP.

### D9. Regeneration + drift prevention

`haex install` is the sole re-hydration trigger and must be **fully
deterministic**: two runs on identical inputs produce byte-identical
output. Rules of determinism:

- Resolve, render, concatenate, verify, and write lock records in one
  canonical order: ascending effective priority, then atom-ID in ascending
  bytewise UTF-8 order. Rendering never changes the ordering key.
- No timestamps, no random values, no environment variable leaks
- Contribution paths within an atom are ascending bytewise UTF-8 order;
  assembled text uses LF line endings. Source files are otherwise copied or
  rendered as bytes specified by D15.

`haex verify [--exit-code]` re-computes what `install` would produce and
compares hashes against `install.lock`. A `.git/hooks/pre-commit` shim
installed by `haex init` invokes `haex verify --exit-code` and refuses
the commit on mismatch. The verify command is also the CI-integration
point (`haex verify --exit-code` in a GitHub-Actions step).

**Rationale**: catches drift the moment the user tries to commit
inconsistent state. No CI dependency for the local safety net. Works
offline. Constitution v1.2.0 already forbids `--no-verify` bypass
without explicit permission.

### D10. Migration pattern: review-gated

Schema migrations (v1→v2 of `.haex-hive.json`, and future schema evolutions)
use a review-gated pattern:

1. A v1 user installs the v2 package, which provides the executable
   `haex`, then runs `haex migrate`; `haex-init migrate` is not an alias.
2. A regular run invalidates any existing `.haex-hive.json.migrated` sidecar
   before evaluation, then writes the proposal to a same-directory temporary
   file. It atomically replaces the sidecar only after every migration and
   validation step succeeds; it never overwrites the original.
3. It prints the unified diff to stdout for review.
4. On any failure it deletes the temporary file and ensures no sidecar
   remains, so a stale proposal cannot be manually applied. The original
   `.haex-hive.json` remains untouched.
5. `--dry-run` / `--check` performs no sidecar or temporary-file mutation,
   useful in CI.
6. User reviews, manually `mv .migrated → .haex-hive.json`, commits via PR.

**Rationale**: Principle VI (self-modifying instructions are always
review-gated) applies. Any automatic rewrite of a versioned config file
violates it. The sidecar+diff pattern preserves the review gate. This
pattern is a candidate for codification in the Constitution v1.3.0
amendment.

### D11. Consumer→atom resolution: atom-ID lookup via publisher root manifest

Publisher repo has a root `manifest.json` mapping atom-IDs to internal
paths:

```json
{
  "haex_hive_version": "2",
  "atoms": {
    "com.github.haexmas.blueprints.graphify-integration": {
      "path": "atoms/graphify-integration",
      "version": "1.2.0"
    }
  }
}
```

Consumer references atoms by ID; `haex install` clones publisher, reads
root manifest, resolves ID → path. Publisher can rename internal paths
between commits without breaking consumers (as long as the ID stays stable).

**Rationale**: rename-safety without publisher-managed migration tables.
Atom-ID becomes single source of truth. Consumer configs are shorter and
harder to break by accident.

**Consequence**: haex-hive itself needs a root `manifest.json` in this
repo mapping `com.github.haexmas.haex-hive.constitution` to
`.specify/memory/`. The atom's own `manifest.json` is located in that
directory; it in turn declares `constitution.md` as the contributed file.
Landing this manifest is part of Spec 007's implementation.

### D12. Consumer entry shape: uniform `includes[]`

Every consumer entry has the same JSON shape:

```json
{
  "source": "https://github.com/haexmas/blueprints.git",
  "revision": "abc123...",
  "track": "main",
  "includes": [
    "com.github.haexmas.blueprints.skill-x"
  ],
  "config": {
    "com.github.haexmas.blueprints.skill-x": {
      "values": { }
    }
  }
}
```

Single-atom pick: `includes` length 1. Multi-atom manual bundle: length N.
Publisher-defined profile: length 1 pointing at the profile atom, which
resolves transitively.

**Rationale**: one shape, one mental model, one schema. No dual "atom vs
profile" entry syntax. Adding atoms or upgrading pins is uniform across
all use cases.

**Consequence**: profile-atom conflict resolution (D14) becomes important
because explicit direct pins and profile-included pins can compete.

### D13. Publisher manifest: type-by-shape (no `type` field)

Atom manifests declare what they contribute; type is derived mechanically
from shape:

- Has `contributes.constitution` → participates in constitution merge
- Has `contributes.spec` → copied to `.haex-hive/generated/specs/`
- Has `contributes.rules` / `.hooks` / `.skills` → hydrated to
  `.haex-hive/generated/`
- Has `includes` → composition (resolve transitively)
- Combinations allowed: an atom may have `contributes` AND `includes`

The first profile-expansion resolver (Spec 008) uses depth-first traversal with
an active recursion stack keyed by `(source, full revision, atom-id)`. Seeing a
key already on that stack rejects the install with the complete cycle trace
before further expansion, hydration, or lockfile output. `haex verify` uses
the same resolver and rejects the same cycle. This is a prerequisite for
supporting profile atoms; Spec 010 extends its coverage with publisher
reference atoms but does not defer cycle safety.

**Rationale**: no redundant `type` field to diverge from actual content.
Manifest shape IS the type declaration. The dispatch table
(`contributes.X` → hydration path) is mechanical and testable.

### D14. Profile-vs-explicit-pin: explicit wins with warning

When a consumer has both a profile-atom entry that transitively includes
atom X AND an explicit pin for X (at a different SHA), the explicit pin
shadows the profile-provided version. `haex install` prints a warning:
`atom X from profile Y shadowed by explicit pin (SHA-Z replaces SHA-W).
Ensure compatibility.`

**Rationale**: user-first semantics; typical case is a bugfix that the
user needs before the profile author pins the newer version. Warning
makes divergence visible so it does not become silent drift. Consistent
with D7's consumer-override-wins model.

### D15. Storage layout: hybrid content-addressed store

Two-tier storage:

- **`$HAEX_HIVE_STATE/repos/<clone-hash>/`** — raw git clones (shared
  across all consumer repos on device)
- **`$HAEX_HIVE_STATE/store/<content-hex>/`** — content-addressed shared
  store (deduplicated resolved-atom trees across all consumer repos)
- **`.haex-hive/generated/`** in consumer — copies from store,
  agent-facing, committed to repo

`$HAEX_HIVE_STATE` resolves per-OS:

- Linux: `$XDG_STATE_HOME/haex-hive` (default `~/.local/state/haex-hive`)
- macOS: `~/Library/Application Support/haex-hive`
- Windows: `%LOCALAPPDATA%\haex-hive`

**Rationale**: dedup cross-project like pnpm's global store. Copy (not
symlink/hardlink) into consumer keeps Windows-portable. Consumer's
`.haex-hive/generated/` is the single Truth agents read from — no
"which folder wins" confusion.

**Content-integrity serialization**: every `sha256-<base64>` value is the
standard base64 encoding (with `=` padding) of SHA-256 over the following
canonical tree serialization, named `haex-hive-tree-v1`. It starts with the
ASCII bytes `haex-hive-tree-v1\0`. Entries follow in ascending bytewise UTF-8
order of their normalized relative POSIX path; paths use `/`, contain no `.`
or `..` segments, and are UTF-8 NFC. Directories are implicit and have no
record. Before sorting or hashing, install and verify reject a tree if two
distinct entries have the same normalized path (after NFC normalization);
they never emit or accept a canonical tree with duplicate names. Each record
is byte-framed as
`<kind>\0<mode>\0<path-length>\0<path-bytes><payload-length>\0<payload-bytes>\0`,
where `kind` is `F` for a regular file or `L` for a symlink, `mode` is exactly
`100644`, `100755`, or `120000`, and decimal lengths are ASCII. For `F`, the
payload is the file's bytes; for `L`, it is the symlink target's UTF-8 bytes.
Symlinks are represented, never followed. No platform encoding, separator,
or line-ending normalization occurs: raw trees hash checked-out raw bytes,
while generated trees hash their final rendered/copied bytes (including their
specified LF separators).

The path-safe `<content-hex>` store key is the 64-character lowercase hex
encoding of the digest bytes in its lockfile `sha256-<base64>` value:
base64-decode the suffix after `sha256-`, then hex-encode those 32 bytes with
no prefix, padding, truncation, or further hash. The lockfile retains the
unchanged `sha256-<base64>` integrity value; the hex key is only a local store
directory name.

`atoms[].content_integrity` hashes the raw, validated atom tree stored under
`$HAEX_HIVE_STATE/store/`; `constitution.content_integrity` hashes a one-file
tree containing the final committed `constitution.md`; and
`generated_content_integrity` hashes the final `.haex-hive/generated/` tree.
`haex install` and `haex verify` MUST use this exact serialization for every
write and comparison. `install.lock` itself is not included in any of these
trees.

### D16. `.haex-hive/` fully committed

All of `.haex-hive/` is version-controlled. No gitignored subdirs. Byte
identity across devices is guaranteed by git, not by hoping deterministic
install produces the same bytes everywhere:

```text
.haex-hive.json                          # root, source of truth
.haex-hive/
  install.lock                           # pinned state
  constitution.md                        # LLM-merged or straight-copy
  config/
    <atom-id>.json                       # per-atom effective config
  generated/
    rules.md                             # priority-ordered concat
    hooks/
      <trigger>/
        NNN-<atom-id>.py                 # dispatcher-managed
    skills/
      <atom-id>/SKILL.md
    specs/
      <atom-id>.md
```

Nothing under `.haex-hive/` is gitignored. Everything is a legitimate
output of a review-gated `haex install`.

**Rationale**: fresh `git clone` = working agent — no install step
needed for read-only agent use. Committing keeps agents' visible state
and the operator's audit trail identical. Diffs on `.haex-hive/generated/`
are meaningful signal (SHA bump, config change, priority update).

**Consequence**: `haex install` on device B/C after `git pull` from device A
should produce zero diff (deterministic install + identical inputs).
Users can add `.haex-hive/generated/` to their code-review "expect this
folder to change together with `.haex-hive.json`" mental model.

### D17. CLI verb surface

Twelve verbs in seven categories, all under a single `haex` binary
(renamed from `haex-init`):

**Bootstrap**: `haex init`

**Install-workflow**: `haex add <atom-id> --source <url>`, `haex install`,
`haex update [<atom-id>] [--to <sha>]`, `haex remove <atom-id>`

**Verification**: `haex verify [--exit-code]`

**Discovery**: `haex atoms list --source <url>`, `haex atoms show
<atom-id> --source <url>`

**Migration**: `haex migrate [--dry-run] [--check]`

**Constitution**: `haex constitution assemble`, `haex constitution show`

**Store admin**: `haex store prune [--dry-run]`, `haex store status`

**Hook runtime**: `haex hook run <trigger> [--json-context <fd>]`

**Rationale**: pnpm-inspired mental model. Single binary matches
git/docker/kubectl convention. Verb-noun surface is small enough to
memorize.

**Consequence**: `haex-init` binary is renamed. Old `haex-init` invocations
break at v2 boundary. Migration path (D10) is invoked as `haex migrate` and
documents the renamed command in its output; `haex-init migrate` is not a
supported alias.

## Consolidated model

### Consumer `.haex-hive.json` v2

```json
{
  "haex_hive_version": "2",
  "haex_hive_min_version": ">=2.0.0",
  "identity": "com.github.haexmas.haex-hive",
  "atoms": [
    {
      "source": "https://github.com/haexmas/haex-hive.git",
      "revision": "b2f884158dc90fbd4ab956f00ee100a82b6ec3eb",
      "track": "main",
      "includes": [
        "com.github.haexmas.haex-hive.constitution"
      ],
      "config": {}
    }
  ],
  "groups": [],
  "active_feature": null
}
```

Field-level notes:

- `haex_hive_version`: schema major, drives migrations
- `haex_hive_min_version`: minimum CLI that can consume this file (semver
  range), refuse-and-suggest-upgrade on mismatch
- `identity`: consumer's own reverse-DNS project ID
- `atoms[]`: replaces v1's `harness_sources[]`. Uniform shape per D12.
- `atoms[].track`: optional, non-authoritative branch annotation; a missing
  value means the branch is unknown and never weakens the required full SHA.
- `atoms[].config.<atom-id>`: optional object with `priority` and `values`
  only, as defined by D5/D7; the atom-ID must be selected by that entry.
- `groups`, `active_feature`: carried forward from v1 (Spec 004/005)

### Publisher root `manifest.json`

```json
{
  "haex_hive_version": "2",
  "publisher": "com.github.haexmas.haex-hive",
  "atoms": {
    "com.github.haexmas.haex-hive.constitution": {
      "path": ".specify/memory",
      "version": "1.3.0"
    }
  }
}
```

The `path` is the directory containing the atom's `manifest.json`.

### Atom `manifest.json`

```json
{
  "haex_hive_version": "2",
  "id": "com.github.haexmas.haex-hive.constitution",
  "version": "1.3.0",
  "priority": 10,
  "contributes": {
    "constitution": "constitution.md"
  },
  "defaults": {},
  "config_schema": "config.schema.json"
}
```

or, for a profile:

```json
{
  "haex_hive_version": "2",
  "id": "com.github.haexmas.blueprints.recommended",
  "version": "0.4.0",
  "includes": [
    "com.github.haexmas.blueprints.constitution",
    "com.github.haexmas.blueprints.skill-x"
  ]
}
```

or, for a blueprint bundling rules + hooks:

```json
{
  "haex_hive_version": "2",
  "id": "com.github.haexmas.blueprints.graphify",
  "version": "1.0.0",
  "priority": 200,
  "contributes": {
    "rules": ["rules/*.md"],
    "hooks": ["hooks/*.py"],
    "skills": ["skills/*/SKILL.md"]
  },
  "defaults": {
    "max_query_depth": 3
  },
  "config_schema": "config.schema.json"
}
```

### `install.lock`

```json
{
  "haex_hive_version": "2",
  "generated_by": "haex 2.0.0",
  "atoms": [
    {
      "id": "com.github.haexmas.haex-hive.constitution",
      "source": "https://github.com/haexmas/haex-hive.git",
      "source_sha": "b2f884158dc90fbd4ab956f00ee100a82b6ec3eb",
      "content_integrity": "sha256-<base64>",
      "resolved_from_entry_index": 0
    }
  ],
  "constitution": {
    "sources": ["com.github.haexmas.haex-hive.constitution"],
    "content_integrity": "sha256-<base64>"
  },
  "generated_content_integrity": "sha256-<base64>"
}
```

Alphabetically-sorted keys, deterministic JSON serialization (no
timestamps except in an inline non-hashed metadata block if needed for
human display).

## Constitution v1.3.0 amendment

Three changes, all deriving from decisions above:

1. **Principle IV — path semantics** (from PR #8 groundwork): The
   `path` component of a pinned reference may point to a directory
   containing a `manifest.json` (an atom), not only to a single file.
2. **Principle VI — clarification** (from D10): Any schema migration of
   a versioned config file (`.haex-hive.json`, `install.lock`,
   `constitution.md`, `manifest.json`, or successor schemas) MUST be
   done through a review-gated pattern: an explicit `migrate` command
   that (a) writes to a `.migrated` sidecar, (b) prints a review-able
   diff, (c) is deterministic, (d) supports `--dry-run/--check`. No
   automatic rewrite of versioned config files.
3. **New convention** (from D2, D16): The path `.haex-hive/constitution.md`
   is reserved for the consumer-side effective (possibly merged)
   constitution. Its content is either a straight-copy of a single source
   or the LLM-merged result of multiple sources. It is committed to the
   consumer repo.

Version bump: `1.2.0 → 1.3.0` (MINOR — expansion of an existing principle
plus a new convention, no NON-NEGOTIABLE relaxed). ADR in `docs/adr/`.

## Spec phasing

Instead of one mega-spec, four sequenced deliverables:

### Spec 007 — Manifest v2 + Migration + Constitution reshape

Landing content:

- `.haex-hive.json` v2 schema (D12, D16 layout)
- Publisher root `manifest.json` + atom `manifest.json` schemas (D11, D13)
- `haex migrate` command (D10)
- `haex constitution assemble` command (D2)
- `haex constitution show` command
- Root `manifest.json` for this repo (haex-hive as its own first publisher)
- Constitution v1.3.0 amendment landed
- Rename ADR: `haex-init` → `haex` and the distributable `haex` console
  script needed to run migration for v1 consumers

**Not in Spec 007**: `haex install` reconciliation logic, hook dispatcher,
store admin, publisher-side hydration of blueprint atoms. Those are Spec
008/009/010.

### Spec 008 — `haex install` reconciliation + storage layer

- `haex install` end-to-end (fetch → resolve atom-IDs → hash-verify → hydrate)
- Profile expansion and cycle detection before any hydration or lock output
- Content-addressed store at `$HAEX_HIVE_STATE/store/` (D15)
- `.haex-hive/generated/rules.md` assembly with priority ordering (D5)
- Jinja2 rendering (D4) with deterministic context (D9)
- `haex verify` + git pre-commit-hook installation (D9)
- `haex store prune`, `haex store status`
- `haex add`, `haex update`, `haex remove` verbs

### Spec 009 — Hook dispatcher (Python-only)

- `haex hook run <trigger>` (D1)
- Python-subprocess execution with JSON stdin context
- Hook discovery from `.haex-hive/generated/hooks/<trigger>/`
- Hook error semantics (fail-fast vs. warn-continue — TBD)
- Timeout/env-isolation contract
- Consumer-side hook install (git-hooks wiring, pre-commit dispatcher)

### Spec 010 — Publisher manifest contract + Blueprint atoms

- Blueprint-type atom hydration (rules/hooks/skills/config)
- `contributes.rules` glob resolution with path-segment semantics
- Agent adapters (Claude Code `.claude/settings.json`, Codex
  `.codex/config.toml`, etc.) — D6-compatible pointer emission
- `haex atoms list`, `haex atoms show` (D17 discovery verbs)
- Publisher-profile reference examples and transitive-resolution coverage
- Reference publisher-atom examples

## Migration path v1 → v2

Existing consumers using v1 `.haex-hive.json` (Spec 004/005 shape):

```json
{
  "haex_hive_version": "1",
  "identity": "github.com/haexmas/haex-hive",
  "harness_sources": [
    {
      "role": "constitution",
      "repository": "self",
      "revision": "b2f884...",
      "path": ".specify/memory/constitution.md"
    }
  ]
}
```

Automatic migration produced by `haex migrate`:

```json
{
  "haex_hive_version": "2",
  "haex_hive_min_version": ">=2.0.0",
  "identity": "com.github.haexmas.haex-hive",
  "atoms": [
    {
      "source": "https://github.com/haexmas/haex-hive.git",
      "revision": "b2f884...",
      "includes": [
        "com.github.haexmas.haex-hive.constitution"
      ],
      "config": {}
    }
  ],
  "groups": [],
  "active_feature": null
}
```

Migration rules (deterministic — same input → byte-identical output):

| v1 input shape | Deterministic v2 result |
|---|---|
| `identity: "github.com/<owner>/<repo>"` | Lowercase both `<owner>` and `<repo>`, construct `com.github.<owner>.<repo>`, then validate the result against the v2 reverse-DNS grammar before writing the sidecar. |
| `identity` already matches the v2 reverse-DNS grammar | Preserve it unchanged. |
| Any other schema-valid `identity` | Refuse: `cannot migrate identity: not a GitHub identity or v2 reverse-DNS ID`. |
| Every role-carrying entry (`role`, `repository`, `revision`, `path`), whether `repository` is `self` or external | Resolve `self` to the consumer's `remote.origin.url`, resolve the v1 7–40-character revision to its full 40-character commit SHA, and read that publisher's root `manifest.json` at that SHA. Select the one atom whose declared directory contains `path` and whose contribution declares that file. Emit its source, full SHA, and atom-ID in `atoms[]`. Refuse zero or multiple matching atoms with the entry index and path. |
| Multiple role-carrying entries | Convert every entry using the preceding rule. Entries with the same source and full SHA are grouped into one `atoms[]` entry; its `includes` are bytewise atom-ID sorted. Other entries are sorted by source, full SHA, then atom-ID. `config` is `{}` and `track` is omitted because v1 has no branch annotation. |
| Optional v1 `identity_note`, `groups`, and `active_feature` | Preserve unchanged. The v2 schema retains these optional compatibility fields. |
| Permission-only entry with only `repository` | Refuse: `cannot migrate harness_sources[i]: permission-only repository scope has no v2 atom equivalent`. |
| Permission-only entry with `repository` and `revision` | Refuse: `cannot migrate harness_sources[i]: permission-only repository@revision scope has no v2 atom equivalent`. |
| Permission-only entry with `repository` and `paths` (with or without `revision`) | Refuse: `cannot migrate harness_sources[i]: permission-only paths scope has no v2 atom equivalent`. |

The final three rows cover every valid v1 permission-only shape. v2's
`atoms[]` grants concrete atom content rather than a general reference
permission, so dropping or widening such a scope would change authorization;
the operator must replace it with explicit v2 atom entries in a reviewed PR.
If a `self` repository has no `remote.origin.url`, the requested commit is
unavailable, a pin cannot be expanded to a full SHA, or the required v2
publisher manifest is absent, migration refuses with the relevant entry index
and leaves the original file untouched; it also removes any temporary or
previous migration sidecar as required by D10.

Output written to `.haex-hive.json.migrated`. User reviews, moves manually,
commits. `haex install` on the v2 file then reconciles.

## Deferred / open questions

Non-blocking for Spec 007 but must be resolved by Spec 008/009/010:

- **Hook execution model**: subprocess (isolation, clean env) vs
  in-process import (perf, cross-hook state). Currently leaning
  subprocess for isolation.
- **Hook error semantics**: fail-fast, warn-continue, per-hook
  configurable. TBD in Spec 009.
- **Cache eviction policy for `.haex-hive/generated/`**: auto-cleanup
  when `.haex-hive.json` shrinks vs preserve-until-explicit. Currently
  leaning auto-cleanup (project-local safe).
- **Config merge semantics for length-N `includes[]`**: user's config
  map has atom-ID keys; but what if two atoms in the same includes
  share a config-key name? Currently: each atom gets its own subtree
  under `config.<atom-id>.values.<key>`, no cross-atom shared keys.
- **Multi-agent adapter framework**: agents that don't do markdown
  loading (Codex TOML, others). Framework Spec 010 territory; per-agent
  adapters ship incrementally.
- **`haex init --from-repo`**: the Spec 006 bootstrap-from-neighbor
  convenience mode. Not blocking Spec 007; could land in Spec 008 or a
  later add-source-focused mini-spec.

## Constitution compliance check

All eight NON-NEGOTIABLE principles:

- **I (No Secrets in Git)**: no change; content stores hold public git
  content only, and D7 permits only device-local keychain references—not
  plaintext secret values—in committed effective config.
- **II (No Absolute Paths in Versioned Config)**: `.haex-hive/` and
  `.haex-hive.json` remain repo-relative. `$HAEX_HIVE_STATE/` is
  device-local, never in versioned config.
- **III (Project Identity Is Device-Independent)**: identity is
  reverse-DNS derived from git remote URL. Same across devices by
  construction.
- **IV (Cross-Repo References Pin Immutable Revisions)**: every atom
  entry carries `source + revision (full SHA)`. Track is convenience.
  Extension: `path` may point to a directory (D11, amended in v1.3.0).
- **V (External Sources Are Opt-in Per Project)**: unchanged;
  `.haex-hive.json`'s `atoms[]` is the explicit allowlist.
- **VI (Self-Modifying Instructions Are Always Review-Gated)**:
  reinforced. D10's migration pattern is a candidate v1.3.0 clarification.
  All schema evolutions land through sidecar-diff-manual-review.
- **VII (Relay Unavailability Never Blocks Local Work)**: preserved.
  Constitution merge sync (D2) uses git as primary channel; Nostr is
  optional notify only.
- **VIII (No Concealment Instructions in Agent Output)**: unaffected.

Zero conflicts. Amendment to Principle IV and clarification to Principle
VI are the only two constitution changes.
