# CLI Contract: `haex-init add-source`

**Phase**: 1 (planning)
**Spec references**: FR-028 through FR-032; SC-004, SC-009

Mechanical contract for the new `haex-init add-source` sub-command.

## Synopsis

```
haex-init add-source [--from-repo <PATH>] [--url <URL>] [--revision <SHA>]
                     [--name <NAME>] [--auto-include <PRESET>]
                     [--additional-include <PATH>[,<PATH>...]]
                     [--role <ROLE>:<PATH>:<ALIAS>[,...]]
                     [--replace] [--no-sync] [--yes]
```

## Purpose

Add an `external-harness` entry to the current consumer's
`.haex-hive.json`. Two modes:

- **From-scratch mode**: prompt operator for all fields (or accept
  them via flags), validate, write.
- **`--from-repo <path>` mode**: read a neighbor consumer's
  `.haex-hive.json`, list its `external-harness` entries, prompt
  for selection, re-validate against current context, write.

After a successful write, trigger `haex-init sync` unless `--no-sync`
was passed (FR-032).

## Flags

| Flag | Meaning |
|---|---|
| `--from-repo <PATH>` | Bootstrap-from-neighbor mode. Path is a directory containing a `.haex-hive.json`. Mutually exclusive with `--url`, `--revision`. |
| `--url <URL>` | Producer repository URL. Required in from-scratch non-interactive mode. |
| `--revision <SHA>` | Full 40-hex-char SHA. Required in from-scratch non-interactive mode. |
| `--name <NAME>` | Storage name. Optional; defaults to URL basename with `.git` stripped. |
| `--auto-include <PRESET>` | Preset name (currently `speckit-defaults` or unset). |
| `--additional-include <PATH>[,<PATH>...]` | Comma-separated repo-relative paths. |
| `--role <ROLE>:<PATH>:<ALIAS>[,...]` | Comma-separated explicit-item declarations. Repeatable. |
| `--replace` | If an entry with the same `repository` already exists, replace it. Without this flag, duplicate refuses (exit 2). |
| `--no-sync` | Do NOT trigger `haex-init sync` after write. |
| `--yes` | Auto-confirm interactive prompts. Required for non-TTY stdin. |

## Exit codes (aligned with FR-027a Spec 005 scheme)

| Code | Meaning |
|---|---|
| 0 | Success — entry added (and `sync` succeeded, unless `--no-sync`) |
| 1 | Not applicable (`--dry-run` not supported for add-source) |
| 2 | Refused: bad CLI, schema violation, HTTPS with userinfo, invalid SHA, unsafe name, storage-name collision with different URL, duplicate `repository` without `--replace`, ambiguous resolved keys, neighbor `.haex-hive.json` schema-invalid |
| 3 | External-ref verification failed (rare during `add-source`; only if a triggered `sync` fails at that stage) |
| 4 | Git subprocess failed unexpectedly |

Structured stderr diagnostic same format as
[haex-init-sync.cli.md](haex-init-sync.cli.md).

## From-scratch mode: interactive flow

If flags are incomplete and stdin is a TTY, prompt sequentially:

1. **Repository URL** — validate SSH or credential-free HTTPS
   (FR-007). On HTTPS with userinfo → refuse loudly, tell operator
   to use SSH URL or credential manager.
2. **Revision** — full 40-hex-char SHA. Regex-validated.
   Note: no network round-trip here; reachability check happens
   only in the follow-up `sync`.
3. **Storage name** — default to URL basename with `.git` suffix
   stripped. Operator can accept default or override.
   Validated per FR-008. Storage-name-collision check against
   existing entries: if same `name` but different `repository`,
   refuse.
4. **auto_include** — offer `speckit-defaults` or none. Skip if
   `--auto-include` given.
5. **additional_include** — accept comma-separated paths. Skip if
   `--additional-include` given.
6. **items[]** — allow N `role`:`path`:`as` triples. Each `as`
   validated per FR-006 grammar. Skip if `--role` given.
7. **Confirm** — show the constructed entry, ask Y/N.

Non-TTY without `--yes` or without all required flags → exit 2.

## From-scratch mode: non-interactive flow

`--url` + `--revision` required. All other fields default or take
from flags. Prompts skipped entirely. `--yes` still required if
prompts would otherwise appear.

## `--from-repo` mode: interactive flow

1. Read `<PATH>/.haex-hive.json`
2. Schema-validate — refuse if invalid (FR-031, SC-004)
3. Enumerate `external-harness` entries in the neighbor's
   `harness_sources[]`
4. If 0 entries: exit 2 with message ("no external-harness entries
   in neighbor to copy")
5. If 1 entry: prompt Y/N for that single entry
6. If N entries: prompt operator to pick by number (0-indexed)
7. Re-validate selected entry against current context:
   - Storage-name collision with distinct URL in current consumer's
     config → refuse
   - Duplicate `repository` in current config without `--replace` →
     refuse
   - Any field validation that changed since neighbor wrote it →
     refuse and name the field
8. Confirm — show the entry that will be added, ask Y/N
9. On accept: append entry to current consumer's
   `.haex-hive.json`

## Write behavior

`.haex-hive.json` is rewritten atomically:

- Read current file
- Add / replace entry in memory
- Validate the resulting document against
  `haex-hive.schema.json`
- Write to `.haex-hive.json.tmp-<pid>-<rand>` in the consumer repo
- `os.replace` to `.haex-hive.json`
- Do NOT change file permissions (respect operator's umask —
  `.haex-hive.json` is a committed file, semantics are the
  operator's choice)

**No temp file leaks on failure** — best-effort cleanup on `sync`
startup mirrors what Research §3 says for `.haex-hive.local.json`.

## Post-write behavior

Unless `--no-sync`:

- Invoke `haex-init sync` as a subprocess (same argv[0] as the
  current process for accurate re-invocation)
- Pass through `--yes` if it was set
- `sync`'s exit code becomes `add-source`'s exit code

## Interactions

- `haex-init add-source` NEVER writes producer content or the
  device-local state area. It only mutates `.haex-hive.json`. The
  subsequent `sync` invocation handles state-area work.
- `--from-repo <path>` is READ-ONLY on `<path>`. Never mutates the
  neighbor.
- `--from-repo` combined with `--url` / `--revision` → refuse with
  usage error (bad CLI).

## Constitution-check crossreferences

- Principle I: FR-007 rejects HTTPS URLs with userinfo before write
- Principle II: no device-local paths ever land in
  `.haex-hive.json`
- Principle III: `repository` stays a device-independent URL,
  storage `name` is a stable identifier not a filesystem path
- Principle IV: every added entry pins a full 40-hex-char SHA
- Principle V: adding a source is the explicit review-gated act
  the constitution expects — operator invokes it, reviews the
  entry, commits through PR flow (Constitution v1.2.0 §Development
  Workflow)
- Principle VI: the review gate is the operator's PR review of the
  `.haex-hive.json` diff, not `add-source`'s own logic
