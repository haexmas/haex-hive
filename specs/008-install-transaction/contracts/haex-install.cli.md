# CLI Contract: `haex install`

**Spec**: [Spec 008 — Install Transaction Contract](../spec.md)
**Referenced by**: FR-001–FR-022

## Usage

```console
haex install [--repo-root PATH] [--verify-only] [--json]
```

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--repo-root PATH` | current working directory | Path to the project checkout. Inherited from the top-level `haex --repo-root` per Spec 007. |
| `--verify-only` | off | Acquire the SHARED read lock, validate the current `install.lock` schema/migration gate, verify recorded paths and generation agreement, then exit. Never mutates. Same shape as `haex verify` today. |
| `--json` | off | Emit the versioned `haex-install-result-v1` result object instead of human-readable status text. The result includes any capability degradations. |

Single-source installations use the deterministic fast path. Multi-source
installations use the same deterministic concatenation-with-provenance format
defined in [ADR 0010](../../../docs/adr/0010-drop-multi-source-llm-constitution-merge.md);
there is no model invocation, pending state, or interactive confirmation path.

Recovery is implicit: any subsequent `haex install` acquires the exclusive lock, removes a leftover `<root>.next/` sibling, retains `<root>.prev/` until the replacement is successfully published, and reinstalls from the deterministic pinned inputs. There is no separate `haex verify --recover` verb (retired 2026-09-02 by the detect+retry amendment).

## Behaviour matrix

| Invocation | Lock class | On success | On failure |
|---|---|---|---|
| `haex install` | Exclusive | Prints "installed generation `<gen>`" or "no changes", exit 0. Cleans stale `<root>.next/`; removes `<root>.prev/` only after successful publication. | Prints refusal reason + exit code per matrix below |
| `haex install --verify-only` | Shared | Prints "generation `<gen>` verified", exit 0 | Prints mismatch detail, exit per matrix |

## Exit codes

Uses the canonical set defined in [src/haex_hive/util/exit_codes.py](../../../src/haex_hive/util/exit_codes.py).

| Code | Trigger | Example diagnostic |
|---|---|---|
| 64 | Usage error | unknown subcommand, invalid flag, or missing flag value; no lock is acquired |
| 0 | Success | `installed generation g_20260831T142011Z_a4c2` |
| 2 | Input refuse (FR-006 / Principle V) | `.haex-hive.json not found` / `.haex-hive.json.atoms is empty (Principle V opt-in required)` |
| 3 | I/O refuse (FR-006) | `publisher clone for <source> not found under $HAEX_HIVE_STATE/repos/` |
| 4 | Validation refuse (FR-006) | `plan snapshot digest does not match commit snapshot; source mutated during install` |
| 5 | System refuse (FR-003) | `declared environment provider is unavailable` |
| 6 | Post-write validation (FR-005 / FR-009) | `install.lock schema or published generation validation failed` |
| 7 | Incomplete transaction | `journal cannot be recovered to a stable generation pair` |
| 8 | Constitution concealment (Principle VIII) | (from Spec 007's guard; unchanged) |
| 9 | Writer busy (FR-001 / FR-010) | `lock held by <pid>@<hostname> since <acquired_at> (heartbeat <n>s ago, ttl <t>s)` |
| 10 | Plaintext secret (Principle I) | (from Spec 007's guard; unchanged) |

## Refusal semantics

Every refusal MUST cite the specific requirement (FR-###) or Principle it enforces, and identify the offending file/entry, so the operator can locate and fix it without guesswork (FR-019).

Examples:

```text
haex install
error: exit=9 key=install-lock-busy (FR-001 / FR-010)
  lock held by 31245@laptop-hex.local since 2026-08-31T14:20:11Z
  (heartbeat 3s ago, ttl 60s)
  hint: wait or investigate PID 31245; if the process is dead, retry `haex install`

haex install
error: exit=4 key=commit-snapshot-mismatch (FR-006)
  .haex-hive.json digest changed during install
  plan snapshot: sha256-QK+AUjCuNhHjAJap8cbgk6VkyZipJm3f1ZIH4oOqigg
  commit snapshot: sha256-abc123...
  hint: another editor rewrote .haex-hive.json during the install; retry
```

The exit-code precedence is deterministic: parse/usage errors first; then
writer-lock acquisition (9); transaction recovery (7); manifest validation
(2 or 4); source resolution and local-content access (2 or 3); Principle-I
source validation (10); environment requirements (5); generated payload
validation (4, 8, or 10); and finally publication/post-write verification (6).
The first failing stage wins and later stages are not attempted. A missing
`requires` provider is therefore a system refusal with exit 5, not a warning.
An unsupported optional hook is a successful install with a degradation entry.

With `--json`, stdout contains one LF-terminated UTF-8 object with schema
`haex-install-result-v1`:

```json
{
  "schema": "haex-install-result-v1",
  "status": "installed",
  "exit_code": 0,
  "generation": "<generation-id-or-null>",
  "degradations": [],
  "error": null
}
```

`status` is `installed`, `no_changes`, or `refused`; `generation` is null on
refusal. `degradations` is always present and sorted by
`(target, kind, id, event)`. Every degradation item MUST be an object with
exactly these required properties, all non-empty UTF-8 strings:
`target`, `kind`, `id`, `event`, `fallback`, and `reason`. `fallback` names the
weaker mechanism installed, while `reason` explains the unsupported
capability. No additional properties are permitted, and neither field may
contain a secret value. `error` is null on success and otherwise contains only
`{ "key": <diagnostic-key>, "message": <safe-message> }`; its message never
contains a secret value. The JSON schema is versioned by the `schema` field,
and the exit code is duplicated in `exit_code` so an orchestrator can use
either the process result or the captured object.

## Reader consistency (informational)

Third-party readers (agent CLIs, editors) do not invoke this CLI — they read the participating output roots directly. Per FR-005, correct readers:

1. Acquire the shared/read lock before the initial `.haex-hive/install.lock` read and retain it through validation and consumption.
2. Pass the lock's `haex_hive_version` schema/migration gate first.
3. Reject unsupported versions, retired fields, and required migrations; do not treat that lock as authoritative or rewrite it implicitly.
4. Verify that every path in `install.lock.molecules[].paths[]` exists.
5. For mixed-ownership roots, verify that every active adapter pointer names `install.lock.generation_id`.
6. Treat a missing lock, missing path, or generation mismatch as an unavailable installation, never as a partially-valid one.

The Spec 008 landing includes a reference reader-guide in [quickstart.md](../quickstart.md) for adapter authors.

## Deferred to later specs

- **Publisher-hook invocations** (Spec 009 territory) — will surface as a new `entry_type` in the journal and matching CLI diagnostic; no change to this contract.
- **Adapter-emitted outputs** (Spec 010 territory) — will surface as additional molecule `paths` under mixed-ownership roots; the CLI schema of THIS spec already accommodates them without change.

## Sibling subcommands

`haex constitution show` remains as the read-only inverse of `haex install`: it prints the byte-for-byte effective constitution from the currently published generation. It does not resolve, assemble, or write.

The former `haex constitution assemble` shortcut was retired in favour of
`haex install`. Under the pre-user policy, keeping two commands doing the same
work carried UX cost without adoption benefit. The install command does not
accept the retired `--llm` or `--accept-merged` flags.
