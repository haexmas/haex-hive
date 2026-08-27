# spec-resolve

Repo-local CLI that resolves cross-repo references pinned by immutable
Git SHA. Ships with Spec 004 — cross-repo references (Phase 1).

The authoritative command contract is
[spec-resolve.cli.md](../specs/004-cross-repo-refs/contracts/spec-resolve.cli.md).
This document is the operator-facing reference: what the tool does, how
its cache is laid out, how to wire your editor to the schema, and how
to extend the Spec 003 session-start snippet to call it.

## Command surface

Executable: `.specify/scripts/spec-resolve`
(`#!/usr/bin/env python3`, Python 3.10+ stdlib only, no third-party
dependencies.)

Every subcommand loads `.haex-hive.json` at the current working
directory (or `--repo <path>`) and validates it against the schema
before doing anything else. If the config is missing or invalid, ALL
subcommands exit non-zero with a stderr message that names the
specific problem.

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success. |
| 1 | Reference or scope refused by allowlist (Principle V enforcement). |
| 2 | Config invalid (schema violation, unknown role, forbidden field combo). |
| 3 | Resolution failed (missing SHA in cache and offline; git-fetch failure; path not present). |
| 4 | Invalid CLI usage (bad flag, missing required argument, deferred subcommand). |
| 5 | Unexpected internal error. |

Global option: `--repo <path>` — override the enclosing repo (default:
cwd).

### `resolve`

Resolves one reference to stdout.

```text
spec-resolve resolve --role <name>
spec-resolve resolve --repository <url|self> --revision <sha> --path <p>
```

`--role` uses the role-carrying entry in `harness_sources`
(Phase 1: only `constitution`). The direct triple form
(`--repository/--revision/--path`) is validated against the allowlist —
role-carrying entries are self-permitting for their own triple; any
other reference must match a `harness_sources` entry.

Output is raw file bytes to stdout, unmodified — no encoding change,
no trailing newline added or removed. Safe to redirect into a file
and `diff` against the source-of-truth blob at that SHA.

### `prefetch`

Populates the cache for every discoverable reference.

```text
spec-resolve prefetch
spec-resolve prefetch --dry-run
```

Enumerates every role-carrying entry in `harness_sources`
**plus** every entry in every `specs/*/spec-ref.json`, deduplicates by
(repository, revision, path), and fetches any missing SHAs into the
per-repo cache directory. Permission-only `harness_sources` entries
are NOT prefetched — they name allowlist scopes, not concrete refs.

`--dry-run` prints `OK <ref>` for already-cached and `MISSING <ref>`
for not-yet-cached references without touching the network.

### `status`

Reports cache presence and last-update-check for known references.

```text
spec-resolve status
spec-resolve status --json
```

Text mode is the default and produces the compact one-liner the
session-start snippet consumes:

```text
1 ref, 1 cached, last update-check: never
3 refs, 2 cached (1 missing), last update-check: 2026-08-27 (0 days ago)
```

`--json` emits a structured envelope with the per-source breakdown.
`self` references count as always cached (no network needed).

Note: `status` does NOT exit non-zero for missing cache — the missing
count is data, not a failure. Consumers that want fail-on-missing
behaviour run `prefetch` first.

### Deferred subcommands

`check-updates` and `bump` are named in the parser so `spec-resolve
--help` lists them, but they exit 4 with a pointer to Spec 005 (they
land there).

## Cache location and layout

Cache root: `$XDG_CACHE_HOME/haex-hive/repos/`, falling back to
`~/.cache/haex-hive/repos/` when `$XDG_CACHE_HOME` is unset. Under
that, one bare-Git-repo-shaped directory per distinct `repository`
string:

```text
~/.cache/haex-hive/repos/
├── <hash1>/            # bare git dir for repo-URL-1
│   ├── HEAD
│   ├── objects/
│   ├── refs/
│   └── .haex-hive-cache-meta.json   # {repository, first_seen, last_fetch}
├── <hash2>/
└── ...
```

`<hashN>` = first 16 hex chars of
`SHA-256(byte-identical-repository-string)`. Two URL variants of the
same underlying repo hash to different directories — acceptable per
Spec 004 Q1 clarification (string-exact matching is the whole point
of `harness_sources` allowlist enforcement).

### Cache-wipe safety

The cache is a pure Git object cache with a metadata sidecar. Deleting
`~/.cache/haex-hive/` is always safe:

- Every referenced SHA is still pinned in some committed
  `.haex-hive.json` or `spec-ref.json` — re-fetch is deterministic.
- No secrets ever land in the cache — only Git objects fetched from
  the URLs listed in `harness_sources` (Principle I).
- Next `spec-resolve resolve` or `prefetch` invocation re-populates
  the needed slice on demand.

If the cache metadata sidecar (`.haex-hive-cache-meta.json`) goes
missing, `spec-resolve status` reports `last update-check: never`
until the next fetch writes a fresh sidecar. No consequence for
correctness — the sidecar is timing telemetry, not authoritative
state.

## JSON Schema editor mapping

`.haex-hive.json`'s canonical shape is defined by
[`.specify/schemas/haex-hive.schema.json`](../.specify/schemas/haex-hive.schema.json).
Mapping your editor to this schema unlocks inline validation and
autocomplete while you edit — the editor catches unknown roles,
missing revisions, invalid SHA patterns, and rejected URL schemes
before you ever run `spec-resolve`.

