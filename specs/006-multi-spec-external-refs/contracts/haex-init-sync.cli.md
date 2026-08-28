# CLI Contract: `haex-init sync`

**Phase**: 1 (planning)
**Spec references**: FR-021 through FR-027a, FR-038; SC-002, SC-003,
SC-006, SC-007, SC-011

Mechanical contract for the new `haex-init sync` sub-command. All
behavior below must be respected byte-for-byte by the implementation
and by every test that asserts against it.

## Synopsis

```
haex-init sync [--dry-run] [--yes]
```

## Purpose

Bring the consumer project into a resolved state consistent with its
`.haex-hive.json`:

1. Ensure every declared producer is cloned under the state area
2. Ensure every pinned revision is reachable in the local clone
3. Extract every required file to a content-addressed extract path
4. Regenerate `.haex-hive.local.json` mapping resolved keys to
   absolute paths
5. Ensure `.gitignore` entry for `.haex-hive.local.json` is present

## Flags

| Flag | Meaning |
|---|---|
| `--dry-run` | Compute the ExpansionPlan and print the action plan; exit 0 if nothing to do, 1 if actions pending. No fetches, no writes. |
| `--yes` | Auto-confirm any interactive prompts (currently none in `sync`; reserved for future prompts). Required for non-TTY stdin. |

## Exit codes (FR-027a — Spec 005 scheme)

| Code | Meaning | Failure cases from FR-026 |
|---|---|---|
| **0** | Success (applied cleanly, or `--dry-run` had no pending actions). | — |
| **1** | `--dry-run` found pending actions. | — |
| **2** | Refused (bad CLI, schema-invalid config, precondition unmet). | (b) explicit item path absent at pinned revision, (c) `additional_include` glob matches nothing, (d) include match is symlink/non-regular, (e) local clone origin URL disagrees, (f) storage-name collision with distinct URLs, (g) resolved key collision |
| **3** | External-ref verification failed. | (a) pinned revision unreachable after fetch; any auth/reachability failure per FR-037 |
| **4** | Git subprocess failed unexpectedly (unrecognised git error, timeout, disk full during git operation). | — |

All non-zero exits accompanied by a **structured stderr diagnostic**
naming the offending entry, the offending path (if applicable), and
a remediation hint. Format:

```
haex-init sync: <ROLE-CODE>: <one-sentence problem>
  entry: harness_sources[<index>] (name: <name>, repository: <url>)
  detail: <specific value that failed> (e.g., path, sha, key)
  fix: <one-line remediation hint>
```

## Preflight (order of validation, before any mutation)

Per FR-022: preflight succeeds fully or the whole run refuses without
side effects.

1. **CLI parse** — invalid flags → exit 2 with usage note
2. **`.haex-hive.json` exists + readable** — else exit 2
3. **`.haex-hive.json` schema validation** — else exit 2 with schema
   error path
4. **Storage-name / URL uniqueness across entries** — collision →
   exit 2 (case f)
5. **Alias / key uniqueness across entries** — collision → exit 2
   (case g)
6. **Per entry**:
   - If clone missing, plan clone
   - If clone present, verify `origin.url` (case e) → exit 2 on
     mismatch
   - Plan `git fetch origin` (network required)
   - Plan `git cat-file -e <revision>^{commit}` to verify
     reachability
   - For each `items[]`, plan `git ls-tree` at `<revision>` to
     verify `path:` exists as regular file / directory
   - For each `additional_include` entry, plan `git ls-tree -r
     --format='%(objecttype) %(path)'` and match glob → non-empty
     required
   - For each `auto_include: "speckit-defaults"` path, expand
     against pinned tree
   - Reject any symlink / non-regular entry (case d) → exit 2
7. **Compute `resolved` map** — assign keys deterministically
8. **Compute `constitutions` array** — top-level `role:
   "constitution"` first, then nested items in declared order
9. **Build the target LocalStateTable in memory**
10. **Serialise to JSON** in memory — validate against
    `haex-hive-local.schema.json`

Everything above happens with **zero writes to the consumer repo or
to the state area**. On `--dry-run`, exit here with code 0 or 1.

## Apply phase (only after preflight succeeds)

Per FR-023/FR-024/FR-025: every write is a temp-file + atomic rename.
The order:

1. **Acquire `$HAEX_HIVE_STATE/repos/<name>/.sync.lock`** for each
   producer clone touched, in `name`-sorted order (avoid deadlock
   across concurrent multi-producer syncs). Uses `fcntl.flock`
   / `msvcrt.locking` per Research §2.
