# Contract: `spec-resolve` CLI

**Date**: 2026-08-27
**Feature**: 004-cross-repo-refs

CLI command surface, exit codes, input/output format, and side effects
for the `spec-resolve` tool. Implementation must conform to this
contract; tests assert against it.

## Executable

- Path: `.specify/scripts/spec-resolve`
- Interpreter: `#!/usr/bin/env python3` (Python 3.10+)
- Executable bit MUST be set on commit.

## Global behavior

- Every invocation loads `.haex-hive.json` at the current working
  directory (or `--repo <path>` if given). If loading or schema
  validation fails, ALL subcommands exit non-zero with a message
  naming the specific problem (per FR-017, fail-closed whole-file).
- Exit codes:
  - `0` — success.
  - `1` — reference or scope refused by allowlist (Principle V enforcement).
  - `2` — config invalid (schema violation, unknown role, forbidden field combo).
  - `3` — resolution failed for a non-permission reason (missing SHA in cache and offline; git-fetch failure; path not present at pinned SHA).
  - `4` — invalid CLI usage (bad flag, missing required argument).
  - `5` — unexpected internal error (uncaught exception, must never happen in normal operation).
- All error output goes to stderr; all resolved content and structured
  status output goes to stdout.
- No log file is created; nothing is written to disk under the working
  tree; the only side effect anywhere is populating the shared cache
  directory (subcommands `prefetch` and `resolve` cache-miss path).

## Subcommand: `resolve`

### Synopsis

```text
spec-resolve resolve --role <name>
spec-resolve resolve --repository <url|self> --revision <sha> --path <p>
spec-resolve resolve --from <spec-ref-json-path>
```

### Options

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--role <name>` | string | (a) | Resolves the role-carrying entry in `.haex-hive.json.harness_sources` whose `role == <name>`. Phase 1: only `constitution`. Exactly one such entry must exist. |
| `--repository <url\|self>` | string | (b) | Direct triple mode. Requires `--revision` and `--path`. |
| `--revision <sha>` | string | (b) | Full SHA (7-40 lowercase hex chars). Case-normalized to lowercase before validation. |
| `--path <p>` | string | (b) | Repo-relative path. |
| `--from <spec-ref-json-path>` | path | (c) | Reads a `spec-ref.json` file, resolves each named entry within, prints them to stdout separated by a JSON envelope (see Output). |
| `--repo <path>` | path | No | Override for the enclosing repo (default: cwd). |

One of (a), (b), (c) MUST be given. Providing more than one is a
usage error (exit 4).

### Behavior

1. Load and validate `.haex-hive.json` (fail-closed on any error).
2. Resolve the target reference(s) per the mode.
3. Enforce allowlist:
   - Role-carrying entry's own reference is self-permitted.
   - Direct or `--from` references must match at least one entry
     in `harness_sources`. First match wins (array order).
4. If reference is `self`: read from local repo via
   `git show <sha>:<path>`. If SHA is missing, exit 3 with a message
   naming the missing SHA and `.haex-hive.json`'s pin.
5. If reference is external: check cache; if hit, `git show`; if
   miss and network available, fetch (Decision 3 in research.md);
   if miss and offline, exit 3 with a message naming the missing SHA.
6. Write resolved content to stdout as-is (binary-safe; no encoding
   transformation; no trailing newline added or removed).

### Output

- **Mode (a) or (b)**: raw file content to stdout, exit 0.
- **Mode (c)**: JSON envelope on stdout — each entry as a JSON object
  wrapping the content, separated by a well-defined boundary. Exact
  envelope shape:

  ```json
  {
    "refs": [
      {
        "name": "<key from spec-ref.json>",
        "repository": "...",
        "revision": "...",
        "path": "...",
        "content_base64": "<base64-encoded content>",
        "byte_length": 12345
      },
      ...
    ]
  }
  ```

  Base64-wrapping keeps the envelope binary-safe without stream-parsing
  complexity. Consumers decode as needed. Only used in `--from` mode —
  single-ref mode returns raw content to stdout.

### Errors

- Ref not in allowlist: exit 1, stderr message like:
  `spec-resolve: refusing reference {repository}@{revision}:{path} — not permitted by any entry in harness_sources.`
- Config invalid: exit 2, stderr message pointing at the offending
  entry (by array index or role) and the specific constraint violated.
- SHA missing offline: exit 3, message names SHA + repo.
- Ambiguous mode: exit 4, message lists provided flags and required
  choice.

## Subcommand: `prefetch`

### Synopsis

```text
spec-resolve prefetch
spec-resolve prefetch --dry-run
```

### Options

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--dry-run` | flag | No | Prints what would be fetched, doesn't touch the cache or network. |
| `--repo <path>` | path | No | Override for the enclosing repo (default: cwd). |