### VSCode

Add to your workspace `.vscode/settings.json` (or user settings) inside
this repo:

```json
{
  "json.schemas": [
    {
      "fileMatch": [".haex-hive.json"],
      "url": "./.specify/schemas/haex-hive.schema.json"
    }
  ]
}
```

Open `.haex-hive.json` in VSCode. The editor:

- Autocompletes `role`, `repository`, and other top-level keys.
- Flags unknown role names with `Value is not accepted. Valid values:
  "constitution"`.
- Flags mixed-case or wrong-length SHA values against the pattern
  `^[0-9a-f]{7,40}$`.
- Flags `additionalProperties` violations at the top level and inside
  each `harness_sources` entry.

### JetBrains (IntelliJ / PyCharm / GoLand / …)

Preferences → Languages & Frameworks → Schemas and DTDs → JSON Schema
Mappings → `+`:

- **Name**: `haex-hive`
- **Schema file or URL**: `.specify/schemas/haex-hive.schema.json`
- **Schema version**: Draft 7
- **File path pattern**: `.haex-hive.json`

Apply. Reopen `.haex-hive.json`. Same inline validation and completion
as VSCode.

### Verifying the mapping

Introduce any of these into `.haex-hive.json` and confirm the editor
highlights it before saving:

- `"role": "not-a-real-role"` — unknown enum value.
- Remove `"revision"` from a role-carrying entry — missing required.
- Add `"paths": [...]` alongside `"path"` on a role entry — forbidden
  combination.
- `"revision": "406FC786..."` (uppercase) — pattern mismatch.
- `"repository": "file:///tmp/foo"` — pattern mismatch on the URL scheme.

The same malformations, when saved and passed to `spec-resolve
status`, exit 2 with the same error described. See
[`.validation-runs/2026-08-27-story-3.md`](../specs/004-cross-repo-refs/.validation-runs/2026-08-27-story-3.md).

## Snippet extension (session-start integration)

Spec 003 delivered a global session-start snippet that operators paste
into their per-CLI configuration (Claude's user-level `CLAUDE.md`,
Codex's `AGENTS.md`, etc.). Spec 004 adds one new step (Step 8) that
runs `spec-resolve status` as the first pre-work check for the
haex-hive-opted-in repo.

Operators who installed the earlier snippet: replace the snippet's
Step 8 (or append it if the snippet did not have one) with the block
below.

```markdown
### Step 8 — Verify harness-source cache freshness for haex-hive-opted-in repos

If `.haex-hive.json` is present at the repo root, run:

    .specify/scripts/spec-resolve status

Read the output. It looks like `N refs, M cached (K missing), last
update-check: <date | never>`.

- Exit 0, `K == 0`: continue.
- Exit 0, `K > 0` (missing refs): tell the operator which refs are
  missing (`.specify/scripts/spec-resolve prefetch --dry-run` prints
  the per-ref detail). Do not proceed with any work that depends on
  the missing SHAs until the operator authorises `spec-resolve
  prefetch` (network access required) or updates `.haex-hive.json`.
- Exit 2 (config invalid): read the stderr line — it pinpoints the
  offending `harness_sources[N]` entry and constraint. Refuse to
  proceed with harness work; ask the operator to correct
  `.haex-hive.json` first.

This step is a no-op in repos without a `.haex-hive.json`.
```

Rationale for pasting this yourself rather than committing it to the
repo: Spec 003 established that the snippet lives per-operator, not
per-repo, so this repo cannot auto-update someone else's private
config. See ADR 0002 for the underlying constraint.

## Wiring an external `harness_sources` entry (consuming-repo how-to)

The Phase 1 haex-hive repo uses only a `self`-role constitution entry
— no external harness sources are consumed yet. When a downstream
consuming repo needs to pull content from an external harness (e.g.,
a team's shared spec-kit repository), the pattern is:

1. Add a permission-only entry to `.haex-hive.json`:

   ```json
   {
     "repository": "https://gitlab.example/team/harness",
     "revision": "<full 40-char SHA>",
     "paths": ["specs/some-spec/plan.md", "docs/patterns.md"]
   }
   ```

   `revision` and `paths` are both optional; omitting them widens
   the permission scope. Omit both to permit any SHA and any path in
   that repository.

2. Reference concrete refs in a `specs/<feature>/spec-ref.json` file:

   ```json
   {
     "team-plan": {
       "repository": "https://gitlab.example/team/harness",
       "revision": "<full 40-char SHA>",
       "path": "specs/some-spec/plan.md"
     }
   }
   ```

   The referenced (repository, revision, path) MUST fall within the
   permission-only entry's scope — otherwise `spec-resolve`
   refuses at load time (Principle V).

3. `spec-resolve prefetch` populates the per-URL cache directory
   with the required Git objects.

4. `spec-resolve resolve --repository <url> --revision <sha> --path
   <p>` streams the resolved bytes to stdout for consumption by the
   downstream tool (e.g., a spec-kit compiler; deferred to Phase 2).

Every step above is auditable through commits — the review boundary
that Principle VI mandates.