2. **Clone missing producers** — `git clone <url>
   <state-area>/repos/<name>/`, with directories created at
   `0700` mode (Research §4).
3. **Fetch on existing producers** — `git fetch origin`
4. **Verify reachability of pinned revisions** — for each entry,
   `git cat-file -e <sha>^{commit}`. On miss: `git fetch origin <sha>`
   (fallback for producer rewound branches). On persistent miss:
   exit 3.
5. **Extract missing content**:
   - For each `ResolvedPath` in the plan, ensure the target
     directory exists at `0700`
   - Check if the target file exists AND its byte-length matches
     the git-object size → reuse
   - Otherwise: `git cat-file blob <sha>:<path>` piped to
     `<target>.tmp-<pid>-<rand>`, close+fsync, then
     `os.replace(<tmp>, <target>)`, then `os.chmod(target, 0o600)`
6. **Write LocalStateTable** — serialise + fsync to
   `.haex-hive.local.json.tmp-<pid>-<rand>` in consumer repo root,
   then `os.replace(...)` to `.haex-hive.local.json`. Set
   `0600` mode.
7. **Update `.gitignore`** — if the tool-managed marker block is
   absent, add it (per Spec 005 marker-block conventions) with the
   entry `.haex-hive.local.json`. If a stray outside-marker
   `.haex-hive.local.json` line exists elsewhere, do NOT add a
   duplicate; note it in a warning line on stdout.
8. **Release lock** — implicit on process exit.

Any error during Apply that reaches the CLI: temp files are removed
best-effort, target files are untouched (per FR-022, FR-024). Locked
producer clones may end up with newly-cloned but no-extracts state
— that is safe (idempotent re-sync recovers).

## Output on success (exit 0)

Human-readable summary on stdout. Example (not enforced as machine
contract; the machine contract is exit code + stderr on failure):

```
haex-init sync: 2 producers, 3 resolved keys, 0 changes.
  secana-specs @ b2f8841... (in-sync)
  another-source @ 7c3fa12... (in-sync)
```

Or, when changes applied:

```
haex-init sync: 2 producers, 12 resolved keys, 8 changes.
  secana-specs @ b2f8841... -> a1c4d92...
    + 5 new extract files
    ~ 3 refreshed extract files
  another-source @ 7c3fa12... (in-sync)
```

## Output on `--dry-run`

Exit 0 (no pending actions) or 1 (pending actions listed).
Human-readable structured plan on stdout:

```
haex-init sync (dry-run): 2 producers, 12 resolved keys
  secana-specs @ a1c4d92... [new pin, was b2f8841...]
    + fetch producer
    + extract 8 files under .extracts/@a1c4d92.../
    ! constitution moved: .specify/memory/constitution.md ->
      unchanged path, byte-changed content
  another-source (in-sync, no action)
```

## Interactions with other haex-init flags

- `haex-init sync` is INDEPENDENT of `--pin-constitution` (which is
  its own Spec 005 sub-command). Running `haex-init sync` never
  changes `.haex-hive.json`.
- `haex-init add-source` may trigger `sync` post-write per FR-032
  unless `--no-sync` is passed.
- `haex-init` (no sub-command, Spec 005 initial-bootstrap) is
  UNCHANGED by Spec 006. It never runs `sync` — the operator
  invokes `sync` explicitly after adding sources.

## Constitution-check crossreferences

Every gate below MUST hold across every code path in the
implementation:

- Principle I: no branch of `sync` ever writes an HTTPS URL with
  userinfo into `.haex-hive.json` (FR-007) — but note `sync` doesn't
  write config anyway; the check is upstream in `add-source`
- Principle II: `.haex-hive.local.json` (the file `sync` writes)
  is gitignored (FR-018) — its device-local paths never touch
  versioned config
- Principle III: `.haex-hive.json` retains only device-independent
  identifiers (repository URLs, storage names, SHAs)
- Principle IV: every produced key resolves to a `git show
  <sha>:<path>` operation; content NEVER read from a working tree
- Principle V: no auto-behavior inherits content not declared in the
  consumer's own `.haex-hive.json`
- Principle VI: `sync` writes ONLY device-local state
  (`.haex-hive.local.json`, `$HAEX_HIVE_STATE`); it MUST NEVER
  mutate `.haex-hive.json` or any file under
  `.specify/` in the consumer or producer