### Behavior

1. Load and validate `.haex-hive.json` (fail-closed on any error).
2. Enumerate every reference discoverable in the repo:
   - All role-carrying entries in `harness_sources`.
   - All entries in every `specs/*/spec-ref.json` (glob).
   - Permission-only entries in `harness_sources` are NOT prefetched —
     they name scopes, not concrete refs.
3. For each concrete reference, check if the pinned SHA is present in
   its target cache directory (or in the local repo for `self`).
4. For missing SHAs:
   - If `--dry-run`: print `MISSING {repository}@{revision}` to stdout.
   - Else: attempt fetch per the ladder in research.md Decision 3.
5. Update per-cache-dir `.haex-hive-cache-meta.json` with new
   `last_fetch` timestamp.

### Output

- `--dry-run`: line per reference, plain text: `OK <ref>` for
  already-present, `MISSING <ref>` for not-yet-cached, `UNRESOLVABLE
  <ref> (<reason>)` for refs whose refspec fetch failed even at fallback.
- Non-dry: quiet on success (only fetch progress from `git` if a TTY
  is attached; suppressed if not). Errors go to stderr.

### Exit codes

- 0 — all refs cached (or all were already cached in dry-run).
- 3 — at least one reference could not be fetched. Message names each.

### Errors

- Config invalid: exit 2 (same as resolve).
- Network unreachable, cache miss: exit 3, message names each affected
  ref.

## Subcommand: `status`

### Synopsis

```text
spec-resolve status
spec-resolve status --json
```

### Options

| Option | Type | Required | Notes |
|--------|------|----------|-------|
| `--json` | flag | No | Emit structured JSON on stdout instead of the compact text summary. |
| `--repo <path>` | path | No | Override for the enclosing repo (default: cwd). |

### Behavior

1. Load and validate `.haex-hive.json`.
2. Enumerate discoverable references (same rule as `prefetch`).
3. For each: check cache presence WITHOUT network. Read
   `.haex-hive-cache-meta.json` for `last_fetch`.
4. Print summary.

### Output — text mode (default)

Single line for the snippet's staleness indicator:

```text
3 refs, 3 cached, last update-check: 2026-08-27 (0 days ago)
```

If any ref is not cached:

```text
3 refs, 2 cached (1 missing), last update-check: 2026-08-27 (0 days ago)
```

If no update-check has ever happened for any external source:

```text
1 ref, 1 cached, last update-check: never
```

`self` references count as always cached (no network needed).

### Output — `--json` mode

```json
{
  "refs_total": 3,
  "refs_cached": 3,
  "refs_missing": 0,
  "last_update_check": {
    "iso": "2026-08-27T12:00:00Z",
    "days_ago": 0
  },
  "sources": [
    {
      "repository": "self",
      "cached": true,
      "last_fetch": null
    },
    {
      "repository": "https://gitlab.com/...",
      "cached": true,
      "last_fetch": "2026-08-27T11:45:23Z"
    }
  ]
}
```

### Exit codes

- 0 — status printed (whether or not refs are missing).
- 2 — config invalid (fail-closed).
- Note: status does NOT exit non-zero for missing cache; the missing
  count is data, not a failure. Consumers who want "refuse if missing"
  behavior use `prefetch` first.

## Subcommand — not shipped in Spec 004

Explicitly deferred to Spec 005:

- `check-updates` (fetch and diff against pinned)
- `bump` (write proposed SHA-update commits)

Invoking either exits 4 with a message pointing at Spec 005.

## Flags that MUST NOT exist in Spec 004

- Any "quiet" / "no-output" flag that suppresses the resolved content
  or error messages (would border on Principle VIII — an operator
  running the tool must see what it does).
- Any flag that writes secrets to disk (Principle I).
- Any flag that accepts an absolute path in a value that will be
  committed (Principle II).

## Testing hooks

`tests/spec-resolve/` invokes each subcommand under scripted scenarios:

- Happy path: run with a valid config and fixture; assert stdout hash
  and exit 0.
- Refusal path: run with an allowlist-mismatched reference; assert
  exit 1 AND specific stderr substring AND no writes anywhere.
- Config-invalid path: run with a malformed `.haex-hive.json`;
  assert exit 2 AND specific stderr substring naming the offending
  entry.
- Cache-miss offline: run with an unpopulated cache and network
  disabled (env var or namespace); assert exit 3.
- Schema-tool agreement: for each valid/invalid sample config, both
  the schema validator (in test-harness only) and the tool agree on
  accept/reject.
